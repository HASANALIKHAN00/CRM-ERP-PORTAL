from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_, case
from datetime import date, datetime, timedelta
import models
import erpnext_client
import re

TIME_OF_DAY_BUCKETS = {
    "Morning": (6, 12),
    "Afternoon": (12, 17),
    "Evening": (17, 21),
    "Night": (21, 6),  # wraps past midnight
}


BLOCKED_FOR_SALES_USER = {
    "summary": "This report isn't available for your account. It covers team-wide or company-wide data rather than your own customers.",
    "records": [],
    "source": "Access restricted to admin",
}

NOT_YOUR_CUSTOMER = {
    "summary": "No matching customer found in your assigned accounts.",
    "records": [],
    "source": "Access restricted \u2014 this customer is not assigned to you",
}

def clean_department_label(raw: str) -> str:
    """
    ERPNext's Employee.department stores the real Department doc ID, which
    includes a trailing " - <Company>" suffix (added to keep names unique
    across companies) and sometimes double-spaced raw entry, e.g.
    "Software Department  - BT". Strips both for display purposes only --
    filtering logic still matches against the raw underlying value.
    """
    if not raw:
        return raw
    cleaned = re.sub(r"\s*-\s*[A-Za-z0-9]+$", "", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def apply_time_of_day_filter(query, time_of_day: str, time_column):
    if not time_of_day or time_of_day not in TIME_OF_DAY_BUCKETS:
        return query
    start, end = TIME_OF_DAY_BUCKETS[time_of_day]
    hour_expr = extract('hour', time_column)
    if start < end:
        return query.filter(hour_expr >= start, hour_expr < end)
    return query.filter(or_(hour_expr >= start, hour_expr < end))


def resolve_period(days: int = None, this_month: bool = False, start_date: str = None, end_date: str = None, default_days: int = 30):
    """
    Shared time-window resolver. Priority order: explicit start_date/end_date
    (a real arbitrary range) > this_month (real calendar-month boundary) >
    a rolling N-day window, which is what a plain 'days' value means.

    Returns a 3-tuple (start, end, period_label) -- callers must filter on
    BOTH bounds now, not just >= start, since an arbitrary range has a real
    end date that isn't necessarily today.
    """
    today = date.today()
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
        return start, end, f"{start_date} to {end_date or str(today)}"
    if this_month:
        return today.replace(day=1), today, "this month"
    days = days or default_days
    # N-day window INCLUDING today spans back (N-1) days, not N -- e.g.
    # "Today" (days=1) must mean exactly today, not today AND yesterday.
    # Confirmed 2026-07-24: the old `today - timedelta(days=days)` math
    # made every preset (Today/This week/This month) silently one calendar
    # day wider than labeled, across every function using this helper.
    return today - timedelta(days=days - 1), today, f"the last {days} days"



def get_calls_by_salesperson_this_week(db: Session, user_id: str = None, role: str = "admin"):
    # See get_calls_today for why this filters on activity_type rather than
    # the unreliable activity_scenario field.
    cutoff = date.today() - timedelta(days=6)  # 7-day window including today, not 8 -- see resolve_period's fix note
    query = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == user_id)
    results = query.group_by(models.CustomerActivityDetail.logged_by_user).all()
    return {
        "summary": "Calls by salesperson over the last 7 days.",
        "records": [{"salesperson": u or "Unassigned", "count": c} for u, c in results],
        "source": f"Based on {sum(c for _, c in results)} Customer Activity Detail records (activity_type = 'Phone Call')"
    }

def get_last_sync_time(db: Session):
    run = (
        db.query(models.SyncRun)
        .filter(models.SyncRun.completed_at.isnot(None))
        .order_by(models.SyncRun.completed_at.desc())
        .first()
    )
    if not run:
        return {
            "summary": "No completed sync runs found.",
            "records": [],
            "source": "Based on Sync Run records",
        }
    return {
        "summary": f"Last data sync completed at {run.completed_at.isoformat()} ({run.result}).",
        "records": [{
            "completed_at": run.completed_at.isoformat(),
            "result": run.result,
            "records_processed": run.records_processed,
        }],
        "source": "Based on Sync Run records",
    }


def get_stale_customers(db: Session, days: int = None, this_month: bool = False, country: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=7)
    subq = db.query(models.CustomerActivityDetail.customer_id).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    ).subquery().select()
    query = db.query(models.Customer).filter(
        models.Customer.customer_id.notin_(subq), models.Customer.is_disabled == False
    )
    if country:
        query = query.filter(models.Customer.country == country)
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    customers = query.all()

    # Look up each stale customer's most recent activity date (if any at all)
    # so the UI can show a real "N days ago" instead of just the query's
    # fixed cutoff window. Customers with no activity history at all get
    # last_activity_date/days_since_activity = null.
    customer_ids = [c.customer_id for c in customers]
    last_activity_by_id = {}
    if customer_ids:
        rows = (
            db.query(
                models.CustomerActivityDetail.customer_id,
                func.max(models.CustomerActivityDetail.activity_date).label("last_date"),
            )
            .filter(models.CustomerActivityDetail.customer_id.in_(customer_ids))
            .group_by(models.CustomerActivityDetail.customer_id)
            .all()
        )
        last_activity_by_id = {r.customer_id: r.last_date for r in rows}

    today = date.today()
    records = []
    for c in customers:
        last_date = last_activity_by_id.get(c.customer_id)
        records.append({
            "customer_id": c.customer_id,
            "customer_name": c.customer_name,
            "last_activity_date": last_date.isoformat() if last_date else None,
            "days_since_activity": (today - last_date).days if last_date else None,
            "monthly_recurring_value_usd": float(c.total_monthly_devices_usd or 0),
        })

    # Ranked by recurring revenue at risk (highest first), not activity
    # recency or insertion order -- the point of this list is "who should
    # I call first", and a quiet customer worth $8k/month is a bigger
    # problem than one worth $80/month, regardless of which went quiet
    # more recently.
    records.sort(key=lambda r: r["monthly_recurring_value_usd"], reverse=True)

    return {
        "summary": f"{len(customers)} customer(s) with no activity in {period_label}.",
        "records": records,
        "source": f"Based on {len(customers)} Customer and Customer Activity Detail records; ranked by recurring monthly device value (Customer.total_monthly_devices_usd)"
    }


def get_total_sales_value(db: Session, within_days: int = None, this_month: bool = False, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    cutoff, end, period_label = resolve_period(within_days, this_month, start_date, end_date, default_days=30)
    query = db.query(models.SalesInvoice).filter(
        models.SalesInvoice.invoice_date >= cutoff,
        models.SalesInvoice.invoice_date <= end
    )
    if role == "sales_user" and user_id:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == user_id)
    elif employee:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == employee)
    invoices = query.all()
    total = sum(float(i.invoice_value or 0) for i in invoices)
    return {
        "summary": f"Total sales value over {period_label}: ${total:,.2f}.",
        "records": [{"invoice_id": i.invoice_id, "customer_name": i.customer_name, "value": float(i.invoice_value or 0)} for i in invoices],
        "source": f"Based on {len(invoices)} Sales Invoice records"
    }

def get_opportunities_by_stage(db: Session, employee: str = None, user_id: str = None, role: str = "admin"):
    # Filters by employee (owner_user) only -- deliberately NOT by pipeline_stage
    # itself, since collapsing a stage-distribution chart to match a single
    # selected stage would leave one bar and defeat the chart's purpose.
    # Also deliberately NOT date-scoped: pipeline_stage is a live/current field
    # on each Opportunity, so this represents "where is the pipeline right now",
    # not "what was created in a given period".
    query = db.query(
        models.Opportunity.pipeline_stage,
        func.count(models.Opportunity.opportunity_id),
        func.sum(models.Opportunity.total_value_usd),
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Opportunity.owner_user == user_id)
    elif employee:
        query = query.filter(models.Opportunity.owner_user == employee)
    results = query.group_by(models.Opportunity.pipeline_stage).all()
    total_value = sum(float(v or 0) for _, _, v in results)
    return {
        "summary": f"Opportunities by pipeline stage, worth ${total_value:,.2f} total.",
        "records": [
            {"stage": stage or "Unspecified", "count": count, "total_value_usd": round(float(v or 0), 2)}
            for stage, count, v in results
        ],
        "source": f"Based on {sum(c for _, c, _ in results)} Opportunity records"
    }

def get_opportunities_in_stage(db: Session, stage: str = None, employee: str = None, user_id: str = None, role: str = "admin"):
    """
    Drill-down counterpart to get_opportunities_by_stage. That function
    deliberately doesn't filter by pipeline_stage (it would collapse the
    distribution to one bar). This one is the actual place a Sales Stage
    filter has real teeth: list the individual opportunities currently in
    a given stage, so selecting a stage answers "which deals, exactly?"
    rather than trying to force a distribution chart to filter itself.
    """
    query = db.query(models.Opportunity)
    if stage:
        query = query.filter(models.Opportunity.pipeline_stage == stage)
    if role == "sales_user" and user_id:
        query = query.filter(models.Opportunity.owner_user == user_id)
    elif employee:
        query = query.filter(models.Opportunity.owner_user == employee)
    opportunities = query.order_by(models.Opportunity.total_value_usd.desc().nullslast()).limit(50).all()
    today = date.today()
    records = []
    for o in opportunities:
        days_open = (today - o.opportunity_date).days if o.opportunity_date else None
        # Positive = days remaining until the deal's own committed close date;
        # negative = days past it without having closed. Distinct from days_open
        # (which just measures age) -- this measures whether the deal is on
        # track for the date it was actually forecast to close.
        days_until_close = (o.expected_closing_date - today).days if o.expected_closing_date else None
        records.append({
            "opportunity_id": o.opportunity_id,
            "customer_name": o.customer_name,
            "pipeline_stage": o.pipeline_stage or "Unspecified",
            "owner_user": o.owner_user,
            "total_value_usd": float(o.total_value_usd or 0),
            "days_open": days_open,
            "expected_closing_date": o.expected_closing_date.isoformat() if o.expected_closing_date else None,
            "days_until_close": days_until_close,
        })
    stage_desc = f" in stage '{stage}'" if stage else ""
    return {
        "summary": f"{len(records)} opportunit{'y' if len(records) == 1 else 'ies'}{stage_desc}, ranked by value.",
        "records": records,
        "source": "Based on Opportunity records"
    }

def get_opportunity_close_forecast(db: Session, employee: str = None, user_id: str = None, role: str = "admin"):
    """
    Buckets OPEN opportunities (excludes Converted/Closed/Lost) by how
    close -- or how overdue -- they are against their own committed
    expected_closing_date. Distinct from get_opportunities_by_stage
    (where a deal sits in the pipeline) and get_opportunities_in_stage's
    per-deal days_until_close; this is the aggregate forecast view: how
    much is genuinely coming due soon vs. already past its committed
    date. Not date-range filterable by the dashboard's global range
    selector -- expected_closing_date is a field on each Opportunity,
    not an activity being counted within a window, same reasoning as
    get_opportunities_by_stage's pipeline_stage.

    Caveat worth surfacing to the caller: total_value_usd is sparsely
    populated on many Opportunity rows, so the dollar figures here
    likely undercount the real pipeline value in each bucket -- treat
    the counts as the more reliable number.
    """
    query = db.query(models.Opportunity).filter(
        models.Opportunity.status.notin_(["Converted", "Closed", "Lost"])
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Opportunity.owner_user == user_id)
    elif employee:
        query = query.filter(models.Opportunity.owner_user == employee)
    opportunities = query.all()

    today = date.today()

    def bucket_for(o):
        if o.expected_closing_date is None:
            return "No date set"
        days = (o.expected_closing_date - today).days
        if days < 0:
            return "Overdue"
        if days <= 30:
            return "Closing within 30 days"
        if days <= 90:
            return "Closing within 90 days"
        return "Closing later than 90 days"

    bucket_order = ["Closing within 30 days", "Closing within 90 days", "Closing later than 90 days", "Overdue", "No date set"]
    totals = {b: {"count": 0, "value": 0.0} for b in bucket_order}
    for o in opportunities:
        b = bucket_for(o)
        totals[b]["count"] += 1
        totals[b]["value"] += float(o.total_value_usd or 0)

    records = [
        {"bucket": b, "count": totals[b]["count"], "value": round(totals[b]["value"], 2)}
        for b in bucket_order if totals[b]["count"] > 0
    ]
    total_count = sum(r["count"] for r in records)
    total_value = sum(r["value"] for r in records)

    return {
        "summary": (
            f"{total_count} open opportunit{'y' if total_count == 1 else 'ies'} with a recorded value totaling "
            f"${total_value:,.2f} (likely an undercount -- total_value_usd is sparse), by proximity to their "
            f"expected closing date."
        ),
        "records": records,
        "source": "Based on Opportunity records with status not in (Converted, Closed, Lost)"
    }

def get_call_to_sales_ratio(db: Session, days: int = None, this_month: bool = False, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    A customer-level correlation, not a record-level causal link: there is
    no field connecting a specific call to the Sales Order it may have led
    to (same gap investigated for Todo.linked_doctype -- it only points
    generically to a Customer, not to a specific call or activity). This
    counts customers who were called AND got a new Sales Order in the same
    window, which is the closest honest approximation buildable from the
    current schema.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)

    called_q = db.query(models.CustomerActivityDetail.customer_id).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if employee:
        called_q = called_q.filter(models.CustomerActivityDetail.logged_by_user == employee)
    called_customers = {r[0] for r in called_q.distinct().all()}

    sold_customers = {r[0] for r in db.query(models.SalesOrder.customer_id).filter(
        models.SalesOrder.order_date >= cutoff,
        models.SalesOrder.order_date <= end
    ).distinct().all()}

    overlap = called_customers & sold_customers
    ratio = round((len(overlap) / len(called_customers)) * 100, 1) if called_customers else 0

    return {
        "summary": (
            f"{len(overlap)} of {len(called_customers)} called customers ({ratio}%) also had a new Sales Order "
            f"in {period_label}. This is a customer-level correlation, not proof the call caused the sale -- "
            "there's no record-level link between a specific call and a specific order in the synced data."
        ),
        "records": [
            {"metric": "Customers called", "value": len(called_customers)},
            {"metric": "Customers called AND with a new sales order", "value": len(overlap)},
            {"metric": "Correlation rate (%)", "value": ratio},
        ],
        "source": "Customer-level correlation between Customer Activity Detail (calls) and Sales Order records \u2014 not a causal, record-level link"
    }

def get_lead_to_opportunity_conversion(db: Session, user_id: str = None, role: str = "admin"):
    """
    Mirrors the honest-caveat pattern in get_opportunity_to_quotation_conversion:
    only reports a percentage when there is an actual traceable link between
    the two record types, otherwise says so explicitly instead of dividing
    two unrelated counts.

    Checked on 2026-07-15: Opportunity has no synced field referencing a
    source Lead (see sync_config.py's Opportunity field_map), and Lead has
    no customer_id to cross-reference by customer either. So "new leads this
    month" and "new opportunities this month" are two independent counts
    with zero queryable relationship -- dividing one by the other can and
    does produce nonsense (e.g. 1 lead vs 57 opportunities = 5700%), not
    because conversion is happening at that rate but because the two counts
    don't describe the same cohort at all.

    LINKAGE_AVAILABLE is hardcoded False because no such field is synced
    today. If a real lead-reference field is later added to Opportunity's
    sync_config.py mapping (worth asking Hassan whether ERPNext's Opportunity
    doctype has one, e.g. via 'opportunity_from'), this function should be
    updated to count actual linked records the way get_opportunity_to_quotation_conversion
    does, rather than just flipping this flag.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    LINKAGE_AVAILABLE = False

    start_of_month = date.today().replace(day=1)
    new_leads = db.query(func.count(models.Lead.lead_id)).filter(
        func.date(models.Lead.created_at) >= start_of_month
    ).scalar()
    new_opportunities = db.query(func.count(models.Opportunity.opportunity_id)).filter(
        func.date(models.Opportunity.created_at) >= start_of_month
    ).scalar()

    if LINKAGE_AVAILABLE:
        summary = f"{new_leads} new lead(s), {new_opportunities} new opportunity/opportunities this month."
    else:
        summary = (
            f"{new_leads} new lead(s) and {new_opportunities} new opportunity/opportunities this month, "
            "but a conversion rate can't be shown: Opportunity records have no synced field linking back "
            "to a source Lead, so a percentage here would compare two unrelated counts rather than a real "
            "conversion."
        )

    return {
        "summary": summary,
        "records": [
            {"metric": "New leads (month)", "value": new_leads},
            {"metric": "New opportunities (month)", "value": new_opportunities},
            {"metric": "linkage_available", "value": LINKAGE_AVAILABLE},
        ],
        "source": "Based on Lead and Opportunity records \u2014 no lead-to-opportunity link field is currently synced"
    }


def get_new_leads_this_month(db: Session, status: str = None, user_id: str = None, role: str = "admin"):
    start_of_month = date.today().replace(day=1)
    query = db.query(models.Lead).filter(func.date(models.Lead.created_at) >= start_of_month)
    if status:
        query = query.filter(models.Lead.status == status)
    if role == "sales_user" and user_id:
        query = query.filter(models.Lead.owner_user == user_id)
    leads = query.all()
    return {
        "summary": f"{len(leads)} new lead(s) created this month.",
        "records": [{"lead_id": l.lead_id, "client_name": l.client_name, "status": l.status} for l in leads],
        "source": f"Based on {len(leads)} Leads records"
    }


def get_customers_with_pending_payments(db: Session, user_id: str = None, role: str = "admin"):
    query = db.query(models.SalesInvoice).filter(models.SalesInvoice.outstanding_amount > 0)
    if role == "sales_user" and user_id:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == user_id)
    invoices = query.all()
    total_outstanding = sum(float(i.outstanding_amount or 0) for i in invoices)
    return {
        "summary": f"{len(invoices)} invoice(s) with pending payment, totaling ${total_outstanding:,.2f}.",
        "records": [{"customer_name": i.customer_name, "invoice_id": i.invoice_id, "outstanding": float(i.outstanding_amount or 0)} for i in invoices],
        "source": f"Based on {len(invoices)} Sales Invoice records"
    }


def get_invoice_aging(db: Session, user_id: str = None, role: str = "admin"):
    """
    Buckets outstanding (unpaid) Sales Invoice balances by how overdue
    they are, so collections can be prioritized by age rather than seeing
    only one lump "pending payments" total (see
    get_customers_with_pending_payments for that flat figure). Bucket
    order is fixed rather than sorted by size, since the aging
    progression itself is the point.
    """
    today = date.today()
    query = db.query(models.SalesInvoice).filter(models.SalesInvoice.outstanding_amount > 0)
    if role == "sales_user" and user_id:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == user_id)
    invoices = query.all()

    def bucket_for(inv):
        if inv.due_date is None:
            return "No due date"
        days_overdue = (today - inv.due_date).days
        if days_overdue < 0:
            return "Not yet due"
        if days_overdue <= 30:
            return "1-30 days overdue"
        if days_overdue <= 60:
            return "31-60 days overdue"
        return "60+ days overdue"

    bucket_order = ["Not yet due", "1-30 days overdue", "31-60 days overdue", "60+ days overdue", "No due date"]
    totals = {b: {"count": 0, "amount": 0.0} for b in bucket_order}
    for inv in invoices:
        b = bucket_for(inv)
        totals[b]["count"] += 1
        totals[b]["amount"] += float(inv.outstanding_amount or 0)

    records = [
        {"bucket": b, "count": totals[b]["count"], "amount": round(totals[b]["amount"], 2)}
        for b in bucket_order
        if totals[b]["count"] > 0
    ]
    grand_total = sum(r["amount"] for r in records)

    return {
        "summary": f"{len(invoices)} unpaid invoice(s) totaling ${grand_total:,.2f}, broken down by how overdue they are.",
        "records": records,
        "source": f"Based on {len(invoices)} Sales Invoice records with outstanding_amount > 0"
    }


def get_sales_invoices_between_dates(db: Session, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    query = db.query(models.SalesInvoice)
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        query = query.filter(models.SalesInvoice.invoice_date >= start)
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        query = query.filter(models.SalesInvoice.invoice_date <= end)
    if role == "sales_user" and user_id:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == user_id)
    invoices = query.all()
    total = sum(float(i.invoice_value or 0) for i in invoices)
    range_label = f"between {start_date} and {end_date}" if start_date and end_date else (
        f"up to {end_date}" if end_date else (f"from {start_date} onward" if start_date else "across all available history")
    )
    return {
        "summary": f"{len(invoices)} invoice(s) {range_label}, totaling ${total:,.2f}.",
        "records": [{"invoice_id": i.invoice_id, "customer_name": i.customer_name, "date": str(i.invoice_date), "value": float(i.invoice_value or 0)} for i in invoices],
        "source": f"Based on {len(invoices)} Sales Invoice records"
    }


def get_activities_for_customer(db: Session, customer_id: str, user_id: str = None, role: str = "admin"):
    if role == "sales_user" and user_id:
        owned = db.query(models.Customer).filter(
            models.Customer.customer_id == customer_id,
            models.Customer.account_manager_user == user_id
        ).first()
        if not owned:
            return NOT_YOUR_CUSTOMER

    activities = db.query(models.CustomerActivityDetail).filter(
        models.CustomerActivityDetail.customer_id == customer_id
    ).order_by(models.CustomerActivityDetail.activity_date.desc()).all()
    return {
        "summary": f"{len(activities)} activity record(s) for customer {customer_id}.",
        "records": [{"date": str(a.activity_date), "type": a.activity_type, "status": a.status, "result": a.result} for a in activities],
        "source": f"Based on {len(activities)} Customer Activity Detail records"
    }


def _filtered_activity_rows(db: Session, days: int = None, time_from: str = None, time_to: str = None,
                            activity_type: str = None, status: str = None, employee: str = None,
                            country: str = None, start_date: str = None, end_date: str = None,
                            user_id: str = None, role: str = "admin"):
    """Return CRM activities after applying the dashboard's shared filters."""
    # `resolve_period` intentionally treats an explicit start as the custom
    # range trigger.  A To-only dashboard filter also needs to be honoured,
    # so start at the earliest returned activity rather than silently falling
    # back to the rolling preset.
    if end_date and not start_date:
        start = date.min
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        start, end, _ = resolve_period(days, start_date=start_date, end_date=end_date, default_days=30)
    query = db.query(models.CustomerActivityDetail).filter(
        models.CustomerActivityDetail.activity_date >= start,
        models.CustomerActivityDetail.activity_date <= end,
    )
    if activity_type:
        query = query.filter(models.CustomerActivityDetail.activity_type == activity_type)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    if country:
        query = query.join(models.Customer).filter(models.Customer.country == country)
    if time_from:
        query = query.filter(models.CustomerActivityDetail.activity_time >= datetime.strptime(time_from, "%H:%M").time())
    if time_to:
        query = query.filter(models.CustomerActivityDetail.activity_time <= datetime.strptime(time_to, "%H:%M").time())
    if role == "sales_user" and user_id:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == user_id)
    rows = query.all()
    if end_date and not start_date:
        start = min((row.activity_date for row in rows if row.activity_date), default=end)
    return rows, start, end


def _activity_group_records(rows, start: date, end: date, group_by: str):
    """Aggregate real rows and keep expected empty periods as zero-valued slots."""
    group_by = (group_by or "day").lower()
    counts = {}
    if group_by in ("hour", "30min"):
        for row in rows:
            # Many Customer Activity Detail rows have activity_date but no
            # activity_time. Still count them (00:00 / first half-hour) so
            # Group By Hour and 30 Minutes match the real record set.
            t = row.activity_time
            hour = t.hour if t is not None else 0
            minute = t.minute if t is not None else 0
            key = f"{hour:02d}:{(30 if group_by == '30min' and minute >= 30 else 0):02d}"
            counts[key] = counts.get(key, 0) + 1
        slots = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in ([0, 30] if group_by == "30min" else [0])]
        return [{"time_slot": slot, "activity_count": counts.get(slot, 0)} for slot in slots]

    if group_by == "week":
        week_start = lambda value: value - timedelta(days=value.weekday())
        for row in rows:
            if not row.activity_date:
                continue
            key = week_start(row.activity_date).isoformat()
            counts[key] = counts.get(key, 0) + 1
        cursor, records = week_start(start), []
        while cursor <= end:
            key = cursor.isoformat()
            records.append({"period": key, "activity_count": counts.get(key, 0)})
            cursor += timedelta(days=7)
        return records

    if group_by == "month":
        for row in rows:
            if not row.activity_date:
                continue
            key = row.activity_date.strftime("%Y-%m")
            counts[key] = counts.get(key, 0) + 1
        cursor, records = start.replace(day=1), []
        while cursor <= end:
            key = cursor.strftime("%Y-%m")
            records.append({"period": key, "activity_count": counts.get(key, 0)})
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        return records

    if group_by == "year":
        for row in rows:
            if not row.activity_date:
                continue
            key = str(row.activity_date.year)
            counts[key] = counts.get(key, 0) + 1
        return [{"period": str(year), "activity_count": counts.get(str(year), 0)} for year in range(start.year, end.year + 1)]

    for row in rows:
        if not row.activity_date:
            continue
        key = row.activity_date.isoformat()
        counts[key] = counts.get(key, 0) + 1
    cursor, records = start, []
    while cursor <= end:
        key = cursor.isoformat()
        records.append({"period": key, "activity_count": counts.get(key, 0)})
        cursor += timedelta(days=1)
    return records


def get_activities_by_time_slot(db: Session, days: int = None, time_from: str = None, time_to: str = None, activity_type: str = None, status: str = None, employee: str = None, country: str = None, group_by: str = "hour", start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    rows, start, end = _filtered_activity_rows(db, days, time_from, time_to, activity_type, status, employee, country, start_date, end_date, user_id, role)
    return {"summary": f"Activity grouped by {group_by}.", "records": _activity_group_records(rows, start, end, group_by), "source": f"Based on {len(rows)} Customer Activity Detail records"}


def get_activities_by_period(db: Session, days: int = None, time_from: str = None, time_to: str = None, activity_type: str = None, status: str = None, employee: str = None, country: str = None, group_by: str = "day", start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    rows, start, end = _filtered_activity_rows(db, days, time_from, time_to, activity_type, status, employee, country, start_date, end_date, user_id, role)
    return {"summary": f"Activity grouped by {group_by}.", "records": _activity_group_records(rows, start, end, group_by), "source": f"Based on {len(rows)} Customer Activity Detail records"}


def compare_weekly_activity(db: Session, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    # Both windows are now genuinely 7 days each (previously this_week was
    # 8 days and last_week was 7 -- an unfair comparison on top of the
    # same off-by-one fixed in resolve_period).
    this_week_start = date.today() - timedelta(days=6)
    last_week_start = date.today() - timedelta(days=13)
    this_week = db.query(func.count(models.CustomerActivityDetail.id)).filter(
        models.CustomerActivityDetail.activity_date >= this_week_start
    ).scalar()
    last_week = db.query(func.count(models.CustomerActivityDetail.id)).filter(
        models.CustomerActivityDetail.activity_date >= last_week_start,
        models.CustomerActivityDetail.activity_date < this_week_start
    ).scalar()
    change = this_week - last_week
    return {
        "summary": f"This week: {this_week} activities. Last week: {last_week} activities. Change: {'+' if change >= 0 else ''}{change}.",
        "records": [{"period": "This week", "count": this_week}, {"period": "Last week", "count": last_week}],
        "source": "Based on Customer Activity Detail records"
    }

def compare_monthly_activity(db: Session, user_id: str = None, role: str = "admin"):
    """
    Mirrors compare_weekly_activity's pattern, but calendar months differ in
    length and "this month" is necessarily partial (1st through today), so
    a raw count comparison would be misleading -- e.g. 3 days of this month
    vs 30 full days of last month would look like a huge decline even at an
    identical daily pace. Reports both raw counts (for context) and a
    daily-average comparison (the actually fair, like-for-like number).
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    days_elapsed_this_month = (today - this_month_start).days + 1
    days_in_last_month = (last_month_end - last_month_start).days + 1

    this_month_count = db.query(func.count(models.CustomerActivityDetail.id)).filter(
        models.CustomerActivityDetail.activity_date >= this_month_start
    ).scalar()
    last_month_count = db.query(func.count(models.CustomerActivityDetail.id)).filter(
        models.CustomerActivityDetail.activity_date >= last_month_start,
        models.CustomerActivityDetail.activity_date < this_month_start
    ).scalar()

    this_month_avg = round(this_month_count / days_elapsed_this_month, 1) if days_elapsed_this_month else 0
    last_month_avg = round(last_month_count / days_in_last_month, 1) if days_in_last_month else 0
    avg_change = round(this_month_avg - last_month_avg, 1)

    return {
        "summary": (
            f"This month so far ({days_elapsed_this_month} days): {this_month_count} activities "
            f"({this_month_avg}/day). Last month (full {days_in_last_month} days): {last_month_count} activities "
            f"({last_month_avg}/day). Daily-average change: {'+' if avg_change >= 0 else ''}{avg_change}/day. "
            "Raw totals aren't directly comparable since this month is still in progress -- the daily average "
            "is the fair comparison."
        ),
        "records": [
            {"period": "This month (to date)", "count": this_month_count, "daily_avg": this_month_avg},
            {"period": "Last month (full)", "count": last_month_count, "daily_avg": last_month_avg},
        ],
        "source": "Based on Customer Activity Detail records"
    }

def get_high_value_low_engagement_customers(db: Session, engagement_days: int = None, this_month: bool = False, min_value: float = 1000, country: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    "High value" blends two lenses: historical one-off Sales Invoice
    total, and recurring device revenue (Customer.total_monthly_devices_usd,
    annualized x12 so it's on the same scale as a lump invoice sum) --
    not invoice history alone. A customer on a purely recurring
    arrangement with zero discrete invoices previously fell through this
    report entirely, since it inner-joined to invoices and zero invoices
    meant zero rows; that's fixed here by outer-joining and treating
    missing invoice history as $0 rather than excluding the customer.
    Ranked by the combined figure, so the biggest overall relationship
    going quiet surfaces first -- a customer with strong MRR and no
    invoice history can outrank one with a single large invoice from
    years ago and nothing recurring today.
    """
    cutoff, end, period_label = resolve_period(engagement_days, this_month, start_date, end_date, default_days=14)
    recent_activity_subq = db.query(models.CustomerActivityDetail.customer_id).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    ).subquery().select()
    sales_by_customer = db.query(
        models.SalesInvoice.customer_id, func.sum(models.SalesInvoice.invoice_value).label("total")
    ).group_by(models.SalesInvoice.customer_id).subquery()
    query = db.query(models.Customer, sales_by_customer.c.total).outerjoin(
        sales_by_customer, models.Customer.customer_id == sales_by_customer.c.customer_id
    ).filter(
        models.Customer.customer_id.notin_(recent_activity_subq)
    )
    if country:
        query = query.filter(models.Customer.country == country)
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    rows = query.all()

    records = []
    for c, sales_total in rows:
        historical_sales_value = float(sales_total or 0)
        monthly_recurring_value = float(c.total_monthly_devices_usd or 0)
        combined_value = historical_sales_value + monthly_recurring_value * 12
        if combined_value < min_value:
            continue
        records.append({
            "customer_name": c.customer_name,
            "total_sales_value": round(historical_sales_value, 2),
            "monthly_recurring_value_usd": round(monthly_recurring_value, 2),
            "combined_value_usd": round(combined_value, 2),
        })
    records.sort(key=lambda r: r["combined_value_usd"], reverse=True)

    return {
        "summary": (
            f"{len(records)} customer(s) with combined value (historical sales + annualized recurring "
            f"revenue) \u2265 ${min_value:,.0f} but no activity in {period_label}."
        ),
        "records": records,
        "source": "Based on Sales Invoice, Customer Activity Detail, and Customer.total_monthly_devices_usd (annualized) records"
    }


def get_activities_by_employee(db: Session, days: int = None, this_month: bool = False, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    results = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    ).group_by(
        models.CustomerActivityDetail.logged_by_user
    ).order_by(func.count(models.CustomerActivityDetail.id).desc()).all()
    return {
        "summary": f"Activities logged per employee over {period_label}, highest first.",
        "records": [{"employee": u, "count": c} for u, c in results],
        "source": f"Based on {sum(c for _, c in results)} Customer Activity Detail records"
    }

def get_opportunity_to_quotation_conversion(db: Session, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    total_opportunities = db.query(func.count(models.Opportunity.opportunity_id)).scalar()
    linked_quotations = db.query(func.count(func.distinct(models.Quotation.opportunity_id))).filter(
        models.Quotation.opportunity_id.isnot(None)
    ).scalar()
    total_quotations = db.query(func.count(models.Quotation.quotation_id)).scalar()
    return {
        "summary": (
            f"{linked_quotations} of {total_opportunities} opportunities have a traceably-linked quotation. "
            f"Note: only a minority of quotations in ERPNext currently have the opportunity link filled in "
            f"({linked_quotations} of {total_quotations} total quotations), so this likely undercounts the "
            f"real conversion rate rather than overstating it."
        ),
        "records": [
            {"metric": "Total opportunities", "value": total_opportunities},
            {"metric": "Total quotations", "value": total_quotations},
            {"metric": "Quotations linked to an opportunity", "value": linked_quotations},
        ],
        "source": "Based on Opportunity and Quotation records; linkage completeness noted above"
    }


def get_quotation_status_breakdown(db: Session, user_id: str = None, role: str = "admin"):
    """
    Quotation value and count grouped by status, in funnel order (Draft
    -> Open -> Ordered, with Expired/Cancelled as the off-ramps) rather
    than sorted by size -- the progression is the point, same reasoning
    as get_invoice_aging's bucket ordering. Shows how much quotation
    value is stuck at each stage, which get_opportunity_to_quotation_conversion
    doesn't surface (that one only tracks whether a quotation exists at
    all, not what happened to it). Company-wide, so unlike most reports
    here it's not available to sales_user accounts -- Quotation has no
    direct owner/account-manager column to scope by.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    results = db.query(
        models.Quotation.status,
        func.count(models.Quotation.quotation_id),
        func.sum(models.Quotation.grand_total),
    ).group_by(models.Quotation.status).all()

    status_order = ["Draft", "Open", "Ordered", "Expired", "Cancelled"]
    by_status = {(s or "Unspecified"): (c, float(v or 0)) for s, c, v in results}
    ordered_statuses = status_order + sorted(s for s in by_status if s not in status_order)

    records = [
        {"status": s, "count": by_status[s][0], "value": round(by_status[s][1], 2)}
        for s in ordered_statuses if s in by_status
    ]
    total_count = sum(r["count"] for r in records)
    total_value = sum(r["value"] for r in records)
    return {
        "summary": f"{total_count} quotation(s) worth ${total_value:,.2f}, broken down by status.",
        "records": records,
        "source": f"Based on {total_count} Quotation records"
    }


def get_sample_testing_funnel(db: Session, user_id: str = None, role: str = "admin"):
    """
    Customer Sample Testing records grouped by test_stage, in funnel
    order (earliest evaluation stage first) rather than sorted by size --
    shows where hardware evaluations stall before a sale even gets to
    the Opportunity/Quotation stage. A leading indicator sitting earlier
    in the pipeline than everything get_opportunities_by_stage covers.
    """
    query = db.query(
        models.CustomerSampleTesting.test_stage,
        func.count(models.CustomerSampleTesting.id),
    )
    if role == "sales_user" and user_id:
        query = query.join(
            models.Customer, models.Customer.customer_id == models.CustomerSampleTesting.customer_id
        ).filter(models.Customer.account_manager_user == user_id)
    results = query.group_by(models.CustomerSampleTesting.test_stage).all()

    stage_order = [
        "Initial Contact & Key Contact Identified",
        "Device Proposed & Sample Requested",
        "Testing Approved & Sample Delivered",
        "Technical Setup & Installation",
        "Testing & Issue Resolution",
        "Testing Completed & Feedback Shared",
    ]
    by_stage = {(s or "Unspecified"): c for s, c in results}
    ordered_stages = stage_order + sorted(s for s in by_stage if s not in stage_order)

    records = [{"stage": s, "count": by_stage[s]} for s in ordered_stages if s in by_stage]
    total = sum(r["count"] for r in records)
    return {
        "summary": f"{total} customer(s) currently in sample testing, across {len(records)} stage(s).",
        "records": records,
        "source": f"Based on {total} Customer Sample Testing records"
    }


def get_customers_by_country(db: Session, user_id: str = None, role: str = "admin"):
    query = db.query(models.Customer.country, func.count(models.Customer.customer_id))
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    results = query.group_by(models.Customer.country).order_by(func.count(models.Customer.customer_id).desc()).all()
    return {
        "summary": "Customers by country.",
        "records": [{"country": c or "Unspecified", "count": n} for c, n in results],
        "source": f"Based on {sum(n for _, n in results)} Customer records"
    }


def get_clients_reached(db: Session, days: int = None, this_month: bool = False, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=7)
    query = db.query(func.count(func.distinct(models.CustomerActivityDetail.customer_id))).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    )
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    count = query.scalar()
    return {
        "summary": f"{count} distinct client(s) reached in {period_label}.",
        "records": [{"period": period_label, "clients_reached": count}],
        "source": "Based on Customer Activity Detail records"
    }


def get_meeting_count(db: Session, days: int = None, this_month: bool = False, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, default_days=30)
    count = db.query(models.CustomerActivityDetail).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type.ilike("%meeting%")
    ).count()
    return {
        "summary": f"{count} meeting(s) logged in {period_label}.",
        "records": [{"period": period_label, "meeting_count": count}],
        "source": "Based on Customer Activity Detail records \u2014 filtered on activity_type containing 'meeting'; exact label not yet validated against real data"
    }


def get_quotations_sent(db: Session, days: int = None, this_month: bool = False, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, default_days=30)
    quotations = db.query(models.Quotation).filter(
        models.Quotation.transaction_date >= cutoff,
        models.Quotation.transaction_date <= end
    ).all()
    return {
        "summary": f"{len(quotations)} quotation(s) sent in {period_label}.",
        "records": [{"quotation_id": q.quotation_id, "customer_name": q.customer_name, "grand_total": float(q.grand_total or 0)} for q in quotations],
        "source": f"Based on {len(quotations)} Quotation records"
    }


def get_phone_call_activity(db: Session, days: int = None, this_month: bool = False, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, default_days=30)
    count = db.query(models.CustomerActivityDetail).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    ).count()
    return {
        "summary": f"{count} phone call activity/activities logged in {period_label}.",
        "records": [{"period": period_label, "call_count": count}],
        "source": "Based on Customer Activity Detail records (activity_type = 'Phone Call') \u2014 Call Log itself remains empty; see note"
    }

def get_login_times_by_employee(db: Session, days: int = None, this_month: bool = False, user_id: str = None, role: str = "admin"):
    # NOTE: despite the name, this is login to OUR reporting tool
    # (ActivityLogEntry, our own audit log), not ERPNext. For real ERPNext
    # employee login/attendance data, see get_employee_daily_summary below,
    # which uses the actual synced Employee Checkin / Attendance doctypes.
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, default_days=7)
    results = db.query(models.ActivityLogEntry).filter(
        models.ActivityLogEntry.operation == "Login",
        models.ActivityLogEntry.logged_at >= cutoff
    ).order_by(models.ActivityLogEntry.user_id, models.ActivityLogEntry.logged_at).all()
    return {
        "summary": f"{len(results)} login event(s) logged in {period_label}.",
        "records": [{"user": r.user_id, "login_time": str(r.logged_at)} for r in results],
        "source": f"Based on {len(results)} Activity Log records"
    }

def get_employee_daily_summary(db: Session, days: int = None, this_month: bool = False, employee: str = None, department: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    Answers the checklist's "Employee login time, first and last activity,
    working hours and daily work pattern" using real ERPNext HR data --
    Employee Checkin for first/last punch times each day, Attendance for
    working_hours/status -- joined via Employee.user_id to the same email
    identifiers used elsewhere in this app (logged_by_user, etc).

    Accepts an optional department (Team filter) alongside employee --
    deliberately filters THIS table by team rather than the "Activity by
    team" distribution chart, same reasoning as Opportunities-by-stage:
    collapsing a distribution to match its own selected value defeats the
    chart's purpose, but narrowing a detail table to one team is genuinely
    useful.

    Returns an empty result set until Employee/Employee Checkin/Attendance
    read access is granted in ERPNext and a sync has run (see the new
    Tier 1b block in sync_config.py) -- that's expected, not a bug, in the
    meantime.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=7)

    # The Team dropdown sends a CLEANED label (see clean_department_label,
    # applied in get_activity_by_team), which won't literally match the raw
    # stored value (e.g. "Software Department  - BT"). Translate back to
    # every raw value that cleans to the requested label before filtering.
    department_raw_values = None
    if department:
        all_depts = [d[0] for d in db.query(models.Employee.department).distinct().all() if d[0]]
        department_raw_values = [d for d in all_depts if clean_department_label(d) == department]

    checkin_query = db.query(
        models.EmployeeCheckin.employee_id,
        func.date(models.EmployeeCheckin.time).label("day"),
        func.min(case((models.EmployeeCheckin.log_type == "IN", models.EmployeeCheckin.time))).label("first_in"),
        func.max(case((models.EmployeeCheckin.log_type == "OUT", models.EmployeeCheckin.time))).label("last_out"),
        func.count(models.EmployeeCheckin.checkin_id).label("checkin_count"),
    ).filter(
        func.date(models.EmployeeCheckin.time) >= cutoff,
        func.date(models.EmployeeCheckin.time) <= end
    )
    if employee or department:
        checkin_query = checkin_query.join(
            models.Employee, models.Employee.employee_id == models.EmployeeCheckin.employee_id
        )
        if employee:
            checkin_query = checkin_query.filter(models.Employee.user_id == employee)
        if department:
            checkin_query = checkin_query.filter(models.Employee.department.in_(department_raw_values))
    checkins = checkin_query.group_by(
        models.EmployeeCheckin.employee_id, func.date(models.EmployeeCheckin.time)
    ).all()

    attendance_query = db.query(models.Attendance).filter(
        models.Attendance.attendance_date >= cutoff,
        models.Attendance.attendance_date <= end
    )
    if employee or department:
        attendance_query = attendance_query.join(
            models.Employee, models.Employee.employee_id == models.Attendance.employee_id
        )
        if employee:
            attendance_query = attendance_query.filter(models.Employee.user_id == employee)
        if department:
            attendance_query = attendance_query.filter(models.Employee.department.in_(department_raw_values))
    checkin_by_key = {(c.employee_id, c.day): c for c in checkins}
    attendance_by_key = {
        (a.employee_id, a.attendance_date): a for a in attendance_query.all()
    }

    emp_names = {e.employee_id: e.employee_name for e in db.query(models.Employee).all()}

    # Union of employee-days present in EITHER table -- Attendance and
    # Checkin are populated independently in ERPNext (confirmed 2026-07-17:
    # Attendance had 324 real rows through the current week, Checkin had
    # only 4, from three weeks earlier). Gating on checkins existing, as an
    # earlier version of this function did, silently hid all Attendance
    # data whenever checkins happened to be sparse for the selected window.
    all_keys = set(checkin_by_key.keys()) | set(attendance_by_key.keys())

    records = []
    for emp_id, day in sorted(all_keys, key=lambda k: (str(k[1]), k[0])):
        c = checkin_by_key.get((emp_id, day))
        att = attendance_by_key.get((emp_id, day))
        records.append({
            "employee_id": emp_id,
            "employee_name": emp_names.get(emp_id, emp_id),
            "date": str(day),
            "first_checkin": str(c.first_in) if c and c.first_in else None,
            "last_checkin": str(c.last_out) if c and c.last_out else None,
            "checkin_count": c.checkin_count if c else 0,
            "working_hours": float(att.working_hours) if att and att.working_hours is not None else None,
            "status": att.status if att else None,
        })

    return {
        "summary": f"{len(records)} employee-day record(s) over {period_label}.",
        "records": records,
        "source": "Based on Employee Checkin and Attendance records, joined via Employee.user_id"
    }


def get_activity_by_team(db: Session, days: int = None, this_month: bool = False, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    Real Team filter, built on ERPNext's Department field (Employee.department)
    joined via Employee.user_id to logged_by_user.

    Includes a per-employee breakdown within each team (who's actually
    driving the number) and a period-over-period trend (current window vs.
    an equal-length prior window immediately before it) -- a flat
    team-vs-team total falls apart when, as is currently the case, only
    one team logs any customer activity at all: comparing "teams" that
    all sit at or near zero isn't informative, but that one team's own
    employee breakdown and its own trend over time still is.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)

    # Equal-length prior window immediately preceding the current one, for
    # the trend comparison (e.g. current = last 30 days, prior = the 30
    # days before that).
    window_days = (end - cutoff).days + 1
    prior_end = cutoff - timedelta(days=1)
    prior_cutoff = prior_end - timedelta(days=window_days - 1)

    current_rows = db.query(
        models.Employee.department, models.Employee.user_id, models.Employee.employee_name,
        func.count(models.CustomerActivityDetail.id)
    ).join(
        models.CustomerActivityDetail, models.CustomerActivityDetail.logged_by_user == models.Employee.user_id
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    ).group_by(models.Employee.department, models.Employee.user_id, models.Employee.employee_name).all()

    prior_rows = db.query(
        models.Employee.department, func.count(models.CustomerActivityDetail.id)
    ).join(
        models.CustomerActivityDetail, models.CustomerActivityDetail.logged_by_user == models.Employee.user_id
    ).filter(
        models.CustomerActivityDetail.activity_date >= prior_cutoff,
        models.CustomerActivityDetail.activity_date <= prior_end
    ).group_by(models.Employee.department).all()

    # Sales value attributed to each employee via the customers they manage
    # (Customer.account_manager_user), same window as the activity count.
    # This is a different attribution path than the activity count above --
    # an employee's sales value comes from invoices on customers they own,
    # not from who logged the activity -- so someone can show activity with
    # $0 attributed (not the account manager on any invoiced customer) or
    # sales value with fewer logged activities (their customers bought
    # without needing many logged touches this window).
    sales_rows = db.query(
        models.Customer.account_manager_user, func.sum(models.SalesInvoice.invoice_value)
    ).join(
        models.SalesInvoice, models.SalesInvoice.customer_id == models.Customer.customer_id
    ).filter(
        models.SalesInvoice.invoice_date >= cutoff,
        models.SalesInvoice.invoice_date <= end
    ).group_by(models.Customer.account_manager_user).all()
    sales_by_user = {u: float(v or 0) for u, v in sales_rows if u}

    # Clean display labels and re-aggregate in Python, in case multiple raw
    # values collapse to the same clean label (e.g. inconsistent spacing) --
    # same reasoning as before, now applied per-employee too.
    teams = {}
    for raw_dept, emp_id, emp_name, count in current_rows:
        label = clean_department_label(raw_dept) or "Unassigned"
        team = teams.setdefault(label, {"count": 0, "employees": {}})
        team["count"] += count
        key = emp_id or emp_name or "Unknown"
        emp = team["employees"].setdefault(key, {
            "employee": emp_id,
            "employee_name": emp_name or emp_id or "Unknown",
            "count": 0,
            "sales_value": sales_by_user.get(emp_id, 0.0),
        })
        emp["count"] += count

    prior_totals = {}
    for raw_dept, count in prior_rows:
        label = clean_department_label(raw_dept) or "Unassigned"
        prior_totals[label] = prior_totals.get(label, 0) + count

    records = []
    for label, team in teams.items():
        prior_count = prior_totals.get(label, 0)
        # None (not 0%) when there's no prior-period data to compare against --
        # a team that went from 0 to 5 isn't meaningfully "+infinity%".
        pct_change = round(((team["count"] - prior_count) / prior_count) * 100) if prior_count > 0 else None
        employees = sorted(team["employees"].values(), key=lambda e: -e["count"])
        records.append({
            "department": label,
            "count": team["count"],
            "prior_count": prior_count,
            "pct_change": pct_change,
            "employees": employees,
        })
    records.sort(key=lambda r: -r["count"])

    return {
        "summary": f"Activity by team/department over {period_label}, with per-employee breakdown (activity count and attributed sales value) and trend vs. the prior {window_days}-day period.",
        "records": records,
        "source": "Based on Customer Activity Detail records (joined via Employee.department and Employee.user_id) and Sales Invoice records attributed via each customer's account manager"
    }

def get_employee_activity_window(db: Session, days: int = None, this_month: bool = False, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    A CRM-native answer to "first and last activity and daily work pattern"
    that doesn't depend on ERPNext's HR/Attendance data at all (see
    get_employee_daily_summary for that version, currently blocked on a
    data-quality question with Hassan -- every Attendance/Checkin record
    seen so far is empty/absent). Uses logged_by_user directly -- the real
    email identifier already on every Customer Activity Detail record --
    so it works for all active CRM users, not just the subset with a
    formal, correctly-linked Employee HR record.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=7)
    query = db.query(
        models.CustomerActivityDetail.logged_by_user,
        models.CustomerActivityDetail.activity_date,
        func.min(models.CustomerActivityDetail.activity_time).label("first_activity"),
        func.max(models.CustomerActivityDetail.activity_time).label("last_activity"),
        func.count(models.CustomerActivityDetail.id).label("activity_count"),
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.logged_by_user.isnot(None)
    )
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    results = query.group_by(
        models.CustomerActivityDetail.logged_by_user, models.CustomerActivityDetail.activity_date
    ).order_by(models.CustomerActivityDetail.activity_date.desc(), models.CustomerActivityDetail.logged_by_user).all()

    return {
        "summary": f"{len(results)} employee-day record(s) over {period_label}, based on logged CRM activity.",
        "records": [
            {
                "employee": u,
                "date": str(d),
                "first_activity_time": str(t1) if t1 else None,
                "last_activity_time": str(t2) if t2 else None,
                "activity_count": c,
            }
            for u, d, t1, t2, c in results
        ],
        "source": "Based on Customer Activity Detail records (activity_time)"
    }

def get_team_performance_summary(db: Session, days: int = None, this_month: bool = False, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, default_days=30)
    activities = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(models.CustomerActivityDetail.activity_date >= cutoff).group_by(
        models.CustomerActivityDetail.logged_by_user
    ).all()
    quotations = db.query(
        models.Quotation.customer_name, func.count(models.Quotation.quotation_id)
    ).filter(models.Quotation.transaction_date >= cutoff).group_by(models.Quotation.customer_name).all()
    return {
        "summary": f"Team performance summary over {period_label}.",
        "records": [
            {"metric": "Activities by employee", "detail": [{"employee": u, "count": c} for u, c in activities]},
            {"metric": "Quotations issued", "detail": len(quotations)},
        ],
        "source": "Based on Customer Activity Detail and Quotation records"
    }

def get_clients_contacted_yesterday(db: Session, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    yesterday = date.today() - timedelta(days=1)
    results = db.query(
        models.CustomerActivityDetail.customer_id
    ).filter(models.CustomerActivityDetail.activity_date == yesterday).distinct().all()
    customer_ids = [r[0] for r in results]
    customers = db.query(models.Customer).filter(models.Customer.customer_id.in_(customer_ids)).all() if customer_ids else []
    return {
        "summary": f"{len(customers)} client(s) contacted yesterday ({yesterday}).",
        "records": [{"customer_id": c.customer_id, "customer_name": c.customer_name} for c in customers],
        "source": "Based on Customer Activity Detail records"
    }

def get_calls_by_employee(db: Session, days: int = None, this_month: bool = False, status: str = None, time_of_day: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    # See get_calls_today for why this filters on activity_type rather than
    # the unreliable activity_scenario field.
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    query = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    results = query.group_by(models.CustomerActivityDetail.logged_by_user).order_by(
        func.count(models.CustomerActivityDetail.id).desc()
    ).all()
    return {
        "summary": f"Phone call activity by employee over {period_label}, most calls first.",
        "records": [{"employee": u, "call_count": c} for u, c in results],
        "source": "Based on Customer Activity Detail records (activity_type = 'Phone Call')"
    }

def get_calls_and_customers_by_employee(db: Session, days: int = None, this_month: bool = False, status: str = None, time_of_day: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    Combines call count and distinct-customer-reached count per employee in
    one grouped query. Neither get_calls_by_employee (calls only, no
    customer breakdown) nor get_clients_reached (distinct customers only,
    no employee breakdown) alone answers "calls vs distinct customers, per
    employee". Filters on activity_type == 'Phone Call', matching the same
    discriminator fix used everywhere else (see get_calls_today).
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    query = db.query(
        models.CustomerActivityDetail.logged_by_user,
        func.count(models.CustomerActivityDetail.id),
        func.count(func.distinct(models.CustomerActivityDetail.customer_id)),
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    results = query.group_by(models.CustomerActivityDetail.logged_by_user).order_by(
        func.count(models.CustomerActivityDetail.id).desc()
    ).all()
    return {
        "summary": f"Calls vs distinct customers called, by employee, over {period_label}.",
        "records": [
            {"employee": u, "call_count": c, "distinct_customers_called": d}
            for u, c, d in results
        ],
        "source": "Based on Customer Activity Detail records (activity_type = 'Phone Call'), grouped by logged_by_user"
    }

def get_sales_value_by_salesperson(db: Session, days: int = None, this_month: bool = False, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    results = db.query(
        models.Customer.account_manager_user, func.sum(models.SalesInvoice.invoice_value)
    ).join(
        models.SalesInvoice, models.SalesInvoice.customer_id == models.Customer.customer_id
    ).filter(
        models.SalesInvoice.invoice_date >= cutoff,
        models.SalesInvoice.invoice_date <= end
    ).group_by(models.Customer.account_manager_user).order_by(
        func.sum(models.SalesInvoice.invoice_value).desc()
    ).all()
    return {
        "summary": f"Total sales value by salesperson over {period_label}.",
        "records": [{"salesperson": u or "Unassigned", "total_value": float(v or 0)} for u, v in results],
        "source": "Based on Sales Invoice records, attributed via each customer's account manager"
    }

def get_monthly_recurring_revenue(db: Session, manufacturer: str = None, user_id: str = None, role: str = "admin"):
    """
    Total recurring monthly device revenue from Customer Monthly Devices --
    the ongoing per-month value of devices already deployed with each
    customer, independent of one-off Sales Order/Invoice activity booked
    in any particular window. This is a live snapshot of current
    recurring commitments, not new revenue booked in a period, so unlike
    most reports here it intentionally takes no start_date/end_date.
    """
    query = db.query(
        models.CustomerMonthlyDevice.manufacturer,
        func.sum(models.CustomerMonthlyDevice.monthly_value_usd),
        func.count(models.CustomerMonthlyDevice.id),
    )
    if role == "sales_user" and user_id:
        query = query.join(
            models.Customer, models.Customer.customer_id == models.CustomerMonthlyDevice.customer_id
        ).filter(models.Customer.account_manager_user == user_id)
    if manufacturer:
        query = query.filter(models.CustomerMonthlyDevice.manufacturer == manufacturer)
    results = query.group_by(models.CustomerMonthlyDevice.manufacturer).order_by(
        func.sum(models.CustomerMonthlyDevice.monthly_value_usd).desc()
    ).all()
    total = sum(float(v or 0) for _, v, _ in results)
    total_records = sum(c for _, _, c in results)
    return {
        "summary": f"${total:,.2f}/month in recurring device revenue across {total_records} device record(s).",
        "records": [{"manufacturer": m or "Unspecified", "monthly_value": round(float(v or 0), 2), "device_count": c} for m, v, c in results],
        "source": f"Based on {total_records} Customer Monthly Device records"
    }

def get_monthly_recurring_revenue_by_customer(db: Session, limit: int = 10, manufacturer: str = None, user_id: str = None, role: str = "admin"):
    """
    Top customers by recurring monthly device revenue (Customer Monthly
    Devices), joined to Customer for the display name. Companion to
    get_monthly_recurring_revenue (which breaks the same total down by
    manufacturer instead) -- together they show whether recurring revenue
    is concentrated in a few large accounts, a few manufacturers, or
    neither. Same live-snapshot caveat: no date range.
    """
    query = db.query(
        models.CustomerMonthlyDevice.customer_id,
        models.Customer.customer_name,
        func.sum(models.CustomerMonthlyDevice.monthly_value_usd),
        func.count(models.CustomerMonthlyDevice.id),
    ).join(
        models.Customer, models.Customer.customer_id == models.CustomerMonthlyDevice.customer_id
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    if manufacturer:
        query = query.filter(models.CustomerMonthlyDevice.manufacturer == manufacturer)
    results = query.group_by(
        models.CustomerMonthlyDevice.customer_id, models.Customer.customer_name
    ).order_by(func.sum(models.CustomerMonthlyDevice.monthly_value_usd).desc()).limit(limit).all()
    return {
        "summary": f"Top {len(results)} customer(s) by recurring monthly device revenue.",
        "records": [{"customer_id": cid, "customer_name": name, "monthly_value": round(float(v or 0), 2), "device_count": c} for cid, name, v, c in results],
        "source": f"Based on Customer Monthly Device records, top {limit} by monthly value"
    }

def get_typical_activity_hours_by_employee(db: Session, days: int = 30, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff = date.today() - timedelta(days=days - 1)  # N-day window including today -- see resolve_period's fix note
    results = db.query(
        models.CustomerActivityDetail.logged_by_user,
        func.min(models.CustomerActivityDetail.activity_time),
        func.max(models.CustomerActivityDetail.activity_time),
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_time.isnot(None)
    ).group_by(models.CustomerActivityDetail.logged_by_user).all()
    return {
        "summary": f"Earliest and latest logged activity time per employee, over the last {days} days.",
        "records": [{"employee": u, "earliest": str(mn), "latest": str(mx)} for u, mn, mx in results],
        "source": "Based on Customer Activity Detail records \u2014 reflects when activities were logged, not necessarily exact work hours"
    }


def get_employees_below_average(db: Session, recent_days: int = 7, baseline_days: int = 90, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    # N-day window including today -- see resolve_period's fix note. The
    # daily-average divisors below (baseline_days/recent_days) stay correct
    # unchanged, since the window length itself now genuinely matches the
    # labeled day count instead of being one day too wide.
    baseline_cutoff = date.today() - timedelta(days=baseline_days - 1)
    recent_cutoff = date.today() - timedelta(days=recent_days - 1)

    baseline = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(models.CustomerActivityDetail.activity_date >= baseline_cutoff).group_by(
        models.CustomerActivityDetail.logged_by_user
    ).all()
    baseline_rates = {u: c / baseline_days for u, c in baseline}

    recent = db.query(
        models.CustomerActivityDetail.logged_by_user, func.count(models.CustomerActivityDetail.id)
    ).filter(models.CustomerActivityDetail.activity_date >= recent_cutoff).group_by(
        models.CustomerActivityDetail.logged_by_user
    ).all()
    recent_rates = {u: c / recent_days for u, c in recent}

    below_average = [
        {"employee": u, "recent_daily_avg": round(recent_rates.get(u, 0), 2), "baseline_daily_avg": round(rate, 2)}
        for u, rate in baseline_rates.items()
        if recent_rates.get(u, 0) < rate
    ]
    return {
        "summary": f"{len(below_average)} employee(s) below their own normal daily activity average.",
        "records": below_average,
        "source": f"Recent window: last {recent_days} days. Baseline: last {baseline_days} days."
    }


def get_clients_without_followup(db: Session, followup_window_days: int = 7, user_id: str = None, role: str = "admin"):
    cutoff = date.today() - timedelta(days=followup_window_days - 1)  # N-day window including today -- see resolve_period's fix note

    # Latest logged activity of any type per customer
    last_activity_subq = db.query(
        models.CustomerActivityDetail.customer_id,
        func.max(models.CustomerActivityDetail.activity_date).label('last_activity_date')
    ).filter(models.CustomerActivityDetail.activity_date.isnot(None)).group_by(
        models.CustomerActivityDetail.customer_id
    ).subquery()

    # Latest call specifically per customer -- filters on activity_type
    # rather than activity_scenario; see get_calls_today for why.
    last_call_subq = db.query(
        models.CustomerActivityDetail.customer_id,
        func.max(models.CustomerActivityDetail.activity_date).label('last_call_date')
    ).filter(
        models.CustomerActivityDetail.activity_type == "Phone Call",
        models.CustomerActivityDetail.activity_date.isnot(None),
    ).group_by(models.CustomerActivityDetail.customer_id).subquery()

    # Customers whose most recent logged activity IS their last call (nothing since),
    # and that call happened more than followup_window_days ago.
    query = db.query(models.Customer, last_call_subq.c.last_call_date).join(
        last_call_subq, models.Customer.customer_id == last_call_subq.c.customer_id
    ).join(
        last_activity_subq, models.Customer.customer_id == last_activity_subq.c.customer_id
    ).filter(
        last_call_subq.c.last_call_date == last_activity_subq.c.last_activity_date,
        last_call_subq.c.last_call_date <= cutoff
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    results = query.all()

    return {
        "summary": f"{len(results)} client(s) whose last logged contact was a call, more than {followup_window_days} days ago, with no activity since.",
        "records": [{"customer_id": c.customer_id, "customer_name": c.customer_name, "last_call_date": str(d)} for c, d in results],
        "source": "Based on Customer Activity Detail records"
    }

def find_person_by_name(db: Session, name: str, user_id: str = None, role: str = "admin"):
    """
    Answers general "who is X" questions by checking both Employee and
    Customer records for a name match, since a name could refer to either
    an internal employee or a customer. Employee data stays admin-only,
    matching the same BLOCKED_FOR_SALES_USER precedent used for other
    employee-level functions (get_employee_daily_summary, etc.) -- a
    sales_user asking about a name only gets Customer-side matches, scoped
    to their own accounts like find_customer_by_name already does.
    """
    employee_matches = []
    if role != "sales_user":
        employees = db.query(models.Employee).filter(
            or_(
                models.Employee.employee_name.ilike(f"%{name}%"),
                models.Employee.user_id.ilike(f"%{name}%"),
            )
        ).limit(10).all()
        employee_matches = [
            {
                "type": "employee",
                "employee_id": e.employee_id,
                "employee_name": e.employee_name,
                # A missing user_id isn't necessarily "doesn't use the CRM" --
                # confirmed 2026-07-18 that some active CRM users (e.g.
                # aneez.ch@boxtech.ai) have real logged activity but no User
                # linked on their Employee HR record. State what we actually
                # know (no link) rather than guessing why.
                "email": e.user_id or "No User account linked on this Employee record",
                "department": e.department or "Not recorded",
            }
            for e in employees
        ]

    customer_query = db.query(models.Customer).filter(
        or_(
            models.Customer.customer_name.ilike(f"%{name}%"),
            models.Customer.email.ilike(f"%{name}%"),
        )
    )
    if role == "sales_user" and user_id:
        customer_query = customer_query.filter(models.Customer.account_manager_user == user_id)
    customers = customer_query.limit(10).all()
    customer_matches = [
        {
            "type": "customer",
            "customer_id": c.customer_id,
            "customer_name": c.customer_name,
            "country": c.country,
            "account_manager": c.account_manager_user,
            "phone": c.phone,
            "email": c.email,
        }
        for c in customers
    ]

    records = employee_matches + customer_matches
    if not records:
        note = " (employee records aren't searchable for this role)" if role == "sales_user" else ""
        return {
            "summary": f"No employee or customer found matching '{name}'{note}.",
            "records": [],
            "source": "Checked Employee and Customer records"
        }

    parts = []
    if employee_matches:
        parts.append(f"{len(employee_matches)} employee match(es)")
    if customer_matches:
        parts.append(f"{len(customer_matches)} customer match(es)")
    source = "Checked Employee and Customer records"
    if role == "sales_user":
        source += " (Employee lookup is admin-only; only Customer records scoped to your own accounts were checked)"
    return {
        "summary": f"Found {' and '.join(parts)} for '{name}'.",
        "records": records,
        "source": source
    }

def find_customer_by_name(db: Session, name: str, user_id: str = None, role: str = "admin"):
    query = db.query(models.Customer).filter(models.Customer.customer_name.ilike(f"%{name}%"))
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    customer = query.first()
    if not customer:
        return {"summary": f"No customer found matching '{name}'.", "records": [], "source": "Based on Customer records"}
    return {
        "summary": f"Found customer: {customer.customer_name}",
        "records": [{"customer_id": customer.customer_id, "customer_name": customer.customer_name}],
        "source": "Based on Customer records"
    }

def get_calls_today(db: Session, status: str = None, time_of_day: str = None, employee: str = None, user_id: str = None, role: str = "admin"):
    # Uses CustomerActivityDetail.activity_type == 'Phone Call' -- CallLog
    # (ERPNext's standard "Call Log" DocType) has zero rows ever synced, so
    # real call activity lives in Customer Activity Detail instead.
    today = date.today()
    query = db.query(models.CustomerActivityDetail).filter(
        models.CustomerActivityDetail.activity_date == today,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    if role == "sales_user" and user_id:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == user_id)
    calls = query.all()
    return {
        "summary": f"{len(calls)} call(s) logged today.",
        "records": [{"customer_id": c.customer_id, "scenario": c.activity_scenario} for c in calls],
        "source": f"Based on {len(calls)} Customer Activity Detail records (activity_type = 'Phone Call')"
    }

def get_daily_activity_pattern(db: Session, days: int = None, this_month: bool = False, activity_type: str = None, status: str = None, time_of_day: str = None, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    query = db.query(
        models.CustomerActivityDetail.activity_date, func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    )
    if activity_type:
        query = query.filter(models.CustomerActivityDetail.activity_type == activity_type)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    results = query.group_by(models.CustomerActivityDetail.activity_date).order_by(models.CustomerActivityDetail.activity_date).all()
    return {
        "summary": f"Daily activity pattern over {period_label}.",
        "records": [{"date": str(d), "count": c} for d, c in results],
        "source": f"Based on {sum(c for _, c in results)} Customer Activity Detail records"
    }


def get_busiest_call_day_of_week(db: Session, days: int = None, this_month: bool = False, status: str = None, time_of_day: str = None, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    # See get_calls_today for why this filters on activity_type rather than
    # the unreliable activity_scenario field.
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=90)
    query = db.query(
        extract('isodow', models.CustomerActivityDetail.activity_date).label("dow"),
        func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    results = query.group_by("dow").order_by(func.count(models.CustomerActivityDetail.id).desc()).all()
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
    return {
        "summary": f"Calls by day of week over {period_label}, busiest first.",
        "records": [{"day": day_names.get(int(d), "Unknown"), "count": c} for d, c in results],
        "source": f"Based on Customer Activity Detail records (activity_type = 'Phone Call') over {period_label}"
    }

def get_calls_by_customer(db: Session, days: int = None, this_month: bool = False, country: str = None, status: str = None, time_of_day: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    A calls-only counterpart to get_most_and_least_contacted_clients, which
    counts all activity types. Filters on activity_type == 'Phone Call' --
    verified against real data on 2026-07-15 that activity_scenario is
    populated for non-call types too (Presentation, Quotation, Meeting/Visit,
    etc.), so it does not reliably identify calls despite its ERPNext field
    name (phone_call_scenario).
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    query = db.query(
        models.CustomerActivityDetail.customer_id, func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_type == "Phone Call"
    )
    if country:
        query = query.join(models.Customer, models.Customer.customer_id == models.CustomerActivityDetail.customer_id).filter(models.Customer.country == country)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    results = query.group_by(
        models.CustomerActivityDetail.customer_id
    ).order_by(func.count(models.CustomerActivityDetail.id).desc()).all()
    return {
        "summary": f"Customers ranked by call count over {period_label}, most calls first.",
        "records": [{"customer_id": c, "call_count": n} for c, n in results],
        "source": "Based on Customer Activity Detail records (activity_type = 'Phone Call') \u2014 calls only, unlike get_most_and_least_contacted_clients which counts all activity types"
    }

def get_most_and_least_contacted_clients(db: Session, days: int = None, this_month: bool = False, country: str = None, status: str = None, time_of_day: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)
    query = db.query(
        models.CustomerActivityDetail.customer_id,
        func.count(models.CustomerActivityDetail.id),
        func.max(models.CustomerActivityDetail.activity_date)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end
    )
    if country:
        query = query.join(models.Customer, models.Customer.customer_id == models.CustomerActivityDetail.customer_id).filter(models.Customer.country == country)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    results = query.group_by(
        models.CustomerActivityDetail.customer_id
    ).order_by(func.count(models.CustomerActivityDetail.id).desc()).all()
    return {
        "summary": f"Clients ranked by contact frequency over {period_label}, most contacted first.",
        "records": [{"customer_id": c, "contact_count": n, "last_contact_date": str(d) if d else None} for c, n, d in results],
        "source": "Based on Customer Activity Detail records"
    }

def get_activities_today(db: Session, activity_type: str = None, status: str = None, time_of_day: str = None, employee: str = None, user_id: str = None, role: str = "admin"):
    today = date.today()
    query = db.query(models.CustomerActivityDetail).filter(models.CustomerActivityDetail.activity_date == today)
    if activity_type:
        query = query.filter(models.CustomerActivityDetail.activity_type == activity_type)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    if role == "sales_user" and user_id:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == user_id)
    count = query.count()
    return {
        "summary": f"{count} activity/activities logged today.",
        "records": [{"date": str(today), "activity_count": count}],
        "source": "Based on Customer Activity Detail records"
    }


def get_clients_contacted_today(db: Session, activity_type: str = None, status: str = None, time_of_day: str = None, employee: str = None, user_id: str = None, role: str = "admin"):
    today = date.today()
    query = db.query(func.distinct(models.CustomerActivityDetail.customer_id)).filter(
        models.CustomerActivityDetail.activity_date == today
    )
    if activity_type:
        query = query.filter(models.CustomerActivityDetail.activity_type == activity_type)
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    query = apply_time_of_day_filter(query, time_of_day, models.CustomerActivityDetail.activity_time)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    if role == "sales_user" and user_id:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == user_id)
    count = query.count()
    return {
        "summary": f"{count} distinct client(s) contacted today.",
        "records": [{"date": str(today), "clients_contacted": count}],
        "source": "Based on Customer Activity Detail records"
    }

def get_new_opportunities_this_month(db: Session, pipeline_stage: str = None, customer_id: str = None, user_id: str = None, role: str = "admin"):
    start_of_month = date.today().replace(day=1)
    query = db.query(models.Opportunity).filter(func.date(models.Opportunity.created_at) >= start_of_month)
    if pipeline_stage:
        query = query.filter(models.Opportunity.pipeline_stage == pipeline_stage)
    if customer_id:
        query = query.filter(models.Opportunity.customer_id == customer_id)
    if role == "sales_user" and user_id:
        query = query.filter(models.Opportunity.owner_user == user_id)
    opportunities = query.all()
    return {
        "summary": f"{len(opportunities)} new opportunity/opportunities created this month.",
        "records": [{"opportunity_id": o.opportunity_id, "customer_name": o.customer_name, "pipeline_stage": o.pipeline_stage} for o in opportunities],
        "source": f"Based on {len(opportunities)} Opportunity records"
    }

def get_busiest_hour_of_day(db: Session, days: int = 30, status: str = None, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    Uses Customer Activity Detail rather than Call Log, since real call
    data is confirmed to live there in practice (see get_phone_call_activity).
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    cutoff, end, _ = resolve_period(days, False, start_date, end_date, default_days=days or 30)
    query = db.query(
        extract('hour', models.CustomerActivityDetail.activity_time).label("hr"),
        func.count(models.CustomerActivityDetail.id)
    ).filter(
        models.CustomerActivityDetail.activity_date >= cutoff,
        models.CustomerActivityDetail.activity_date <= end,
        models.CustomerActivityDetail.activity_time.isnot(None)
    )
    if status:
        query = query.filter(models.CustomerActivityDetail.status == status)
    if employee:
        query = query.filter(models.CustomerActivityDetail.logged_by_user == employee)
    results = query.group_by("hr").order_by(func.count(models.CustomerActivityDetail.id).desc()).all()
    return {
        "summary": f"Busiest working hours over the last {days} days, based on logged activity.",
        "records": [{"hour": int(h), "count": c} for h, c in results],
        "source": "Based on Customer Activity Detail records"
    }


def get_sales_orders_created(db: Session, within_days: int = None, this_month: bool = False, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    cutoff, end, period_label = resolve_period(within_days, this_month, start_date, end_date, default_days=30)
    query = db.query(models.SalesOrder).filter(
        models.SalesOrder.order_date >= cutoff,
        models.SalesOrder.order_date <= end
    )
    if role == "sales_user" and user_id:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == user_id)
    elif employee:
        query = query.join(models.Customer).filter(models.Customer.account_manager_user == employee)
    orders = query.all()
    total = sum(float(o.order_value or 0) for o in orders)
    return {
        "summary": f"{len(orders)} sales order(s) created over {period_label}, totaling ${total:,.2f}.",
        "records": [{"sales_order_id": o.sales_order_id, "customer_name": o.customer_name, "order_date": str(o.order_date), "value": float(o.order_value or 0)} for o in orders],
        "source": f"Based on {len(orders)} Sales Order records"
    }

def get_overdue_todos(db: Session, user_id: str = None, role: str = "admin"):
    # 'Open' is the only real in-progress status in this data (confirmed:
    # Open=12, Cancelled=45, Closed=1 -- Cancelled is NOT outstanding work,
    # so filtering on status == 'Open' rather than status != 'Closed' is
    # the correct overdue definition here.
    query = db.query(models.Todo).filter(
        models.Todo.due_date < date.today(),
        models.Todo.status == "Open"
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Todo.assigned_to_user == user_id)
    todos = query.all()
    return {
        "summary": f"{len(todos)} overdue follow-up(s)/to-do item(s), past their due date and still open.",
        "records": [{"todo_id": t.todo_id, "description": t.description, "due_date": str(t.due_date), "assigned_to": t.assigned_to_user} for t in todos],
        "source": f"Based on {len(todos)} Todo records"
    }

def get_todos_by_status(db: Session, status: str = None, employee: str = None, user_id: str = None, role: str = "admin"):
    """
    General-purpose counterpart to get_overdue_todos, driven by the
    Follow-up Status filter. Accepts any real status (Open/Closed/Cancelled)
    or the virtual "Overdue" value (Open AND past due_date). Confirmed real
    status values on 2026-07-16: Cancelled=45, Open=12, Closed=1 -- a small
    dataset overall, so exact counts will be small regardless of status.
    """
    query = db.query(models.Todo)
    if status == "Overdue":
        query = query.filter(models.Todo.status == "Open", models.Todo.due_date < date.today())
    elif status:
        query = query.filter(models.Todo.status == status)
    if role == "sales_user" and user_id:
        query = query.filter(models.Todo.assigned_to_user == user_id)
    elif employee:
        query = query.filter(models.Todo.assigned_to_user == employee)
    todos = query.all()
    status_desc = status or "all"
    return {
        "summary": f"{len(todos)} follow-up(s)/to-do item(s) with status '{status_desc}'.",
        "records": [{"todo_id": t.todo_id, "description": t.description, "status": t.status, "due_date": str(t.due_date) if t.due_date else None, "assigned_to": t.assigned_to_user} for t in todos],
        "source": f"Based on {len(todos)} Todo records"
    }
def get_overdue_tasks(db: Session, user_id: str = None, role: str = "admin"):
    # Task has no assignee field at all in this schema (only
    # completed_by_user, populated only after completion), so it can't
    # be scoped to "my" tasks -- this is company-wide by necessity,
    # blocked for sales_user like the other team/company-wide reports.
    # Note: as of this writing, Task has 0 rows synced -- this DocType
    # does not appear to be in active use in this ERPNext instance.
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER
    tasks = db.query(models.Task).filter(
        models.Task.expected_end < date.today(),
        models.Task.status != "Completed"
    ).all()
    return {
        "summary": f"{len(tasks)} overdue task(s), past their expected end date and not completed.",
        "records": [{"task_id": t.task_id, "subject": t.subject, "expected_end": str(t.expected_end), "status": t.status} for t in tasks],
        "source": f"Based on {len(tasks)} Task records"
    }


def get_customer_list(db: Session, user_id: str = None, role: str = "admin"):
    # Lightweight option list for the dashboard's Customer/Region filter
    # dropdowns -- not exposed as an AI chat tool, just UI plumbing.
    # Also doubles as the customer_id -> name/value lookup the frontend
    # joins against several activity-count lists (Customer Activity
    # Detail only stores customer_id, not a name or value), so
    # total_monthly_devices_usd rides along here rather than requiring
    # a second fetch.
    query = db.query(
        models.Customer.customer_id, models.Customer.customer_name, models.Customer.country,
        models.Customer.total_monthly_devices_usd,
    )
    if role == "sales_user" and user_id:
        query = query.filter(models.Customer.account_manager_user == user_id)
    customers = query.order_by(models.Customer.customer_name).all()
    return {
        "summary": f"{len(customers)} customer(s) available.",
        "records": [
            {"customer_id": c[0], "customer_name": c[1], "country": c[2], "monthly_recurring_value_usd": float(c[3] or 0)}
            for c in customers
        ],
        "source": f"Based on {len(customers)} Customer records"
    }


def get_activity_type_options(db: Session, user_id: str = None, role: str = "admin"):
    # Distinct category labels only -- no customer-identifying data --
    # so this is safe as reference data for both roles.
    results = db.query(models.CustomerActivityDetail.activity_type).filter(
        models.CustomerActivityDetail.activity_type.isnot(None)
    ).distinct().order_by(models.CustomerActivityDetail.activity_type).all()
    return {
        "summary": f"{len(results)} activity type(s) available.",
        "records": [{"activity_type": r[0]} for r in results],
        "source": "Based on Customer Activity Detail records"
    }


def _activity_log_slot_fields(activity_date, activity_time):
    """Shape date/time into the frontend ActivityRecord slot fields.

    Missing time is returned as null (not invented). hourSlot/halfHourSlot
    stay null so the UI can treat them as 'no time component'.
    """
    date_s = activity_date.isoformat() if activity_date is not None else None
    if activity_time is None:
        return date_s, None, None, None
    hour = activity_time.hour
    minute = activity_time.minute
    time_s = f"{hour:02d}:{minute:02d}"
    half = f"{hour:02d}:{'30' if minute >= 30 else '00'}"
    return date_s, time_s, hour, half


def _activity_log_row(record_id, activity_date, activity_time, salesperson, country, activity_type, client, amount, is_financial):
    date_s, time_s, hour, half = _activity_log_slot_fields(activity_date, activity_time)
    return {
        "id": record_id,
        "date": date_s,
        "time": time_s,
        "hourSlot": hour,
        "halfHourSlot": half,
        "salesperson": salesperson or None,
        "country": country or None,
        "activityType": activity_type,
        "client": client or None,
        "amount": round(float(amount or 0), 2),
        "isFinancial": bool(is_financial),
    }


def _activity_log_keep(row, activity_type=None, country=None, employee=None, start=None, end=None):
    if activity_type and row["activityType"] != activity_type:
        return False
    if country and (row["country"] or "") != country:
        return False
    if employee and (row["salesperson"] or "") != employee:
        return False
    if start or end:
        if not row["date"]:
            return False
        if start and row["date"] < start:
            return False
        if end and row["date"] > end:
            return False
    return True


def get_activity_log_records(db: Session, activity_type: str = None, country: str = None, employee: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """Unified activity stream for the Activity Analysis page.

    Not a database view — UNION of existing synced tables, shaped to the
    frontend ActivityRecord contract. See BoxTech_Reporting_DB_Schema.md §3.
    Null salesperson/country/client are returned as null where the source
    table has no such column (not fabricated).
    """
    if role == "sales_user" and user_id and not employee:
        employee = user_id

    records = []

    cad_rows = db.query(models.CustomerActivityDetail, models.Customer).outerjoin(
        models.Customer, models.CustomerActivityDetail.customer_id == models.Customer.customer_id
    ).filter(
        models.CustomerActivityDetail.activity_date.isnot(None),
        models.CustomerActivityDetail.activity_type.isnot(None),
    ).all()
    for cad, cust in cad_rows:
        records.append(_activity_log_row(
            f"CAD-{cad.id}",
            cad.activity_date,
            cad.activity_time,
            cad.logged_by_user,
            cust.country if cust else None,
            cad.activity_type,
            (cust.customer_name if cust else None) or cad.customer_id,
            0,
            False,
        ))

    opp_rows = db.query(models.Opportunity, models.Customer).outerjoin(
        models.Customer, models.Opportunity.customer_id == models.Customer.customer_id
    ).all()
    for opp, cust in opp_rows:
        records.append(_activity_log_row(
            f"OPP-{opp.opportunity_id}",
            opp.opportunity_date,
            None,
            opp.owner_user,
            cust.country if cust else None,
            "Sales Opportunity",
            (cust.customer_name if cust else None) or opp.customer_name,
            opp.total_value_usd,
            True,
        ))

    quo_rows = db.query(models.Quotation, models.Opportunity, models.Customer).outerjoin(
        models.Opportunity, models.Quotation.opportunity_id == models.Opportunity.opportunity_id
    ).outerjoin(
        models.Customer, models.Opportunity.customer_id == models.Customer.customer_id
    ).all()
    for quo, opp, cust in quo_rows:
        records.append(_activity_log_row(
            f"QUO-{quo.quotation_id}",
            quo.transaction_date,
            None,
            opp.owner_user if opp else None,
            cust.country if cust else None,
            "Quotation",
            (cust.customer_name if cust else None) or quo.customer_name,
            quo.grand_total,
            True,
        ))

    so_rows = db.query(models.SalesOrder, models.Customer).outerjoin(
        models.Customer, models.SalesOrder.customer_id == models.Customer.customer_id
    ).all()
    for so, cust in so_rows:
        records.append(_activity_log_row(
            f"SO-{so.sales_order_id}",
            so.order_date,
            None,
            None,
            cust.country if cust else None,
            "Sales Order",
            (cust.customer_name if cust else None) or so.customer_name,
            so.order_value,
            True,
        ))

    si_rows = db.query(models.SalesInvoice, models.Customer).outerjoin(
        models.Customer, models.SalesInvoice.customer_id == models.Customer.customer_id
    ).all()
    for si, cust in si_rows:
        records.append(_activity_log_row(
            f"SI-{si.invoice_id}",
            si.invoice_date,
            None,
            None,
            cust.country if cust else None,
            "Sales Invoice",
            (cust.customer_name if cust else None) or si.customer_name,
            si.invoice_value,
            True,
        ))

    for task in db.query(models.Task).all():
        task_date = task.expected_end.date() if task.expected_end else (task.created_at.date() if task.created_at else None)
        records.append(_activity_log_row(
            f"TASK-{task.task_id}",
            task_date,
            None,
            task.completed_by_user,
            None,
            "Task",
            None,
            0,
            False,
        ))

    for todo in db.query(models.Todo).all():
        records.append(_activity_log_row(
            f"TODO-{todo.todo_id}",
            todo.due_date,
            None,
            todo.assigned_to_user,
            None,
            "ToDo",
            None,
            0,
            False,
        ))

    for lead in db.query(models.Lead).all():
        records.append(_activity_log_row(
            f"LEAD-{lead.lead_id}",
            lead.lead_date,
            None,
            lead.owner_user,
            lead.country,
            "Lead",
            lead.client_name,
            lead.total_value,
            True,
        ))

    filtered = [
        row for row in records
        if _activity_log_keep(row, activity_type, country, employee, start_date, end_date)
    ]
    filtered.sort(key=lambda r: (r["date"] or "", r["time"] or "", r["id"]))

    return {
        "summary": f"{len(filtered)} activity log record(s).",
        "records": filtered,
        "source": (
            "UNION of customer_activity_details, opportunities, quotations, "
            "sales_orders, sales_invoices, tasks, todos, and leads"
        ),
    }

def get_department_options(db: Session, user_id: str = None, role: str = "admin"):
    """
    Every real department that exists in ERPNext, regardless of whether it
    currently has any CRM activity to report -- deliberately NOT derived
    from get_activity_by_team, which only surfaces departments with logged
    activity (almost always Sales-only, since other departments' staff
    don't use the CRM at all per Hassan). This lets the Team dropdown show
    the full org structure and honestly report 0 for an inactive team,
    rather than silently omitting it as if it didn't exist.
    """
    results = db.query(models.Department.department_label).filter(
        models.Department.department_label.isnot(None),
        models.Department.department_label.notin_(["All Departments"])
    ).distinct().all()
    labels = sorted({clean_department_label(r[0]) for r in results if r[0]})
    return {
        "summary": f"{len(labels)} department(s) available.",
        "records": [{"department": d} for d in labels],
        "source": "Based on Department records"
    }

def get_employee_headcount(db: Session, department: str = None, user_id: str = None, role: str = "admin"):
    """
    Plain roster headcount from ERPNext's Employee doctype -- how many
    employees exist in a department, independent of whether they've
    logged any CRM activity. Deliberately NOT derived from
    get_activity_by_team, which inner-joins to Customer Activity Detail
    and so only counts employees active in the selected window --
    that undercounts headcount and can't answer a plain "how many
    people are in Sales" question at all.

    Returns an empty result set until Employee/Department read access
    is granted in ERPNext and a sync has run (see the Tier 1b block in
    sync_config.py) -- that's expected, not a bug, in the meantime.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER

    department_raw_values = None
    if department:
        all_depts = [d[0] for d in db.query(models.Employee.department).distinct().all() if d[0]]
        department_raw_values = [d for d in all_depts if clean_department_label(d) == department]

    query = db.query(models.Employee.department, func.count(models.Employee.employee_id))
    if department:
        query = query.filter(models.Employee.department.in_(department_raw_values))
    rows = query.group_by(models.Employee.department).all()

    counts = {}
    for raw_dept, count in rows:
        label = clean_department_label(raw_dept) or "Unassigned"
        counts[label] = counts.get(label, 0) + count

    records = [{"department": label, "employee_count": count} for label, count in sorted(counts.items(), key=lambda r: -r[1])]
    total = sum(counts.values())

    if department:
        dept_count = counts.get(department, 0)
        summary = (f"{dept_count} employee(s) in {department}." if records
                   else f"No employee records found for {department} yet — Employee/Department sync may still be pending ERPNext read access.")
    else:
        summary = (f"{total} employee(s) across {len(records)} department(s)." if records
                   else "No employee records available yet — Employee/Department sync may still be pending ERPNext read access.")

    return {
        "summary": summary,
        "records": records,
        "source": "Based on Employee records (headcount, independent of CRM activity)"
    }

def get_recently_added_employees(db: Session, days: int = None, this_month: bool = False, department: str = None, start_date: str = None, end_date: str = None, user_id: str = None, role: str = "admin"):
    """
    Employees whose ERPNext Employee record was CREATED within the given
    window, via Employee.created_at (mapped from ERPNext's own system
    "creation" field -- see the Employee entry in sync_config.py).
    Answers "have any new employees been added" directly, rather than
    inferring it from activity/login data, which only shows usage, not
    roster changes.

    created_at is a real historical ERPNext timestamp, so this is
    accurate immediately after the column is backfilled by the next
    sync -- not just for employees added going forward.

    Returns an empty result set until Employee/Department read access
    is granted in ERPNext and a sync has run.
    """
    if role == "sales_user":
        return BLOCKED_FOR_SALES_USER

    cutoff, end, period_label = resolve_period(days, this_month, start_date, end_date, default_days=30)

    query = db.query(models.Employee).filter(
        func.date(models.Employee.created_at) >= cutoff,
        func.date(models.Employee.created_at) <= end
    )

    if department:
        all_depts = [d[0] for d in db.query(models.Employee.department).distinct().all() if d[0]]
        department_raw_values = [d for d in all_depts if clean_department_label(d) == department]
        query = query.filter(models.Employee.department.in_(department_raw_values))

    rows = query.order_by(models.Employee.created_at.desc()).all()

    records = [{
        "employee_id": e.employee_id,
        "employee_name": e.employee_name,
        "department": clean_department_label(e.department) or "Unassigned",
        "created_at": str(e.created_at) if e.created_at else None,
    } for e in rows]

    summary = (f"{len(records)} new employee(s) added over {period_label}." if records
               else f"No new employee records over {period_label}.")

    return {
        "summary": summary,
        "records": records,
        "source": "Based on Employee.created_at (ERPNext's record creation timestamp)"
    }

def get_lead_status_options(db: Session, user_id: str = None, role: str = "admin"):
    results = db.query(models.Lead.status).filter(models.Lead.status.isnot(None)).distinct().order_by(models.Lead.status).all()
    return {
        "summary": f"{len(results)} lead status option(s) available.",
        "records": [{"status": r[0]} for r in results],
        "source": "Based on Leads records"
    }


def get_opportunity_stage_options(db: Session, user_id: str = None, role: str = "admin"):
    results = db.query(models.Opportunity.pipeline_stage).filter(
        models.Opportunity.pipeline_stage.isnot(None)
    ).distinct().order_by(models.Opportunity.pipeline_stage).all()
    return {
        "summary": f"{len(results)} pipeline stage option(s) available.",
        "records": [{"pipeline_stage": r[0]} for r in results],
        "source": "Based on Opportunity records"
    }


def get_enabled_users(db: Session, user_id: str = None, role: str = "admin"):
    """
    Live ERPNext User names (emails) where enabled = 1.
    Used by the Activity Analysis Salesperson dropdown only.
    Does not read or modify reporting activity tables.
    """
    try:
        records = erpnext_client.get_records(
            "User",
            filters=[["enabled", "=", 1]],
            fields=["name"],
        )
        names = sorted({(r.get("name") or "").strip() for r in records if r.get("name")})
        return {
            "summary": f"{len(names)} enabled user(s) available.",
            "records": [{"salesperson": name} for name in names],
            "source": "Based on ERPNext User records (enabled = 1)",
        }
    except Exception:
        return {
            "summary": "Could not load enabled users from ERPNext.",
            "records": [],
            "source": "ERPNext User API unavailable",
        }


SAFE_FUNCTIONS = {
    "get_last_sync_time": get_last_sync_time,
    "get_calls_today": get_calls_today,
    "find_person_by_name": find_person_by_name,
    "get_calls_by_salesperson_this_week": get_calls_by_salesperson_this_week,
    "get_stale_customers": get_stale_customers,
    "get_total_sales_value": get_total_sales_value,
    "get_opportunities_by_stage": get_opportunities_by_stage,
    "get_opportunities_in_stage": get_opportunities_in_stage,
    "get_opportunity_close_forecast": get_opportunity_close_forecast,
    "get_new_leads_this_month": get_new_leads_this_month,
    "get_customers_with_pending_payments": get_customers_with_pending_payments,
    "get_invoice_aging": get_invoice_aging,
    "get_sales_invoices_between_dates": get_sales_invoices_between_dates,
    "get_activities_for_customer": get_activities_for_customer,
    "get_activities_by_time_slot": get_activities_by_time_slot,
    "get_activities_by_period": get_activities_by_period,
    "get_daily_activity_pattern": get_daily_activity_pattern,
    "get_busiest_call_day_of_week": get_busiest_call_day_of_week,
    "compare_weekly_activity": compare_weekly_activity,
    "compare_monthly_activity": compare_monthly_activity,
    "get_high_value_low_engagement_customers": get_high_value_low_engagement_customers,
    "get_activities_by_employee": get_activities_by_employee,
    "get_opportunity_to_quotation_conversion": get_opportunity_to_quotation_conversion,
    "get_quotation_status_breakdown": get_quotation_status_breakdown,
    "get_sample_testing_funnel": get_sample_testing_funnel,
    "get_call_to_sales_ratio": get_call_to_sales_ratio,
    "get_lead_to_opportunity_conversion": get_lead_to_opportunity_conversion,
    "get_customers_by_country": get_customers_by_country,
    "get_clients_reached": get_clients_reached,
    "get_meeting_count": get_meeting_count,
    "get_quotations_sent": get_quotations_sent,
    "get_phone_call_activity": get_phone_call_activity,
    "get_most_and_least_contacted_clients": get_most_and_least_contacted_clients,
    "get_calls_by_customer": get_calls_by_customer,
    "get_login_times_by_employee": get_login_times_by_employee,
    "get_employee_daily_summary": get_employee_daily_summary,
    "get_activity_by_team": get_activity_by_team,
    "get_employee_activity_window": get_employee_activity_window,
    "get_team_performance_summary": get_team_performance_summary,
    "get_calls_by_employee": get_calls_by_employee,
    "get_clients_contacted_yesterday": get_clients_contacted_yesterday,
    "get_sales_value_by_salesperson": get_sales_value_by_salesperson,
    "get_monthly_recurring_revenue": get_monthly_recurring_revenue,
    "get_monthly_recurring_revenue_by_customer": get_monthly_recurring_revenue_by_customer,
    "get_typical_activity_hours_by_employee": get_typical_activity_hours_by_employee,
    "get_busiest_hour_of_day": get_busiest_hour_of_day,
    "get_employees_below_average": get_employees_below_average,
    "get_clients_without_followup": get_clients_without_followup,
    "find_customer_by_name": find_customer_by_name,
    "get_activities_today": get_activities_today,
    "get_clients_contacted_today": get_clients_contacted_today,
    "get_new_opportunities_this_month": get_new_opportunities_this_month,
    "get_sales_orders_created": get_sales_orders_created,
    "get_overdue_todos": get_overdue_todos,
    "get_todos_by_status": get_todos_by_status,
    "get_overdue_tasks": get_overdue_tasks,
    "get_customer_list": get_customer_list,
    "get_activity_type_options": get_activity_type_options,
    "get_activity_log_records": get_activity_log_records,
    "get_department_options": get_department_options,
    "get_employee_headcount": get_employee_headcount,
    "get_lead_status_options": get_lead_status_options,
    "get_opportunity_stage_options": get_opportunity_stage_options,
    "get_calls_and_customers_by_employee": get_calls_and_customers_by_employee,
    "get_recently_added_employees": get_recently_added_employees,
    "get_enabled_users": get_enabled_users,
}

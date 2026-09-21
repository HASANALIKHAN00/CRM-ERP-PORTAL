"""
Deterministic fictional dataset for Portfolio Demo Mode.

Rather than shadowing every reporting endpoint with a hand-written fake
response, this seeds the real SQLAlchemy models into the in-memory SQLite
database that database.py builds when DEMO_MODE is on. Every existing
query function in query_functions.py then runs its real aggregation over
this data, so dashboard cards, tables, charts, filters, date ranges and
totals stay consistent with each other for free -- there is only one set
of numbers, and it is the one the real code computes.

Everything here is invented: companies, people, amounts and dates. No
ERPNext, customer or credential data is present or reachable.
"""

import random
from datetime import date, datetime, time, timedelta

import models
from database import Base, SessionLocal, engine
from demo_config import DEMO_USERS

# Fixed seed: the same dataset is produced on every start, so screenshots,
# totals and percentages are reproducible.
SEED = 20260921

ACTIVITY_COUNT = 240
OPPORTUNITY_COUNT = 45
LEAD_COUNT = 28
QUOTATION_COUNT = 35
SALES_ORDER_COUNT = 32
INVOICE_COUNT = 60
TODO_COUNT = 26
TASK_COUNT = 12
SAMPLE_TESTING_COUNT = 22
HISTORY_DAYS = 180
ATTENDANCE_DAYS = 30
LOGIN_HISTORY_DAYS = 14

DEPARTMENTS = [
    "Sales - BT",
    "Customer Success - BT",
    "Business Development - BT",
    "Technical Support - BT",
]

# (company, country) -- 40 fictional clients across 10 markets.
CLIENTS = [
    ("Falcon Freight Logistics", "United Arab Emirates"),
    ("Cedar Ridge Transport", "Jordan"),
    ("Blue Harbour Shipping", "Oman"),
    ("Nova Fleet Solutions", "Saudi Arabia"),
    ("Amber Sands Trading", "Qatar"),
    ("Silk Route Carriers", "Pakistan"),
    ("Vertex Mobility Group", "Turkey"),
    ("Golden Dune Rentals", "Kuwait"),
    ("Pioneer Cold Chain", "Egypt"),
    ("Crescent Line Haulage", "Bahrain"),
    ("Orbit Cargo Systems", "United Arab Emirates"),
    ("Northwind Distribution", "Saudi Arabia"),
    ("Sapphire Coast Marine", "Oman"),
    ("Ironwood Equipment Co", "Pakistan"),
    ("Zenith Rail Services", "Turkey"),
    ("Meridian Bus Lines", "Egypt"),
    ("Apex Courier Network", "United Arab Emirates"),
    ("Palm Valley Agritech", "Jordan"),
    ("Quantum Field Services", "Saudi Arabia"),
    ("Lighthouse Utilities", "Qatar"),
    ("Granite Peak Mining", "Oman"),
    ("Skyline Construction Group", "Kuwait"),
    ("Emerald Bay Tourism", "Bahrain"),
    ("Titan Heavy Movers", "Pakistan"),
    ("Copperline Energy", "Turkey"),
    ("Horizon Waste Management", "Egypt"),
    ("Delta Stream Beverages", "Saudi Arabia"),
    ("Redstone Aggregates", "United Arab Emirates"),
    ("Clearwater Facilities", "Qatar"),
    ("Summit Ridge Pharma", "Jordan"),
    ("Atlas Chain Retail", "Turkey"),
    ("Beacon Security Services", "Oman"),
    ("Wildflower Foods", "Egypt"),
    ("Ironclad Armoured Transit", "Kuwait"),
    ("Seabreeze Port Services", "Bahrain"),
    ("Cobalt Industrial Supply", "Pakistan"),
    ("Highland Dairy Co-op", "Saudi Arabia"),
    ("Stellar Ride Share", "United Arab Emirates"),
    ("Juniper Health Logistics", "Qatar"),
    ("Ironbridge Contracting", "Turkey"),
]

COMPANY_ACTIVITIES = [
    "Fleet Management", "Logistics & Distribution", "Cold Chain", "Passenger Transport",
    "Construction", "Field Services", "Rental & Leasing", "Industrial",
]
EMPLOYEE_BANDS = ["11-50", "51-200", "201-500", "501-1000", "1000+"]
CLIENT_PROGRESS = ["Active", "Onboarding", "Pilot", "Dormant"]
TARGET_MARKETS = ["Enterprise", "SMB", "Government"]
CUSTOMER_GROUPS = ["Commercial", "Enterprise", "Government", "Reseller"]

# Invented hardware brands -- no real vendor is named anywhere in this file.
MANUFACTURERS = ["Veltrix", "Quantek", "Corvex", "Ruplex", "Meridia", "Halcyon"]
DEVICE_MODELS = {
    "Veltrix": ["VX-300", "VX-500 Pro", "VX-720 Rugged"],
    "Quantek": ["QT-120", "QT-240 Lite", "QT-880"],
    "Corvex": ["CV-90", "CV-410", "CV-610 Marine"],
    "Ruplex": ["RX-55", "RX-180", "RX-260 Cold"],
    "Meridia": ["MD-1000", "MD-1400", "MD-2200 Asset"],
    "Halcyon": ["HL-20", "HL-70 Dash", "HL-150"],
}

# Weighted so Phone Call dominates, matching how the reports lean on it.
ACTIVITY_TYPES = [
    ("Phone Call", 34),
    ("WhatsApp", 14),
    ("Meeting/ Visit", 11),
    ("Online Meeting", 9),
    ("Email", 9),
    ("Text Message", 6),
    ("Presentation", 5),
    ("Quotation / Commercial Offer", 5),
    ("Samples Sales", 3),
    ("LinkedIn", 2),
    ("Pilot Order", 1),
    ("Development", 1),
]

# Exactly the three values the dashboard's Call Result filter offers.
ACTIVITY_STATUSES = [("\u2705Complete", 62), ("\u23f3In Progress", 27), ("Rejected", 11)]

CONTACT_ROLES = [
    "Fleet Manager", "Operations Director", "Procurement Lead", "IT Manager",
    "Managing Director", "Workshop Supervisor", "Finance Controller",
]
ACTIVITY_RESULTS = [
    "Shared updated pricing sheet and agreed to reconnect next week.",
    "Walked through the live tracking dashboard; positive feedback.",
    "Discussed installation scheduling for the next device batch.",
    "Requested a revised commercial offer with volume discounts.",
    "Reviewed open support tickets; all resolved on the call.",
    "Client asked for a technical comparison against their current unit.",
    "Confirmed pilot results and moved to contract discussion.",
    "No answer; left a voicemail and followed up by message.",
    "Budget approval delayed to the next quarter.",
    "Agreed to a sample shipment of 10 units for evaluation.",
    "Collected fleet expansion plans for the coming year.",
    "Escalated a billing query to the finance team.",
]
ACTIVITY_SCENARIOS = [
    "Follow-up", "New Requirement", "Support Issue", "Renewal",
    "Pricing Discussion", "Onboarding", "Escalation",
]

PIPELINE_STAGES = [
    "Prospecting", "Qualification", "Needs Analysis", "Proposal Sent",
    "Negotiation", "Pilot / Trial", "Closed Won", "Closed Lost",
]
OPPORTUNITY_STATUSES = [("Open", 55), ("Quotation", 20), ("Converted", 12), ("Lost", 8), ("Closed", 5)]
LEAD_STATUSES = ["Lead", "Open", "Replied", "Interested", "Quotation", "Converted", "Do Not Contact"]
QUOTATION_STATUSES = [("Draft", 18), ("Open", 34), ("Ordered", 28), ("Expired", 12), ("Cancelled", 8)]
SAMPLE_STAGES = [
    "Initial Contact & Key Contact Identified",
    "Device Proposed & Sample Requested",
    "Testing Approved & Sample Delivered",
    "Technical Setup & Installation",
    "Testing & Issue Resolution",
    "Testing Completed & Feedback Shared",
]
TODO_SUBJECTS = [
    "Send revised quotation", "Schedule installation visit", "Chase signed purchase order",
    "Share technical datasheet", "Confirm shipment tracking details", "Collect pilot feedback",
    "Renew annual service contract", "Arrange driver training session",
    "Follow up on outstanding invoice", "Prepare account review deck",
]
TASK_SUBJECTS = [
    "Firmware rollout for Q4 fleet batch", "Quarterly territory pipeline review",
    "Update device configuration templates", "Warehouse stock reconciliation",
    "Customer onboarding pack refresh", "Partner enablement workshop",
]

_seed_counts: dict[str, int] = {}
_seeded = False


def _weighted(rng: random.Random, weighted_pairs):
    values = [value for value, _ in weighted_pairs]
    weights = [weight for _, weight in weighted_pairs]
    return rng.choices(values, weights=weights, k=1)[0]


def _activity_offsets(rng: random.Random) -> list[int]:
    """Day offsets for every activity, weighted towards the recent past.

    Today and yesterday get a guaranteed share so the "Today" cards and
    the 7-day presets are never empty, whatever the seed produces.
    """
    offsets = [0] * 6 + [1] * 8
    pool = list(range(2, HISTORY_DAYS))
    weights = [1 + (HISTORY_DAYS - offset) / 35 for offset in pool]
    offsets += rng.choices(pool, weights=weights, k=ACTIVITY_COUNT - len(offsets))
    return offsets


def _activity_time(rng: random.Random) -> time:
    # Working hours dominate, with a thin evening tail so the Morning /
    # Afternoon / Evening / Night filter has something in every bucket.
    hour = _weighted(rng, [
        (8, 6), (9, 12), (10, 16), (11, 15), (12, 8), (13, 7),
        (14, 13), (15, 14), (16, 12), (17, 8), (18, 5), (19, 3), (21, 2),
    ])
    return time(hour, rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]))


def build_dataset(today: date | None = None) -> list:
    """Build every demo row as unsaved model instances, in insert order."""
    today = today or date.today()
    rng = random.Random(SEED)
    rows = []

    now = datetime.combine(today, time(9, 0))
    crm_users = [u for u in DEMO_USERS if u["department"] != "Technical Support - BT"]

    # ---------- Org structure ----------
    rows.append(models.Department(
        department_name="All Departments", department_label="All Departments",
        parent_department=None, company="BoxTech Demo",
    ))
    for department in DEPARTMENTS:
        rows.append(models.Department(
            department_name=department, department_label=department,
            parent_department="All Departments", company="BoxTech Demo",
        ))

    for index, user in enumerate(DEMO_USERS):
        # Two recent joiners so "recently added employees" isn't empty.
        days_ago = rng.randint(4, 26) if index >= len(DEMO_USERS) - 2 else rng.randint(240, 1400)
        rows.append(models.Employee(
            employee_id=user["employee_id"], employee_name=user["full_name"],
            user_id=user["email"], department=user["department"],
            created_at=datetime.combine(today - timedelta(days=days_ago), time(10, 30)),
        ))

    # ---------- Customers and their recurring device revenue ----------
    customers = []
    for index, (name, country) in enumerate(CLIENTS, start=1):
        customer_id = f"CUST-{index:05d}"
        manager = crm_users[index % len(crm_users)]["email"]
        devices = []
        for manufacturer in rng.sample(MANUFACTURERS, rng.randint(1, 3)):
            quantity = rng.randint(15, 420)
            unit_price = round(rng.uniform(1.6, 7.4), 2)
            devices.append((manufacturer, rng.choice(DEVICE_MODELS[manufacturer]), quantity, unit_price))

        device_count = sum(d[2] for d in devices)
        # The customer-level total is derived from the child rows, so the
        # MRR chart and the customer table can never disagree.
        monthly_value = round(sum(d[2] * d[3] for d in devices), 2)
        created = datetime.combine(today - timedelta(days=rng.randint(120, 1500)), time(11, 0))

        customer = models.Customer(
            customer_id=customer_id, customer_name=name,
            customer_group=rng.choice(CUSTOMER_GROUPS), territory=country,
            account_manager_user=manager,
            phone=f"+971-4-{rng.randint(200, 899)}-{rng.randint(1000, 9999)}",
            email=f"contact@{name.lower().replace(' ', '').replace('-', '')[:18]}.example",
            is_disabled=index in (17, 34),
            company_activity=rng.choice(COMPANY_ACTIVITIES),
            employee_count_band=rng.choice(EMPLOYEE_BANDS), country=country,
            device_count=device_count,
            install_volume_monthly=rng.choice(["1-25", "26-50", "51-100", "100+"]),
            total_monthly_devices=device_count, total_monthly_devices_usd=monthly_value,
            gps_installs_monthly=rng.randint(2, 60),
            technician_count_general=rng.randint(1, 18), gps_technician_count=rng.randint(1, 7),
            client_progress=rng.choice(CLIENT_PROGRESS), target_market=rng.choice(TARGET_MARKETS),
            is_assigned=True, assigned_on=created.date(),
            created_at=created, updated_at=now,
        )
        customers.append(customer)
        rows.append(customer)

        for manufacturer, model_name, quantity, unit_price in devices:
            rows.append(models.CustomerMonthlyDevice(
                customer_id=customer_id, erpnext_name=f"CMD-{customer_id}-{manufacturer}",
                manufacturer=manufacturer, model=model_name, monthly_qty=quantity,
                unit_price_usd=unit_price, monthly_value_usd=round(quantity * unit_price, 2),
            ))

    active_customers = [c for c in customers if not c.is_disabled]

    # ---------- Customer activity: the spine of the reporting data ----------
    for index, offset in enumerate(sorted(_activity_offsets(rng), reverse=True), start=1):
        activity_date = today - timedelta(days=offset)
        customer = rng.choice(active_customers)
        # Guarantee a few calls logged today for the "Calls today" card.
        activity_type = "Phone Call" if offset == 0 and index > ACTIVITY_COUNT - 3 else _weighted(rng, ACTIVITY_TYPES)
        rows.append(models.CustomerActivityDetail(
            customer_id=customer.customer_id, erpnext_name=f"CAD-DEMO-{index:05d}",
            logged_by_user=rng.choice(crm_users)["email"],
            activity_date=activity_date, activity_time=_activity_time(rng),
            point_of_contact_role=rng.choice(CONTACT_ROLES),
            activity_type=activity_type, activity_scenario=rng.choice(ACTIVITY_SCENARIOS),
            result=rng.choice(ACTIVITY_RESULTS), status=_weighted(rng, ACTIVITY_STATUSES),
            scenario_other_detail=None,
        ))

    # ---------- Pipeline ----------
    opportunities = []
    for index in range(1, OPPORTUNITY_COUNT + 1):
        customer = rng.choice(active_customers)
        # A third are dated inside the current calendar month so the
        # "new this month" reports have real content.
        opened = today - timedelta(days=rng.randint(0, today.day - 1) if index % 3 == 0
                                   else rng.randint(0, HISTORY_DAYS))
        manufacturer = rng.choice(MANUFACTURERS)
        quantity = rng.randint(20, 900)
        unit_price = round(rng.uniform(22.0, 96.0), 2)
        # Spread across overdue / 30 / 90 / later so the close-forecast
        # chart shows every bucket, with a couple left undated.
        close_offset = rng.choice([-52, -21, -6, 9, 18, 27, 44, 68, 85, 120, 160])
        opportunity = models.Opportunity(
            opportunity_id=f"OPTY-{index:05d}", customer_id=customer.customer_id,
            customer_name=customer.customer_name, status=_weighted(rng, OPPORTUNITY_STATUSES),
            opportunity_from="Customer", owner_user=rng.choice(crm_users)["email"],
            opportunity_amount=round(quantity * unit_price, 2),
            expected_closing_date=None if index % 17 == 0 else today + timedelta(days=close_offset),
            opportunity_date=opened, opportunity_custom_date=opened,
            pipeline_stage=rng.choice(PIPELINE_STAGES),
            stage_comments=rng.choice(ACTIVITY_RESULTS),
            device_manufacturer=manufacturer, product_category=rng.choice(["Hardware", "Hardware + SIM", "Software"]),
            client_requirement_notes="Fleet-wide tracking rollout with driver behaviour reporting.",
            proposed_solution=f"{manufacturer} {rng.choice(DEVICE_MODELS[manufacturer])} with platform integration.",
            device_qty=quantity, device_model=rng.choice(DEVICE_MODELS[manufacturer]),
            unit_price_usd=unit_price, total_value_usd=round(quantity * unit_price, 2),
            lost_reason="Lost on price against an incumbent supplier." if index % 11 == 0 else None,
            created_at=datetime.combine(opened, time(10, 15)), updated_at=now,
        )
        opportunities.append(opportunity)
        rows.append(opportunity)

    for index in range(1, LEAD_COUNT + 1):
        name, country = rng.choice(CLIENTS)
        created = today - timedelta(days=rng.randint(0, today.day - 1) if index % 3 == 0
                                    else rng.randint(0, HISTORY_DAYS))
        value = round(rng.uniform(3200, 88000), 2)
        rows.append(models.Lead(
            lead_id=f"CRM-LEAD-{index:05d}", client_name=f"{name} ({country})", country=country,
            lead_date=created, owner_user=rng.choice(crm_users)["email"],
            expected_closing_date=created + timedelta(days=rng.randint(20, 120)),
            probability=rng.choice([10, 20, 35, 50, 65, 80]),
            status=rng.choice(LEAD_STATUSES),
            stage_comments="Inbound enquiry from the regional trade expo.",
            manufacturer=rng.choice(MANUFACTURERS), category=rng.choice(["Hardware", "Software", "Bundle"]),
            client_requirement_notes="Evaluating a tracking rollout across a mixed fleet.",
            solution="Pilot batch followed by a phased installation plan.",
            quantity=str(rng.randint(10, 400)), total_value=value, base_total_value=value,
            created_at=datetime.combine(created, time(9, 45)), updated_at=now,
        ))

    for index in range(1, QUOTATION_COUNT + 1):
        opportunity = rng.choice(opportunities)
        transaction_date = today - timedelta(days=rng.randint(0, HISTORY_DAYS))
        rows.append(models.Quotation(
            quotation_id=f"SAL-QTN-{index:05d}", customer_name=opportunity.customer_name,
            quotation_to="Customer", transaction_date=transaction_date,
            status=_weighted(rng, QUOTATION_STATUSES),
            grand_total=round(float(opportunity.total_value_usd) * rng.uniform(0.82, 1.14), 2),
            # Only some quotations carry the opportunity link, which is what
            # the conversion report's "traceably linked" caveat describes.
            opportunity_id=opportunity.opportunity_id if index % 5 != 0 else None,
            created_at=datetime.combine(transaction_date, time(12, 5)), updated_at=now,
        ))

    # ---------- Orders, invoices and collections ----------
    for index in range(1, SALES_ORDER_COUNT + 1):
        customer = rng.choice(active_customers)
        # Half sit inside the last 30 days so the call-to-sales correlation
        # and "orders created" card have overlapping windows to work with.
        order_date = today - timedelta(days=rng.randint(0, 29) if index % 2 == 0
                                       else rng.randint(30, HISTORY_DAYS))
        rows.append(models.SalesOrder(
            sales_order_id=f"SAL-ORD-{index:05d}", customer_id=customer.customer_id,
            customer_name=customer.customer_name, order_date=order_date,
            delivery_date=order_date + timedelta(days=rng.randint(7, 45)),
            status=rng.choice(["To Deliver and Bill", "To Bill", "Completed", "Closed"]),
            delivery_status=rng.choice(["Not Delivered", "Partly Delivered", "Fully Delivered"]),
            billing_status=rng.choice(["Not Billed", "Partly Billed", "Fully Billed"]),
            order_value=round(rng.uniform(4200, 145000), 2), currency="USD",
            created_at=datetime.combine(order_date, time(14, 20)), updated_at=now,
        ))

    for index in range(1, INVOICE_COUNT + 1):
        customer = rng.choice(active_customers)
        invoice_date = today - timedelta(days=rng.randint(0, 25) if index % 2 == 0
                                         else rng.randint(26, HISTORY_DAYS))
        value = round(rng.uniform(2600, 128000), 2)
        # Paid / partly paid / fully outstanding, so the aging buckets and
        # the pending-payments total are both real sums of these rows.
        share = rng.choice([0.0, 0.0, 0.0, 0.35, 0.6, 1.0, 1.0])
        outstanding = round(value * share, 2)
        rows.append(models.SalesInvoice(
            invoice_id=f"ACC-SINV-{index:05d}", customer_id=customer.customer_id,
            customer_name=customer.customer_name, invoice_date=invoice_date,
            due_date=invoice_date + timedelta(days=30),
            status="Paid" if outstanding == 0 else ("Overdue" if invoice_date + timedelta(days=30) < today else "Unpaid"),
            invoice_value=value, outstanding_amount=outstanding, is_credit_note=False,
            created_at=datetime.combine(invoice_date, time(16, 40)), updated_at=now,
        ))

    # ---------- Follow-ups ----------
    for index in range(1, TODO_COUNT + 1):
        customer = rng.choice(active_customers)
        # Every third item is open and already past due, which is exactly
        # what the Overdue follow-up filter looks for.
        overdue = index % 3 == 0
        due = today - timedelta(days=rng.randint(2, 40)) if overdue else today + timedelta(days=rng.randint(0, 21))
        rows.append(models.Todo(
            todo_id=f"TODO-{index:05d}",
            description=f"{rng.choice(TODO_SUBJECTS)} \u2014 {customer.customer_name}",
            status="Open" if overdue else rng.choice(["Open", "Closed", "Cancelled"]),
            priority=rng.choice(["Low", "Medium", "High"]), due_date=due,
            assigned_to_user=rng.choice(crm_users)["email"],
            linked_doctype="Customer", linked_record_id=customer.customer_id,
            created_at=datetime.combine(due - timedelta(days=14), time(9, 30)), updated_at=now,
        ))

    for index in range(1, TASK_COUNT + 1):
        start = today - timedelta(days=rng.randint(5, 70))
        end = start + timedelta(days=rng.randint(3, 30))
        completed = end < today and index % 3 != 0
        rows.append(models.Task(
            task_id=f"TASK-{index:05d}", subject=rng.choice(TASK_SUBJECTS),
            status="Completed" if completed else rng.choice(["Open", "Working", "Pending Review"]),
            priority=rng.choice(["Low", "Medium", "High"]),
            expected_start=datetime.combine(start, time(9, 0)),
            expected_end=datetime.combine(end, time(17, 0)),
            completed_by_user=rng.choice(crm_users)["email"] if completed else None,
            completed_on=end if completed else None,
            created_at=datetime.combine(start, time(8, 30)), updated_at=now,
        ))

    for index, customer in enumerate(rng.sample(active_customers, SAMPLE_TESTING_COUNT), start=1):
        rows.append(models.CustomerSampleTesting(
            customer_id=customer.customer_id, erpnext_name=f"CST-{index:05d}",
            test_date=today - timedelta(days=rng.randint(5, 150)),
            test_stage=rng.choice(SAMPLE_STAGES),
            notes="Evaluation unit shipped with a pre-configured tracking profile.",
        ))

    # ---------- HR attendance, used by the performance reports ----------
    attendance_index = 0
    for day_offset in range(ATTENDANCE_DAYS):
        day = today - timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        for user in DEMO_USERS:
            attendance_index += 1
            status = _weighted(rng, [("Present", 88), ("On Leave", 6), ("Half Day", 4), ("Absent", 2)])
            in_time = datetime.combine(day, time(rng.choice([8, 8, 9, 9, 9]), rng.choice([5, 15, 25, 35, 45, 55])))
            hours = 0.0 if status == "Absent" else (round(rng.uniform(3.5, 4.5), 2) if status == "Half Day"
                                                    else round(rng.uniform(7.6, 9.4), 2))
            out_time = in_time + timedelta(hours=hours)
            rows.append(models.Attendance(
                attendance_id=f"HR-ATT-{attendance_index:05d}", employee_id=user["employee_id"],
                employee_name=user["full_name"], attendance_date=day, status=status,
                working_hours=hours, in_time=in_time, out_time=out_time,
                department=user["department"],
            ))
            if status == "Absent":
                continue
            rows.append(models.EmployeeCheckin(
                checkin_id=f"HR-CHK-{attendance_index:05d}-IN", employee_id=user["employee_id"],
                log_type="IN", time=in_time,
                shift_start=datetime.combine(day, time(9, 0)), shift_end=datetime.combine(day, time(18, 0)),
            ))
            rows.append(models.EmployeeCheckin(
                checkin_id=f"HR-CHK-{attendance_index:05d}-OUT", employee_id=user["employee_id"],
                log_type="OUT", time=out_time,
                shift_start=datetime.combine(day, time(9, 0)), shift_end=datetime.combine(day, time(18, 0)),
            ))

    # ---------- Reporting-tool sign-ins and sync history ----------
    for day_offset in range(LOGIN_HISTORY_DAYS):
        day = today - timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        for user in crm_users:
            rows.append(models.ActivityLogEntry(
                user_id=user["email"], operation="Login",
                subject=f"{user['full_name']} signed in to the reporting agent",
                logged_at=datetime.combine(day, time(rng.choice([8, 9, 9, 10]), rng.choice([2, 12, 27, 41, 58]))),
            ))

    for run_index in range(6):
        started = datetime.combine(today - timedelta(days=run_index), time(2, 0)) + timedelta(minutes=run_index)
        processed = rng.randint(1800, 2600)
        inserted = rng.randint(30, 180)
        updated = rng.randint(200, 600)
        rows.append(models.SyncRun(
            started_at=started, completed_at=started + timedelta(minutes=rng.randint(3, 11)),
            backup_file_name=f"boxtech_demo_{(today - timedelta(days=run_index)).isoformat()}.sql",
            backup_file_size_bytes=rng.randint(4_000_000, 9_000_000), result="success",
            records_processed=processed, records_inserted=inserted, records_updated=updated,
            records_skipped=processed - inserted - updated, records_rejected=0,
            retry_count=0, error_summary=None,
        ))

    for day_offset in range(1, 13):
        day = today - timedelta(days=day_offset)
        rows.append(models.DailySummary(
            summary_date=day,
            content=(
                f"**Daily summary \u2014 {day.isoformat()}**\n\n"
                f"The team logged customer activity across the region, with follow-ups "
                f"concentrated in fleet and logistics accounts. Pipeline movement was steady, "
                f"and collections stayed on track against the open invoice book.\n\n"
                f"_Demo environment: this summary describes fictional data._"
            ),
            metrics={"generated_by": "demo", "summary_date": day.isoformat()},
            email_sent=False,
        ))

    return rows


def seed(force: bool = False) -> dict:
    """Create the demo schema and populate it. Safe to call more than once."""
    global _seeded, _seed_counts
    if _seeded and not force:
        return _seed_counts

    Base.metadata.create_all(bind=engine)
    rows = build_dataset()

    session = SessionLocal()
    try:
        session.add_all(rows)
        session.commit()
    finally:
        session.close()

    counts: dict[str, int] = {}
    for row in rows:
        counts[type(row).__name__] = counts.get(type(row).__name__, 0) + 1
    _seed_counts = dict(sorted(counts.items()))
    _seeded = True
    return _seed_counts


def get_enabled_users(db, user_id: str = None, role: str = "admin") -> dict:
    """Demo stand-in for the one query function that calls ERPNext directly."""
    names = sorted(u["email"] for u in DEMO_USERS)
    return {
        "summary": f"{len(names)} enabled user(s) available.",
        "records": [{"salesperson": name} for name in names],
        "source": "Demo environment \u2014 fictional user directory",
    }


# Query functions that cannot run off the seeded database because they read
# an external system. Everything else in SAFE_FUNCTIONS is used unchanged.
SAFE_FUNCTION_OVERRIDES = {
    "get_enabled_users": get_enabled_users,
}

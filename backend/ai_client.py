import os
import json
import inspect
from openai import OpenAI
from sqlalchemy.orm import Session
import query_functions
from datetime import datetime, timezone
import models
from database import SessionLocal
import time

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-5.5"

# How many prior conversation turns (user+assistant messages, not pairs) to
# include for context. Capped to avoid unbounded token growth on long chats —
# only recent turns matter for resolving references like "this month" or
# "what about June".
MAX_HISTORY_MESSAGES = 12

# Explicit tool schema for every safe function — this list, not the
# model, is the actual safety boundary. The model can only ever select
# from and parameterize these; it never generates its own query.
TOOLS = [
    {"type": "function", "function": {
        "name": "get_calls_today", "description": "Count and list calls logged today.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "Call result status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_calls_by_salesperson_this_week", "description": "Calls grouped by salesperson over the last 7 days.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_stale_customers", "description": "Customers with no logged activity in a time window, ranked by recurring monthly device value (highest revenue at risk first).",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_total_sales_value", "description": "Total sales invoice value within a time window.",
        "parameters": {"type": "object", "properties": {
            "within_days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "find_person_by_name", "description": "Looks up a person by name across BOTH Employee and Customer records and returns whatever is found. Use this for general 'who is X' questions. Employee-side matches are admin-only (a sales_user asking about a name only gets Customer-side matches, scoped to their own accounts). For resolving a specific customer_id before calling a function that requires one, use find_customer_by_name instead.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "The person's name as mentioned by the user, full or partial."}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "get_opportunities_by_stage", "description": "Opportunity count and total value grouped by pipeline stage.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_new_leads_this_month", "description": "New leads created this calendar month.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "Lead status to filter by, using the exact value as stated by the user or discovered via another tool result \u2014 do not guess a value. Omit for all statuses."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_customers_with_pending_payments", "description": "Invoices with an outstanding (unpaid) amount.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_invoice_aging", "description": "Outstanding (unpaid) invoice balances grouped into aging buckets: not yet due, 1-30/31-60/60+ days overdue.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_sales_invoices_between_dates", "description": "Sales invoices within a date range. Omit start_date and/or end_date to mean 'no lower/upper bound' \u2014 e.g. for 'every sale ever' or 'all sales up to now', omit both/omit start_date rather than guessing a date.",
        "parameters": {"type": "object", "properties": {
            "start_date": {"type": "string", "description": "Start date, format YYYY-MM-DD. Omit if there's no real lower bound (e.g. 'all sales ever')."},
            "end_date": {"type": "string", "description": "End date, format YYYY-MM-DD. Omit if there's no real upper bound."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_activities_for_customer", "description": "All logged activity records for one specific customer.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "string", "description": "The customer's ID"}
        }, "required": ["customer_id"]}
    }},
    {"type": "function", "function": {
        "name": "get_daily_activity_pattern", "description": "Daily count of logged activities within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."},
            "activity_type": {"type": "string", "description": "Activity type to filter by, e.g. 'Phone Call', 'Meeting/Visit', 'Presentation', 'Quotation'. Omit for all types."},
            "status": {"type": "string", "description": "Status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_busiest_call_day_of_week", "description": "Which day of the week has the most calls, within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."},
            "status": {"type": "string", "description": "Call result status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "compare_weekly_activity", "description": "Compares this week's logged activity count to last week's.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_high_value_low_engagement_customers", "description": "Customers with high combined value (historical sales plus annualized recurring device revenue) but no recent activity.",
        "parameters": {"type": "object", "properties": {
            "engagement_days": {"type": "integer", "description": "Rolling window in days for the inactivity check. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."},
            "min_value": {"type": "number", "description": "Minimum total sales value, default 1000"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_activities_by_employee", "description": "Activities logged per employee, most active first, within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_opportunity_to_quotation_conversion", "description": "How many opportunities have a traceably-linked quotation.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_quotation_status_breakdown", "description": "Quotation value and count grouped by status (Draft, Open, Ordered, Expired, Cancelled), in funnel order. Shows how much quotation value is stuck at each stage rather than just whether a quotation exists.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_sample_testing_funnel", "description": "Customer Sample Testing records grouped by test stage, in funnel order. Shows where hardware evaluations stall before a sale, earlier in the pipeline than Opportunity stages.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_customers_by_country", "description": "Customer count grouped by country.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_clients_reached", "description": "Number of distinct clients contacted within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_meeting_count", "description": "Number of meetings logged within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_quotations_sent", "description": "Quotations sent to customers within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_phone_call_activity", "description": "Count of phone call activity logged within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_most_and_least_contacted_clients", "description": "Clients ranked by how often they were contacted within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_login_times_by_employee", "description": "Employee login events within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_team_performance_summary", "description": "Team performance summary (activities and quotations) within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_calls_by_employee", "description": "Phone call activity by employee within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."},
            "status": {"type": "string", "description": "Call result status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_clients_contacted_yesterday", "description": "Clients contacted yesterday.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_sales_value_by_salesperson", "description": "Total sales value grouped by salesperson within a time window.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_monthly_recurring_revenue", "description": "Total recurring monthly device revenue (Customer Monthly Devices), grouped by manufacturer. A live snapshot of current recurring commitments, not new revenue booked in a window \u2014 takes no date range.",
        "parameters": {"type": "object", "properties": {
            "manufacturer": {"type": "string", "description": "Manufacturer to filter by, using the exact value as stated by the user or discovered via another tool result. Omit for all manufacturers."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_monthly_recurring_revenue_by_customer", "description": "Top customers by recurring monthly device revenue (Customer Monthly Devices). Companion to get_monthly_recurring_revenue, broken down by customer instead of manufacturer. A live snapshot \u2014 takes no date range.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Number of top customers to return, default 10."},
            "manufacturer": {"type": "string", "description": "Manufacturer to filter by, using the exact value as stated by the user or discovered via another tool result. Omit for all manufacturers."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_typical_activity_hours_by_employee", "description": "Earliest and latest activity time logged per employee.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Number of days to look back, default 30"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_busiest_hour_of_day", "description": "Busiest working hours of the day, based on logged activity.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Number of days to look back, default 30"},
            "status": {"type": "string", "description": "Status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_employees_below_average", "description": "Employees whose recent activity rate is below their own historical daily average.",
        "parameters": {"type": "object", "properties": {
            "recent_days": {"type": "integer", "description": "Recent window in days, default 7"},
            "baseline_days": {"type": "integer", "description": "Historical baseline window in days, default 90"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_clients_without_followup", "description": "Clients who were called but received no follow-up activity within a window afterward.",
        "parameters": {"type": "object", "properties": {
            "followup_window_days": {"type": "integer", "description": "Days allowed for a follow-up to count, default 7"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "find_customer_by_name", "description": "Look up a customer's exact ID from a partial or approximate name, needed before calling functions that require a customer_id.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "The customer name as mentioned by the user"}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "get_activities_today", "description": "Count of activities logged today.",
        "parameters": {"type": "object", "properties": {
            "activity_type": {"type": "string", "description": "Activity type to filter by, e.g. 'Phone Call', 'Meeting/Visit', 'Presentation', 'Quotation'. Omit for all types."},
            "status": {"type": "string", "description": "Status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_clients_contacted_today", "description": "Count of distinct clients contacted today.",
        "parameters": {"type": "object", "properties": {
            "activity_type": {"type": "string", "description": "Activity type to filter by, e.g. 'Phone Call', 'Meeting/Visit', 'Presentation', 'Quotation'. Omit for all types."},
            "status": {"type": "string", "description": "Status: '\u2705Complete', '\u23f3In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."},
            "employee": {"type": "string", "description": "Employee email to filter by. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_new_opportunities_this_month", "description": "New opportunities created this calendar month.",
        "parameters": {"type": "object", "properties": {
            "pipeline_stage": {"type": "string", "description": "Pipeline stage to filter by, e.g. 'Qualification', 'Proposal', 'Negotiation'. Omit for all stages."},
            "customer_id": {"type": "string", "description": "Exact customer ID to filter by \u2014 use find_customer_by_name first to resolve a name to an ID. Omit for all customers."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_sales_orders_created", "description": "Sales orders created within a time window.",
        "parameters": {"type": "object", "properties": {
            "within_days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' \u2014 uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_overdue_todos", "description": "Overdue follow-up/to-do items that are still open past their due date.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_overdue_tasks", "description": "Overdue tasks past their expected end date and not completed. Company-wide only.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_opportunities_in_stage", "description": "Lists individual opportunities currently in a specific pipeline stage, ranked by value — the drill-down detail behind get_opportunities_by_stage's distribution count. Includes each deal's expected closing date and how many days remain until (or past) it. Use this when the user wants to know *which deals* are in a stage, not just the count.",
        "parameters": {"type": "object", "properties": {
            "stage": {"type": "string", "description": "Pipeline stage name to filter by, e.g. 'Qualification', 'Proposal', 'Negotiation'. Omit to list across all stages."},
            "employee": {"type": "string", "description": "Salesperson email to filter by owner. Omit for all owners."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_opportunity_close_forecast", "description": "Open opportunities grouped by proximity to their expected closing date (closing within 30/90 days, overdue, no date set). The aggregate forecast view, complementing get_opportunities_in_stage's per-deal detail.",
        "parameters": {"type": "object", "properties": {
            "employee": {"type": "string", "description": "Salesperson email to filter by owner. Omit for all owners."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "compare_monthly_activity", "description": "Compares this month's activity (to date) against last month's using daily averages, since raw totals aren't fair when this month is still in progress. Company-wide only.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_call_to_sales_ratio", "description": "Customer-level correlation between being called and getting a new Sales Order in the same window. This is a correlation, not a causal record-level link — there's no field connecting a specific call to the order it may have led to. Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "employee": {"type": "string", "description": "Salesperson email to filter calls by. Omit for all salespeople."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_lead_to_opportunity_conversion", "description": "New leads vs new opportunities this calendar month. IMPORTANT: there is no traceable link between Lead and Opportunity records in the synced schema, so this always reports two independent counts with an explicit caveat — never state or imply a conversion percentage from this data. Company-wide only.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_calls_by_customer", "description": "Customers ranked by phone-call count only (unlike get_most_and_least_contacted_clients, which counts all activity types). Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "country": {"type": "string", "description": "Filter to customers in this country. Omit for all countries."},
            "status": {"type": "string", "description": "Call result status: '✅Complete', '⏳In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_employee_daily_summary", "description": "Per-employee, per-day first/last checkin time and working hours/attendance status, from ERPNext HR data (Employee Checkin + Attendance). Returns an empty result if HR sync data isn't populated for the window — that's expected, not an error; mention it plainly rather than treating it as a failure. Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "employee": {"type": "string", "description": "Employee email to filter to one person. Omit for all employees."},
            "department": {"type": "string", "description": "Team/department name to filter by. Omit for all departments."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_activity_by_team", "description": "Logged CRM activity counts grouped by team/department (via Employee.department), with a per-employee breakdown (activity count and attributed sales value) inside each team and a trend vs. the prior equal-length period. Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_employee_headcount", "description": "Plain roster headcount of employees per department from ERPNext's Employee doctype — use this for 'how many employees/people are in <team>' or total headcount questions. This is NOT activity-based: it counts everyone on the roster regardless of whether they've logged CRM activity, unlike get_activity_by_team. Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "department": {"type": "string", "description": "Team/department name to count, e.g. 'Sales'. Omit to get counts for every department."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_employee_activity_window", "description": "Per-employee, per-day first/last logged CRM activity time and activity count — a CRM-native alternative to get_employee_daily_summary that doesn't depend on ERPNext HR/Attendance data being populated. Company-wide only.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "employee": {"type": "string", "description": "Employee email to filter to one person. Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_todos_by_status", "description": "Follow-up/to-do items filtered by status. Accepts real statuses ('Open', 'Closed', 'Cancelled') or the virtual value 'Overdue' (Open and past due_date). For a sales_user, automatically scoped to their own assigned items.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "One of 'Open', 'Closed', 'Cancelled', or 'Overdue'. Omit for all statuses."},
            "employee": {"type": "string", "description": "Employee email to filter by assignee (admin only — ignored/overridden for sales_user, who always sees only their own). Omit for all employees."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_calls_and_customers_by_employee", "description": "Per-employee breakdown showing BOTH call count and distinct customers called in the same window. Use this specifically when the user wants calls vs distinct customers together (e.g. 'calls vs number of customers per account manager') — get_calls_by_employee alone only has the call count, not the customer count.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "status": {"type": "string", "description": "Call result status: '✅Complete', '⏳In Progress', or 'Rejected'. Omit for all statuses."},
            "time_of_day": {"type": "string", "description": "One of 'Morning', 'Afternoon', 'Evening', 'Night'. Omit for all times."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_activity_type_options", "description": "Lists the real activity type values that exist in the data (e.g. 'Phone Call', 'Meeting/Visit', 'Presentation', 'Quotation'). Call this first if you're unsure of the exact activity_type value to pass to another tool, rather than guessing.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_lead_status_options", "description": "Lists the real Lead status values that exist in the data. Call this first if you're unsure of the exact status value to pass to get_new_leads_this_month, rather than guessing.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_opportunity_stage_options", "description": "Lists the real pipeline stage values that exist in the data. Call this first if you're unsure of the exact stage value to pass to get_opportunities_in_stage or get_new_opportunities_this_month, rather than guessing.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_recently_added_employees", "description": "Employees whose ERPNext record was created within a window — use this for 'have any new employees been added/entered' or 'who joined recently' questions. Based on the record's real creation date, not activity/login data, so it directly answers roster-change questions instead of inferring them from usage.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Rolling window in days. Do not use for calendar-month questions."},
            "this_month": {"type": "boolean", "description": "Set true for 'this month' — uses the real calendar-month boundary instead of a rolling day count."},
            "department": {"type": "string", "description": "Team/department name to filter by. Omit for all departments."}
        }, "required": []}
    }},
]

SYSTEM_PROMPT = (
    "You are BoxTech's reporting assistant. You can only retrieve data by "
    "calling one of the provided tools \u2014 never invent or guess a number "
    "that didn't come from a real tool result.\n\n"
    "Once you have real data from a tool call (from this turn, or from earlier "
    "in this same conversation), you are encouraged to perform arithmetic on it "
    "directly \u2014 sums, averages, percentages, differences between two "
    "periods, and similar calculations \u2014 and explain your answer using the "
    "real figures involved. If a question needs data you don't already have in "
    "the conversation, call the appropriate tool(s) first, including multiple "
    "tool calls if comparing periods (e.g. 'compare June and July' needs two "
    "calls, one per month) before computing a combined answer.\n\n"
    "Use the conversation history to resolve references like 'this month', "
    "'that customer', or 'what about June' based on what was already discussed "
    "earlier in the conversation \u2014 don't ask the user to repeat context "
    "they already gave.\n\n"
    "When asked for your take, opinion, or analysis, feel free to give one \u2014 "
    "as long as it's grounded in the real data you've retrieved (e.g. noting "
    "concentration in a few large customers, or a trend across periods). Base "
    "any observation strictly on the actual numbers in front of you, not on "
    "general assumptions.\n\n"
    "When you give a total or summary figure, briefly state what it's based "
    "on (e.g. the date range or record count) so the basis is clear.\n\n"
    "The raw records from your tool call are shown to the user separately, "
    "directly from the data, immediately below your reply \u2014 you do not "
    "need to reproduce them as your own table. For results with more than "
    "a few rows, give a short prose summary and any genuine insight (e.g. "
    "notable outliers, concentration, or a trend) instead of re-listing "
    "every row yourself; the exact data is already visible to the user. "
    "If you do reference a specific value \u2014 a number, an email, a "
    "record ID \u2014 copy it exactly as it appears in the tool result "
    "rather than retyping it from memory, since re-typing long values by "
    "hand is unreliable even when careful.\n\n"
    "If no tool fits the question at all, say so rather than answering from "
    "general knowledge."
)

def ask_ai(question: str, db: Session, user_id: str = None, role: str = "admin", history: list = None, max_steps: int = 6) -> dict:
    request_start = time.perf_counter()
    gpt_time_total = 0.0
    tool_time_total = 0.0
    tool_call_count = 0

    def _log_timing(path_label: str):
        # Visible via `docker logs boxtech-reporting-backend` -- total
        # request time, broken down into time spent waiting on GPT vs. time
        # spent running our own DB queries, so a slow response can be
        # attributed to the right side rather than guessed at.
        total = time.perf_counter() - request_start
        print(
            f"[ai_client] '{question[:60]}' -> {path_label} | "
            f"total={total:.2f}s gpt={gpt_time_total:.2f}s "
            f"tools={tool_time_total:.2f}s ({tool_call_count} call(s))"
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for turn in history[-MAX_HISTORY_MESSAGES:]:
            turn_role = turn.get("role")
            content = turn.get("content")
            if turn_role in ("user", "assistant") and content:
                messages.append({"role": turn_role, "content": content})

    messages.append({"role": "user", "content": question})

    last_result = None
    # Every tool call made while answering, in order -- last_result alone
    # only kept the MOST RECENT call, so a multi-source question (e.g.
    # "compare June and July", which needs two calls) silently lost the
    # first call's records by the time this function returned. This list
    # is what a multi-source export actually reads from.
    tool_call_history = []

    for step in range(max_steps):
        gpt_start = time.perf_counter()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        gpt_time_total += time.perf_counter() - gpt_start
        message = response.choices[0].message

        if not message.tool_calls:
            if last_result and message.content:
                # Model synthesized/computed an answer using real tool data
                # from this conversation — use its actual text, but keep the
                # underlying records/source from the last real tool call for
                # transparency rather than discarding them.
                result = {
                    "summary": message.content,
                    "records": last_result.get("records", []),
                    "source": last_result.get("source", ""),
                    "function_called": last_result.get("function_called"),
                    "arguments_used": last_result.get("arguments_used"),
                    "sources": tool_call_history,
                }
                log_audit_entry(
                    action="ai_question",
                    detail=question,
                    generated_query=f"{result.get('function_called')}({result.get('arguments_used')}) + synthesis",
                    user_id=user_id or "unauthenticated"
                )
                _log_timing("synthesis")
                return result
            if last_result:
                last_result["sources"] = tool_call_history
                log_audit_entry(
                    action="ai_question",
                    detail=question,
                    generated_query=f"{last_result.get('function_called')}({last_result.get('arguments_used')})",
                    user_id=user_id or "unauthenticated"
                )
                _log_timing("tool_result_no_synthesis")
                return last_result
            log_audit_entry(action="ai_question", detail=question, generated_query="no function selected", user_id=user_id or "unauthenticated")
            _log_timing("no_function_selected")
            return {
                "summary": message.content or "I don't have a report configured for that question yet.",
                "records": [],
                "source": "No matching safe function was selected",
                "sources": tool_call_history,
            }

        tool_call = message.tool_calls[0]
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")

        fn = query_functions.SAFE_FUNCTIONS.get(function_name)
        if not fn:
            log_audit_entry(action="ai_question", detail=question, generated_query=f"REJECTED: unrecognized function '{function_name}'", user_id=user_id or "unauthenticated")
            _log_timing("unrecognized_function")
            return {
                "summary": f"Error: model selected an unrecognized function '{function_name}'.",
                "records": [],
                "source": "Safety check failed \u2014 no such function in the registry",
                "sources": tool_call_history,
            }

        sig = inspect.signature(fn)
        if "user_id" in sig.parameters:
            arguments["user_id"] = user_id
        if "role" in sig.parameters:
            arguments["role"] = role

        tool_start = time.perf_counter()
        result = fn(db, **arguments)
        tool_time_total += time.perf_counter() - tool_start
        tool_call_count += 1

        result["function_called"] = function_name
        result["arguments_used"] = arguments
        last_result = result
        tool_call_history.append({
            "function_called": function_name,
            "arguments_used": arguments,
            "summary": result.get("summary"),
            "source": result.get("source"),
            "records": result.get("records", []),
        })

        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tool_call.id,
                "type": "function",
                "function": {"name": function_name, "arguments": tool_call.function.arguments}
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, default=str),
        })

    log_audit_entry(
        action="ai_question", detail=question,
        generated_query=f"{last_result.get('function_called') if last_result else 'none'} (step limit reached)",
        user_id=user_id or "unauthenticated"
    )
    _log_timing("step_limit_reached")
    if last_result:
        last_result["sources"] = tool_call_history
        return last_result
    return {
        "summary": "Could not resolve this question within the allowed number of steps.",
        "records": [],
        "source": "Step limit reached",
        "sources": tool_call_history,
    }

def log_audit_entry(action: str, detail: str, generated_query: str = None, user_id: str = "unauthenticated"):
    """
    Writes one row to audit_log using a dedicated write session, separate
    from whatever read-only session the calling endpoint is using. Audit
    logging is a legitimate write and must not go through the SELECT-only
    connection used for actual data queries.
    """
    write_db = SessionLocal()
    try:
        entry = models.AuditLog(
            user_id=user_id,
            action=action,
            detail=detail,
            generated_query=generated_query,
            occurred_at=datetime.now(timezone.utc),
        )
        write_db.add(entry)
        write_db.commit()
    finally:
        write_db.close()

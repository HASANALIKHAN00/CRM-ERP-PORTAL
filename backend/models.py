from sqlalchemy import Column, String, Integer, Numeric, Boolean, Date, Time, DateTime, Text, ForeignKey
from database import Base
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from database import Base
from sqlalchemy import text as sa_text



class Customer(Base):
    __tablename__ = "customers"
    customer_id = Column(String(140), primary_key=True)
    customer_name = Column(String(255), nullable=False)
    customer_group = Column(String(140))
    territory = Column(String(140))
    account_manager_user = Column(String(140))
    phone = Column(String(50))
    email = Column(String(255))
    is_disabled = Column(Boolean, default=False)
    company_activity = Column(String(140))
    employee_count_band = Column(String(50))
    country = Column(String(140))
    device_count = Column(Integer)
    install_volume_monthly = Column(String(50))
    total_monthly_devices = Column(Numeric(12, 2))
    total_monthly_devices_usd = Column(Numeric(12, 2))
    gps_installs_monthly = Column(Integer)
    technician_count_general = Column(Integer)
    gps_technician_count = Column(Integer)
    client_progress = Column(String(50))
    target_market = Column(String(50))
    is_assigned = Column(Boolean)
    assigned_on = Column(Date)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Lead(Base):
    __tablename__ = "leads"
    lead_id = Column(String(140), primary_key=True)
    client_name = Column(String(255))
    country = Column(String(140))
    lead_date = Column(Date)
    owner_user = Column(String(140))
    expected_closing_date = Column(Date)
    probability = Column(Numeric(5, 2))
    status = Column(String(50))
    stage_comments = Column(Text)
    manufacturer = Column(String(140))
    category = Column(String(50))
    client_requirement_notes = Column(Text)
    solution = Column(Text)
    quantity = Column(String(50))
    total_value = Column(Numeric(14, 2))
    base_total_value = Column(Numeric(14, 2))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Opportunity(Base):
    __tablename__ = "opportunities"
    opportunity_id = Column(String(140), primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    customer_name = Column(String(255))
    status = Column(String(50))
    opportunity_from = Column(String(140))
    owner_user = Column(String(140))
    opportunity_amount = Column(Numeric(14, 2))
    expected_closing_date = Column(Date)
    opportunity_date = Column(Date)
    lost_reason = Column(Text)
    opportunity_custom_date = Column(Date)
    pipeline_stage = Column(String(50))
    stage_comments = Column(Text)
    device_manufacturer = Column(String(140))
    product_category = Column(String(50))
    client_requirement_notes = Column(Text)
    proposed_solution = Column(Text)
    device_qty = Column(Integer)
    device_model = Column(String(140))
    unit_price_usd = Column(Numeric(12, 2))
    total_value_usd = Column(Numeric(14, 2))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    sales_order_id = Column(String(140), primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    customer_name = Column(String(255))
    order_date = Column(Date)
    delivery_date = Column(Date)
    status = Column(String(50))
    delivery_status = Column(String(50))
    billing_status = Column(String(50))
    order_value = Column(Numeric(14, 2))
    currency = Column(String(10))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"
    invoice_id = Column(String(140), primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    customer_name = Column(String(255))
    invoice_date = Column(Date)
    due_date = Column(Date)
    status = Column(String(50))
    invoice_value = Column(Numeric(14, 2))
    outstanding_amount = Column(Numeric(14, 2))
    is_credit_note = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(String(140), primary_key=True)
    subject = Column(String(255))
    status = Column(String(50))
    priority = Column(String(20))
    expected_start = Column(DateTime(timezone=True))
    expected_end = Column(DateTime(timezone=True))
    completed_by_user = Column(String(140))
    completed_on = Column(Date)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Todo(Base):
    __tablename__ = "todos"
    todo_id = Column(String(140), primary_key=True)
    description = Column(Text)
    status = Column(String(50))
    priority = Column(String(20))
    due_date = Column(Date)
    assigned_to_user = Column(String(140))
    linked_doctype = Column(String(140))
    linked_record_id = Column(String(140))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class Communication(Base):
    __tablename__ = "communications"
    communication_id = Column(String(140), primary_key=True)
    medium = Column(String(50))
    sender = Column(String(255))
    recipients = Column(Text)
    communication_at = Column(DateTime(timezone=True))
    direction = Column(String(20))
    status = Column(String(50))
    linked_doctype = Column(String(140))
    linked_record_id = Column(String(140))
    subject = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class CallLog(Base):
    __tablename__ = "call_logs"
    call_id = Column(String(140), primary_key=True)
    from_number = Column(String(50))
    to_number = Column(String(50))
    handled_by_user = Column(String(140))
    call_medium = Column(String(50))
    call_start = Column(DateTime(timezone=True))
    call_end = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    call_direction = Column(String(20))
    call_type = Column(String(50))
    call_status = Column(String(50))
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class LogisticsEntry(Base):
    __tablename__ = "logistics_entries"
    logistics_entry_id = Column(String(140), primary_key=True)
    entry_no = Column(String(140))
    sales_status = Column(String(50))
    entry_date = Column(Date)
    related_order_id = Column(String(140), ForeignKey("sales_orders.sales_order_id"))
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    shipment_status = Column(String(50))
    device_qty = Column(Integer)
    shipment_value = Column(Numeric(14, 2))
    shipment_value_company_currency = Column(Numeric(14, 2))
    courier = Column(String(140))
    shipment_no = Column(String(140))
    destination = Column(String(255))
    duty_paid_by = Column(String(50))
    delivery_status = Column(String(50))
    payment_status = Column(String(50))
    payment_date = Column(Date)
    imei_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class LogisticsEntryItem(Base):
    __tablename__ = "logistics_entry_items"
    id = Column(Integer, primary_key=True)
    erpnext_name = Column(String(140), unique=True)
    logistics_entry_id = Column(String(140), ForeignKey("logistics_entries.logistics_entry_id"))
    item_model = Column(String(140))
    manufacturer = Column(String(140))
    quantity = Column(Integer)
    unit_price = Column(Numeric(12, 2))
    line_amount = Column(Numeric(14, 2))


class LogisticsComment(Base):
    __tablename__ = "logistics_comments"
    id = Column(Integer, primary_key=True)
    logistics_entry_id = Column(String(140), ForeignKey("logistics_entries.logistics_entry_id"))
    erpnext_name = Column(String(140), unique=True)
    comment_at = Column(DateTime(timezone=True))
    team = Column(String(50))
    commented_by_user = Column(String(140))
    comment_text = Column(Text)


class ImeiDetail(Base):
    __tablename__ = "imei_details"
    id = Column(Integer, primary_key=True)
    erpnext_name = Column(String(140), unique=True)
    logistics_entry_id = Column(String(140), ForeignKey("logistics_entries.logistics_entry_id"))
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    item_id = Column(String(140))
    imei_number = Column(String(50))
    serial_number = Column(String(50))


class CustomerMonthlyDevice(Base):
    __tablename__ = "customer_monthly_devices"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    erpnext_name = Column(String(140), unique=True)
    manufacturer = Column(String(140))
    model = Column(String(140))
    monthly_qty = Column(Numeric(10, 2))
    unit_price_usd = Column(Numeric(12, 2))
    monthly_value_usd = Column(Numeric(12, 2))


class CustomerSampleTesting(Base):
    __tablename__ = "customer_sample_testing"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    erpnext_name = Column(String(140), unique=True)
    test_date = Column(Date)
    test_stage = Column(String(140))
    notes = Column(Text)


class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    erpnext_name = Column(String(140), unique=True)
    contact_role = Column(String(140))
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))


class CustomerProjectTask(Base):
    __tablename__ = "customer_project_tasks"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    erpnext_name = Column(String(140), unique=True)
    project_name = Column(String(255))
    device_model = Column(String(140))
    project_stage = Column(String(50))
    reason = Column(Text)
    use_case = Column(String(255))
    quantity = Column(Integer)
    unit_price_usd = Column(Numeric(12, 2))
    project_value_usd = Column(Numeric(14, 2))


class CustomerActivityDetail(Base):
    __tablename__ = "customer_activity_details"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(140), ForeignKey("customers.customer_id"))
    erpnext_name = Column(String(140), unique=True)
    logged_by_user = Column(String(140))
    activity_date = Column(Date)
    activity_time = Column(Time)
    point_of_contact_role = Column(String(140))
    activity_type = Column(String(140))
    activity_scenario = Column(String(140))
    result = Column(Text)
    status = Column(String(20))
    scenario_other_detail = Column(Text)
    


class Quotation(Base):
    __tablename__ = "quotations"
    quotation_id = Column(String(140), primary_key=True)
    customer_name = Column(String(255))
    quotation_to = Column(String(50))
    transaction_date = Column(Date)
    status = Column(String(50))
    grand_total = Column(Numeric(14, 2))
    opportunity_id = Column(String(140), ForeignKey("opportunities.opportunity_id"))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ActivityLogEntry(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(140))
    operation = Column(String(50))
    subject = Column(String(255))
    logged_at = Column(DateTime(timezone=True))


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    backup_file_name = Column(String(255))
    backup_file_size_bytes = Column(Integer)
    result = Column(String(20))
    records_processed = Column(Integer)
    records_inserted = Column(Integer)
    records_updated = Column(Integer)
    records_skipped = Column(Integer)
    records_rejected = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_summary = Column(Text)


class SyncError(Base):
    __tablename__ = "sync_errors"
    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, ForeignKey("sync_runs.id"))
    doctype = Column(String(140))
    record_id = Column(String(140))
    error_message = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(140), nullable=False)
    action = Column(String(50))
    detail = Column(Text)
    generated_query = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False)

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False, default="New chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text)
    records = Column(JSONB)
    source_note = Column(Text)
    # Full per-tool-call trail for this answer (function name, arguments,
    # summary, source note, and records for EVERY tool call made while
    # answering -- not just the last one). `records`/`source_note` above
    # stay as the last call's data for backward compatibility with older
    # rows and the inline table; this is what a multi-source export reads.
    sources = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ---------- HR-module tables, awaiting Employee/Attendance/Department read
# access from ERPNext (requested from Hassan). Sync entries for these are
# present in sync_config.py but will insert 0 rows until that access is
# granted -- these tables and columns are safe to create now regardless. ----

class Department(Base):
    __tablename__ = "departments"
    department_name = Column(String(255), primary_key=True)
    department_label = Column(String(255))
    parent_department = Column(String(255))
    company = Column(String(140))

class Employee(Base):
    __tablename__ = "employees"
    employee_id = Column(String(140), primary_key=True)
    employee_name = Column(String(255))
    user_id = Column(String(140))
    department = Column(String(255))
    created_at = Column(DateTime(timezone=True))

class Attendance(Base):
    __tablename__ = "attendance"
    attendance_id = Column(String(140), primary_key=True)
    employee_id = Column(String(140), ForeignKey("employees.employee_id"))
    employee_name = Column(String(255))
    attendance_date = Column(Date)
    status = Column(String(20))
    working_hours = Column(Numeric(6, 2))
    in_time = Column(DateTime(timezone=True))
    out_time = Column(DateTime(timezone=True))
    department = Column(String(255))


class EmployeeCheckin(Base):
    __tablename__ = "employee_checkins"
    checkin_id = Column(String(140), primary_key=True)
    employee_id = Column(String(140), ForeignKey("employees.employee_id"))
    log_type = Column(String(10))
    time = Column(DateTime(timezone=True))
    shift_start = Column(DateTime(timezone=True))
    shift_end = Column(DateTime(timezone=True))

class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    summary_date = Column(Date, nullable=False, index=True)
    content = Column(Text, nullable=False)
    metrics = Column(JSONB)
    email_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

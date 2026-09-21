-- =========================================================
-- BoxTech Reporting Database — Initial Schema
-- Excludes: Customer Sales Opportunity, Customer Sales Forecast
-- (pending confirmation on which mechanism is actually used)
-- Excludes: 22 dormant Customer custom fields (0% filled in sample)
-- =========================================================

-- ---------- CRM ----------

CREATE TABLE customers (
    customer_id             VARCHAR(140) PRIMARY KEY,   -- ERPNext 'name'
    customer_name           VARCHAR(255) NOT NULL,
    customer_group          VARCHAR(140),
    territory               VARCHAR(140),
    account_manager_user    VARCHAR(140),
    phone                   VARCHAR(50),
    email                   VARCHAR(255),
    is_disabled             BOOLEAN DEFAULT FALSE,

    -- Core custom fields (confirmed consistently populated in sample)
    company_activity        VARCHAR(140),
    employee_count_band     VARCHAR(50),
    country                 VARCHAR(140),
    device_count            INTEGER,
    install_volume_monthly  VARCHAR(50),
    total_monthly_devices   NUMERIC(12,2),
    total_monthly_devices_usd NUMERIC(12,2),
    gps_installs_monthly    INTEGER,
    technician_count        INTEGER,                    -- consolidated from the confirmed duplicate pair
    is_assigned              BOOLEAN,
    assigned_on              DATE,

    created_at              TIMESTAMPTZ NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_customers_territory ON customers(territory);
CREATE INDEX idx_customers_updated_at ON customers(updated_at);

CREATE TABLE leads (
    lead_id                 VARCHAR(140) PRIMARY KEY,
    lead_name                VARCHAR(255),
    company_name             VARCHAR(255),
    email                     VARCHAR(255),
    phone_mobile              VARCHAR(50),
    phone_office               VARCHAR(50),
    phone_whatsapp            VARCHAR(50),
    lead_source                VARCHAR(140),
    owner_user                  VARCHAR(140),
    status                       VARCHAR(50),
    territory                    VARCHAR(140),
    industry                     VARCHAR(140),
    converted_customer_id        VARCHAR(140) REFERENCES customers(customer_id),
    created_at                   TIMESTAMPTZ NOT NULL,
    updated_at                   TIMESTAMPTZ NOT NULL
);
-- Structure only — confirmed 0 records currently in ERPNext

-- ---------- Sales pipeline ----------

CREATE TABLE opportunities (
    opportunity_id           VARCHAR(140) PRIMARY KEY,
    customer_id              VARCHAR(140) REFERENCES customers(customer_id),
    customer_name             VARCHAR(255),
    status                     VARCHAR(50),
    owner_user                  VARCHAR(140),
    opportunity_amount           NUMERIC(14,2),
    expected_closing_date         DATE,
    opportunity_date               DATE,
    lost_reason                     TEXT,

    -- Confirmed real custom fields
    opportunity_custom_date          DATE,
    pipeline_stage                     VARCHAR(50),      -- "Sales Status" on the form
    stage_comments                      TEXT,
    device_manufacturer                   VARCHAR(140),
    product_category                       VARCHAR(50),
    client_requirement_notes                 TEXT,
    proposed_solution                          TEXT,
    device_qty                                   INTEGER,
    device_model                                  VARCHAR(140),
    unit_price_usd                                 NUMERIC(12,2),
    total_value_usd                                 NUMERIC(14,2),

    created_at                                        TIMESTAMPTZ NOT NULL,
    updated_at                                          TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_opportunities_customer ON opportunities(customer_id);
CREATE INDEX idx_opportunities_stage ON opportunities(pipeline_stage);
CREATE INDEX idx_opportunities_updated_at ON opportunities(updated_at);

CREATE TABLE sales_orders (
    sales_order_id          VARCHAR(140) PRIMARY KEY,
    customer_id              VARCHAR(140) REFERENCES customers(customer_id),
    customer_name              VARCHAR(255),
    order_date                    DATE,
    delivery_date                   DATE,
    status                            VARCHAR(50),
    delivery_status                     VARCHAR(50),
    billing_status                        VARCHAR(50),
    order_value                             NUMERIC(14,2),
    currency                                  VARCHAR(10),
    created_at                                  TIMESTAMPTZ NOT NULL,
    updated_at                                    TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_sales_orders_customer ON sales_orders(customer_id);

CREATE TABLE sales_invoices (
    invoice_id                VARCHAR(140) PRIMARY KEY,
    customer_id                 VARCHAR(140) REFERENCES customers(customer_id),
    customer_name                 VARCHAR(255),
    invoice_date                    DATE,
    due_date                          DATE,
    status                              VARCHAR(50),
    invoice_value                         NUMERIC(14,2),
    outstanding_amount                      NUMERIC(14,2),
    is_credit_note                            BOOLEAN DEFAULT FALSE,
    created_at                                  TIMESTAMPTZ NOT NULL,
    updated_at                                    TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_sales_invoices_customer ON sales_invoices(customer_id);
CREATE INDEX idx_sales_invoices_outstanding ON sales_invoices(outstanding_amount) WHERE outstanding_amount > 0;

-- ---------- Activity & communication ----------

CREATE TABLE tasks (
    task_id                  VARCHAR(140) PRIMARY KEY,
    subject                     VARCHAR(255),
    status                        VARCHAR(50),
    priority                        VARCHAR(20),
    expected_start                    TIMESTAMPTZ,
    expected_end                        TIMESTAMPTZ,
    completed_by_user                     VARCHAR(140),
    completed_on                            DATE,
    created_at                                TIMESTAMPTZ NOT NULL,
    updated_at                                  TIMESTAMPTZ NOT NULL
);
-- Structure only — confirmed 0 records currently in ERPNext

CREATE TABLE todos (
    todo_id                   VARCHAR(140) PRIMARY KEY,
    description                  TEXT,
    status                          VARCHAR(50),
    priority                          VARCHAR(20),
    due_date                            DATE,
    assigned_to_user                       VARCHAR(140),
    linked_doctype                            VARCHAR(140),
    linked_record_id                            VARCHAR(140),
    created_at                                    TIMESTAMPTZ NOT NULL,
    updated_at                                      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_todos_linked_record ON todos(linked_doctype, linked_record_id);

CREATE TABLE communications (
    communication_id           VARCHAR(140) PRIMARY KEY,
    medium                        VARCHAR(50),
    sender                           VARCHAR(255),
    recipients                         TEXT,
    communication_at                     TIMESTAMPTZ,
    direction                              VARCHAR(20),
    status                                    VARCHAR(50),
    linked_doctype                              VARCHAR(140),
    linked_record_id                              VARCHAR(140),
    subject                                          VARCHAR(255),
    -- NOTE: full email body intentionally excluded from reporting DB per privacy decision
    created_at                                          TIMESTAMPTZ NOT NULL,
    updated_at                                            TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_communications_linked_record ON communications(linked_doctype, linked_record_id);

CREATE TABLE call_logs (
    call_id                    VARCHAR(140) PRIMARY KEY,
    from_number                  VARCHAR(50),
    to_number                      VARCHAR(50),
    handled_by_user                  VARCHAR(140),
    call_medium                        VARCHAR(50),
    call_start                            TIMESTAMPTZ,
    call_end                                TIMESTAMPTZ,
    duration_seconds                          INTEGER,
    call_direction                              VARCHAR(20),
    call_type                                     VARCHAR(50),
    call_status                                     VARCHAR(50),
    customer_id                                       VARCHAR(140) REFERENCES customers(customer_id),
    -- NOTE: recording_url and summary intentionally excluded per privacy decision
    created_at                                              TIMESTAMPTZ NOT NULL,
    updated_at                                                TIMESTAMPTZ NOT NULL
);
-- Structure only — confirmed 0 records currently; ready for when telephony activates

-- ---------- Logistics ----------

CREATE TABLE logistics_entries (
    logistics_entry_id         VARCHAR(140) PRIMARY KEY,
    entry_no                      VARCHAR(140),
    sales_status                     VARCHAR(50),
    entry_date                          DATE,
    related_order_id                       VARCHAR(140) REFERENCES sales_orders(sales_order_id),
    customer_id                               VARCHAR(140) REFERENCES customers(customer_id),
    shipment_status                              VARCHAR(50),
    device_qty                                     INTEGER,
    shipment_value                                   NUMERIC(14,2),
    shipment_value_company_currency                    NUMERIC(14,2),
    courier                                              VARCHAR(140),
    shipment_no                                            VARCHAR(140),
    destination                                              VARCHAR(255),
    duty_paid_by                                               VARCHAR(50),
    delivery_status                                              VARCHAR(50),
    payment_status                                                 VARCHAR(50),
    payment_date                                                     DATE,
    imei_count                                                         INTEGER,
    created_at                                                           TIMESTAMPTZ NOT NULL,
    updated_at                                                             TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_logistics_customer ON logistics_entries(customer_id);
CREATE INDEX idx_logistics_related_order ON logistics_entries(related_order_id);
-- order_no linkage confirmed real but 0% adoption in sample — validate/flag mismatches during sync

CREATE TABLE logistics_entry_items (
    id                        SERIAL PRIMARY KEY,
    logistics_entry_id          VARCHAR(140) REFERENCES logistics_entries(logistics_entry_id),
    item_model                     VARCHAR(140),
    manufacturer                     VARCHAR(140),
    quantity                           INTEGER,
    unit_price                           NUMERIC(12,2),
    line_amount                            NUMERIC(14,2)
);
CREATE INDEX idx_logistics_items_entry ON logistics_entry_items(logistics_entry_id);

CREATE TABLE logistics_comments (
    id                        SERIAL PRIMARY KEY,
    logistics_entry_id          VARCHAR(140) REFERENCES logistics_entries(logistics_entry_id),
    comment_at                     TIMESTAMPTZ,
    team                              VARCHAR(50),
    commented_by_user                  VARCHAR(140),
    comment_text                          TEXT
);
CREATE INDEX idx_logistics_comments_entry ON logistics_comments(logistics_entry_id);

CREATE TABLE imei_details (
    id                        SERIAL PRIMARY KEY,
    logistics_entry_id          VARCHAR(140) REFERENCES logistics_entries(logistics_entry_id),
    customer_id                    VARCHAR(140) REFERENCES customers(customer_id),
    item_id                           VARCHAR(140),
    imei_number                         VARCHAR(50),
    serial_number                         VARCHAR(50)
);
CREATE INDEX idx_imei_details_entry ON imei_details(logistics_entry_id);
CREATE INDEX idx_imei_details_imei ON imei_details(imei_number);

CREATE TABLE customer_monthly_devices (
    id                        SERIAL PRIMARY KEY,
    customer_id                  VARCHAR(140) REFERENCES customers(customer_id),
    manufacturer                    VARCHAR(140),
    model                              VARCHAR(140),
    monthly_qty                          NUMERIC(10,2),
    unit_price_usd                          NUMERIC(12,2),
    monthly_value_usd                          NUMERIC(12,2)
);
CREATE INDEX idx_customer_monthly_devices_customer ON customer_monthly_devices(customer_id);

-- ---------- Sync & audit infrastructure ----------

CREATE TABLE sync_runs (
    id                        SERIAL PRIMARY KEY,
    started_at                   TIMESTAMPTZ NOT NULL,
    completed_at                    TIMESTAMPTZ,
    backup_file_name                   VARCHAR(255),
    backup_file_size_bytes                INTEGER,
    result                                    VARCHAR(20),   -- success / partial / failed
    records_processed                           INTEGER,
    records_inserted                              INTEGER,
    records_updated                                 INTEGER,
    records_skipped                                   INTEGER,
    records_rejected                                    INTEGER,
    retry_count                                           INTEGER DEFAULT 0,
    error_summary                                           TEXT
);

CREATE TABLE sync_errors (
    id                        SERIAL PRIMARY KEY,
    sync_run_id                  INTEGER REFERENCES sync_runs(id),
    doctype                         VARCHAR(140),
    record_id                         VARCHAR(140),
    error_message                       TEXT,
    occurred_at                            TIMESTAMPTZ NOT NULL
);

CREATE TABLE audit_log (
    id                        SERIAL PRIMARY KEY,
    user_id                      VARCHAR(140) NOT NULL,
    action                          VARCHAR(50),      -- login / question_asked / report_generated / export
    detail                            TEXT,
    generated_query                     TEXT,
    occurred_at                            TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_audit_log_user ON audit_log(user_id, occurred_at);
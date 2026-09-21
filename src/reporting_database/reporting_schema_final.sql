--
-- PostgreSQL database dump
--

\restrict bW13CwpQYehzihrxiUT1bCweU079h0xTkaMnFuESUb5hBlJdfNvLZiHwXugBIiO

-- Dumped from database version 18.2
-- Dumped by pg_dump version 18.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    user_id character varying(140) NOT NULL,
    action character varying(50),
    detail text,
    generated_query text,
    occurred_at timestamp with time zone NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: call_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.call_logs (
    call_id character varying(140) NOT NULL,
    from_number character varying(50),
    to_number character varying(50),
    handled_by_user character varying(140),
    call_medium character varying(50),
    call_start timestamp with time zone,
    call_end timestamp with time zone,
    duration_seconds integer,
    call_direction character varying(20),
    call_type character varying(50),
    call_status character varying(50),
    customer_id character varying(140),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: communications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.communications (
    communication_id character varying(140) NOT NULL,
    medium character varying(50),
    sender character varying(255),
    recipients text,
    communication_at timestamp with time zone,
    direction character varying(20),
    status character varying(50),
    linked_doctype character varying(140),
    linked_record_id character varying(140),
    subject character varying(255),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: customer_activity_details; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_activity_details (
    id integer NOT NULL,
    customer_id character varying(140),
    activity_date date,
    activity_time time without time zone,
    point_of_contact_role character varying(140),
    activity_type character varying(140),
    activity_scenario character varying(140),
    result text,
    status character varying(20),
    scenario_other_detail text
);


--
-- Name: customer_activity_details_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_activity_details_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_activity_details_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_activity_details_id_seq OWNED BY public.customer_activity_details.id;


--
-- Name: customer_contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_contacts (
    id integer NOT NULL,
    customer_id character varying(140),
    contact_role character varying(140),
    contact_name character varying(255),
    contact_email character varying(255),
    contact_phone character varying(50)
);


--
-- Name: customer_contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_contacts_id_seq OWNED BY public.customer_contacts.id;


--
-- Name: customer_monthly_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_monthly_devices (
    id integer NOT NULL,
    customer_id character varying(140),
    manufacturer character varying(140),
    model character varying(140),
    monthly_qty numeric(10,2),
    unit_price_usd numeric(12,2),
    monthly_value_usd numeric(12,2)
);


--
-- Name: customer_monthly_devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_monthly_devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_monthly_devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_monthly_devices_id_seq OWNED BY public.customer_monthly_devices.id;


--
-- Name: customer_project_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_project_tasks (
    id integer NOT NULL,
    customer_id character varying(140),
    project_name character varying(255),
    device_model character varying(140),
    project_stage character varying(50),
    reason text,
    use_case character varying(255),
    quantity integer,
    unit_price_usd numeric(12,2),
    project_value_usd numeric(14,2)
);


--
-- Name: customer_project_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_project_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_project_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_project_tasks_id_seq OWNED BY public.customer_project_tasks.id;


--
-- Name: customer_sample_testing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_sample_testing (
    id integer NOT NULL,
    customer_id character varying(140),
    test_date date,
    test_stage character varying(140),
    notes text
);


--
-- Name: customer_sample_testing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_sample_testing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_sample_testing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_sample_testing_id_seq OWNED BY public.customer_sample_testing.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    customer_id character varying(140) NOT NULL,
    customer_name character varying(255) NOT NULL,
    customer_group character varying(140),
    territory character varying(140),
    account_manager_user character varying(140),
    phone character varying(50),
    email character varying(255),
    is_disabled boolean DEFAULT false,
    company_activity character varying(140),
    employee_count_band character varying(50),
    country character varying(140),
    device_count integer,
    install_volume_monthly character varying(50),
    total_monthly_devices numeric(12,2),
    total_monthly_devices_usd numeric(12,2),
    gps_installs_monthly integer,
    technician_count_general integer,
    is_assigned boolean,
    assigned_on date,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    gps_technician_count integer,
    client_progress character varying(50),
    target_market character varying(50)
);


--
-- Name: imei_details; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.imei_details (
    id integer NOT NULL,
    logistics_entry_id character varying(140),
    customer_id character varying(140),
    item_id character varying(140),
    imei_number character varying(50),
    serial_number character varying(50)
);


--
-- Name: imei_details_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.imei_details_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: imei_details_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.imei_details_id_seq OWNED BY public.imei_details.id;


--
-- Name: leads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leads (
    lead_id character varying(140) NOT NULL,
    lead_name character varying(255),
    company_name character varying(255),
    email character varying(255),
    phone_mobile character varying(50),
    phone_office character varying(50),
    phone_whatsapp character varying(50),
    lead_source character varying(140),
    owner_user character varying(140),
    status character varying(50),
    territory character varying(140),
    industry character varying(140),
    converted_customer_id character varying(140),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: logistics_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.logistics_comments (
    id integer NOT NULL,
    logistics_entry_id character varying(140),
    comment_at timestamp with time zone,
    team character varying(50),
    commented_by_user character varying(140),
    comment_text text
);


--
-- Name: logistics_comments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.logistics_comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: logistics_comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.logistics_comments_id_seq OWNED BY public.logistics_comments.id;


--
-- Name: logistics_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.logistics_entries (
    logistics_entry_id character varying(140) NOT NULL,
    entry_no character varying(140),
    sales_status character varying(50),
    entry_date date,
    related_order_id character varying(140),
    customer_id character varying(140),
    shipment_status character varying(50),
    device_qty integer,
    shipment_value numeric(14,2),
    shipment_value_company_currency numeric(14,2),
    courier character varying(140),
    shipment_no character varying(140),
    destination character varying(255),
    duty_paid_by character varying(50),
    delivery_status character varying(50),
    payment_status character varying(50),
    payment_date date,
    imei_count integer,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: logistics_entry_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.logistics_entry_items (
    id integer NOT NULL,
    logistics_entry_id character varying(140),
    item_model character varying(140),
    manufacturer character varying(140),
    quantity integer,
    unit_price numeric(12,2),
    line_amount numeric(14,2)
);


--
-- Name: logistics_entry_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.logistics_entry_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: logistics_entry_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.logistics_entry_items_id_seq OWNED BY public.logistics_entry_items.id;


--
-- Name: opportunities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opportunities (
    opportunity_id character varying(140) NOT NULL,
    customer_id character varying(140),
    customer_name character varying(255),
    status character varying(50),
    owner_user character varying(140),
    opportunity_amount numeric(14,2),
    expected_closing_date date,
    opportunity_date date,
    lost_reason text,
    opportunity_custom_date date,
    pipeline_stage character varying(50),
    stage_comments text,
    device_manufacturer character varying(140),
    product_category character varying(50),
    client_requirement_notes text,
    proposed_solution text,
    device_qty integer,
    device_model character varying(140),
    unit_price_usd numeric(12,2),
    total_value_usd numeric(14,2),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: sales_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_invoices (
    invoice_id character varying(140) NOT NULL,
    customer_id character varying(140),
    customer_name character varying(255),
    invoice_date date,
    due_date date,
    status character varying(50),
    invoice_value numeric(14,2),
    outstanding_amount numeric(14,2),
    is_credit_note boolean DEFAULT false,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: sales_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_orders (
    sales_order_id character varying(140) NOT NULL,
    customer_id character varying(140),
    customer_name character varying(255),
    order_date date,
    delivery_date date,
    status character varying(50),
    delivery_status character varying(50),
    billing_status character varying(50),
    order_value numeric(14,2),
    currency character varying(10),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: sync_errors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_errors (
    id integer NOT NULL,
    sync_run_id integer,
    doctype character varying(140),
    record_id character varying(140),
    error_message text,
    occurred_at timestamp with time zone NOT NULL
);


--
-- Name: sync_errors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_errors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_errors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_errors_id_seq OWNED BY public.sync_errors.id;


--
-- Name: sync_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_runs (
    id integer NOT NULL,
    started_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    backup_file_name character varying(255),
    backup_file_size_bytes integer,
    result character varying(20),
    records_processed integer,
    records_inserted integer,
    records_updated integer,
    records_skipped integer,
    records_rejected integer,
    retry_count integer DEFAULT 0,
    error_summary text
);


--
-- Name: sync_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_runs_id_seq OWNED BY public.sync_runs.id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    task_id character varying(140) NOT NULL,
    subject character varying(255),
    status character varying(50),
    priority character varying(20),
    expected_start timestamp with time zone,
    expected_end timestamp with time zone,
    completed_by_user character varying(140),
    completed_on date,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: todos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.todos (
    todo_id character varying(140) NOT NULL,
    description text,
    status character varying(50),
    priority character varying(20),
    due_date date,
    assigned_to_user character varying(140),
    linked_doctype character varying(140),
    linked_record_id character varying(140),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: customer_activity_details id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_activity_details ALTER COLUMN id SET DEFAULT nextval('public.customer_activity_details_id_seq'::regclass);


--
-- Name: customer_contacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_contacts ALTER COLUMN id SET DEFAULT nextval('public.customer_contacts_id_seq'::regclass);


--
-- Name: customer_monthly_devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_monthly_devices ALTER COLUMN id SET DEFAULT nextval('public.customer_monthly_devices_id_seq'::regclass);


--
-- Name: customer_project_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_project_tasks ALTER COLUMN id SET DEFAULT nextval('public.customer_project_tasks_id_seq'::regclass);


--
-- Name: customer_sample_testing id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_sample_testing ALTER COLUMN id SET DEFAULT nextval('public.customer_sample_testing_id_seq'::regclass);


--
-- Name: imei_details id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imei_details ALTER COLUMN id SET DEFAULT nextval('public.imei_details_id_seq'::regclass);


--
-- Name: logistics_comments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_comments ALTER COLUMN id SET DEFAULT nextval('public.logistics_comments_id_seq'::regclass);


--
-- Name: logistics_entry_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entry_items ALTER COLUMN id SET DEFAULT nextval('public.logistics_entry_items_id_seq'::regclass);


--
-- Name: sync_errors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_errors ALTER COLUMN id SET DEFAULT nextval('public.sync_errors_id_seq'::regclass);


--
-- Name: sync_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_runs ALTER COLUMN id SET DEFAULT nextval('public.sync_runs_id_seq'::regclass);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: call_logs call_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_logs
    ADD CONSTRAINT call_logs_pkey PRIMARY KEY (call_id);


--
-- Name: communications communications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.communications
    ADD CONSTRAINT communications_pkey PRIMARY KEY (communication_id);


--
-- Name: customer_activity_details customer_activity_details_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_activity_details
    ADD CONSTRAINT customer_activity_details_pkey PRIMARY KEY (id);


--
-- Name: customer_contacts customer_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_contacts
    ADD CONSTRAINT customer_contacts_pkey PRIMARY KEY (id);


--
-- Name: customer_monthly_devices customer_monthly_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_monthly_devices
    ADD CONSTRAINT customer_monthly_devices_pkey PRIMARY KEY (id);


--
-- Name: customer_project_tasks customer_project_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_project_tasks
    ADD CONSTRAINT customer_project_tasks_pkey PRIMARY KEY (id);


--
-- Name: customer_sample_testing customer_sample_testing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_sample_testing
    ADD CONSTRAINT customer_sample_testing_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (customer_id);


--
-- Name: imei_details imei_details_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imei_details
    ADD CONSTRAINT imei_details_pkey PRIMARY KEY (id);


--
-- Name: leads leads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_pkey PRIMARY KEY (lead_id);


--
-- Name: logistics_comments logistics_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_comments
    ADD CONSTRAINT logistics_comments_pkey PRIMARY KEY (id);


--
-- Name: logistics_entries logistics_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entries
    ADD CONSTRAINT logistics_entries_pkey PRIMARY KEY (logistics_entry_id);


--
-- Name: logistics_entry_items logistics_entry_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entry_items
    ADD CONSTRAINT logistics_entry_items_pkey PRIMARY KEY (id);


--
-- Name: opportunities opportunities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opportunities
    ADD CONSTRAINT opportunities_pkey PRIMARY KEY (opportunity_id);


--
-- Name: sales_invoices sales_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_invoices
    ADD CONSTRAINT sales_invoices_pkey PRIMARY KEY (invoice_id);


--
-- Name: sales_orders sales_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_pkey PRIMARY KEY (sales_order_id);


--
-- Name: sync_errors sync_errors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_errors
    ADD CONSTRAINT sync_errors_pkey PRIMARY KEY (id);


--
-- Name: sync_runs sync_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_runs
    ADD CONSTRAINT sync_runs_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (task_id);


--
-- Name: todos todos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.todos
    ADD CONSTRAINT todos_pkey PRIMARY KEY (todo_id);


--
-- Name: idx_audit_log_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_user ON public.audit_log USING btree (user_id, occurred_at);


--
-- Name: idx_communications_linked_record; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_communications_linked_record ON public.communications USING btree (linked_doctype, linked_record_id);


--
-- Name: idx_customer_activity_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_activity_customer ON public.customer_activity_details USING btree (customer_id);


--
-- Name: idx_customer_activity_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_activity_date ON public.customer_activity_details USING btree (activity_date);


--
-- Name: idx_customer_contacts_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_contacts_customer ON public.customer_contacts USING btree (customer_id);


--
-- Name: idx_customer_monthly_devices_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_monthly_devices_customer ON public.customer_monthly_devices USING btree (customer_id);


--
-- Name: idx_customer_project_tasks_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_project_tasks_customer ON public.customer_project_tasks USING btree (customer_id);


--
-- Name: idx_customers_territory; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customers_territory ON public.customers USING btree (territory);


--
-- Name: idx_customers_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customers_updated_at ON public.customers USING btree (updated_at);


--
-- Name: idx_imei_details_entry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_imei_details_entry ON public.imei_details USING btree (logistics_entry_id);


--
-- Name: idx_imei_details_imei; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_imei_details_imei ON public.imei_details USING btree (imei_number);


--
-- Name: idx_logistics_comments_entry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logistics_comments_entry ON public.logistics_comments USING btree (logistics_entry_id);


--
-- Name: idx_logistics_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logistics_customer ON public.logistics_entries USING btree (customer_id);


--
-- Name: idx_logistics_items_entry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logistics_items_entry ON public.logistics_entry_items USING btree (logistics_entry_id);


--
-- Name: idx_logistics_related_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logistics_related_order ON public.logistics_entries USING btree (related_order_id);


--
-- Name: idx_opportunities_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_opportunities_customer ON public.opportunities USING btree (customer_id);


--
-- Name: idx_opportunities_stage; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_opportunities_stage ON public.opportunities USING btree (pipeline_stage);


--
-- Name: idx_opportunities_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_opportunities_updated_at ON public.opportunities USING btree (updated_at);


--
-- Name: idx_sales_invoices_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sales_invoices_customer ON public.sales_invoices USING btree (customer_id);


--
-- Name: idx_sales_invoices_outstanding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sales_invoices_outstanding ON public.sales_invoices USING btree (outstanding_amount) WHERE (outstanding_amount > (0)::numeric);


--
-- Name: idx_sales_orders_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sales_orders_customer ON public.sales_orders USING btree (customer_id);


--
-- Name: idx_sample_testing_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sample_testing_customer ON public.customer_sample_testing USING btree (customer_id);


--
-- Name: idx_todos_linked_record; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_todos_linked_record ON public.todos USING btree (linked_doctype, linked_record_id);


--
-- Name: call_logs call_logs_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_logs
    ADD CONSTRAINT call_logs_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: customer_activity_details customer_activity_details_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_activity_details
    ADD CONSTRAINT customer_activity_details_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: customer_contacts customer_contacts_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_contacts
    ADD CONSTRAINT customer_contacts_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: customer_monthly_devices customer_monthly_devices_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_monthly_devices
    ADD CONSTRAINT customer_monthly_devices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: customer_project_tasks customer_project_tasks_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_project_tasks
    ADD CONSTRAINT customer_project_tasks_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: customer_sample_testing customer_sample_testing_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_sample_testing
    ADD CONSTRAINT customer_sample_testing_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: imei_details imei_details_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imei_details
    ADD CONSTRAINT imei_details_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: imei_details imei_details_logistics_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imei_details
    ADD CONSTRAINT imei_details_logistics_entry_id_fkey FOREIGN KEY (logistics_entry_id) REFERENCES public.logistics_entries(logistics_entry_id);


--
-- Name: leads leads_converted_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_converted_customer_id_fkey FOREIGN KEY (converted_customer_id) REFERENCES public.customers(customer_id);


--
-- Name: logistics_comments logistics_comments_logistics_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_comments
    ADD CONSTRAINT logistics_comments_logistics_entry_id_fkey FOREIGN KEY (logistics_entry_id) REFERENCES public.logistics_entries(logistics_entry_id);


--
-- Name: logistics_entries logistics_entries_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entries
    ADD CONSTRAINT logistics_entries_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: logistics_entries logistics_entries_related_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entries
    ADD CONSTRAINT logistics_entries_related_order_id_fkey FOREIGN KEY (related_order_id) REFERENCES public.sales_orders(sales_order_id);


--
-- Name: logistics_entry_items logistics_entry_items_logistics_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logistics_entry_items
    ADD CONSTRAINT logistics_entry_items_logistics_entry_id_fkey FOREIGN KEY (logistics_entry_id) REFERENCES public.logistics_entries(logistics_entry_id);


--
-- Name: opportunities opportunities_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opportunities
    ADD CONSTRAINT opportunities_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: sales_invoices sales_invoices_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_invoices
    ADD CONSTRAINT sales_invoices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: sales_orders sales_orders_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: sync_errors sync_errors_sync_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_errors
    ADD CONSTRAINT sync_errors_sync_run_id_fkey FOREIGN KEY (sync_run_id) REFERENCES public.sync_runs(id);


--
-- PostgreSQL database dump complete
--

\unrestrict bW13CwpQYehzihrxiUT1bCweU079h0xTkaMnFuESUb5hBlJdfNvLZiHwXugBIiO


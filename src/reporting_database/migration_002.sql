-- =========================================================
-- BoxTech Reporting Database — Migration 002
-- Corrections + additions from full-backup validation
-- (290 real customers, vs. the earlier 40-record sample)
-- =========================================================

-- ---------- Correction 1: technician fields were wrongly consolidated ----------
-- Originally built as a single technician_count column, based on a
-- sample where the two source fields always matched. Full data shows
-- they diverge in 27 of 290 rows — these are being treated as two
-- genuinely separate fields until BoxTech confirms otherwise.

ALTER TABLE customers RENAME COLUMN technician_count TO technician_count_general;
ALTER TABLE customers ADD COLUMN gps_technician_count INTEGER;

-- ---------- Correction 2: two fields wrongly excluded as "dormant" ----------
-- Full data shows both are genuinely core fields (95% and 49% filled).

ALTER TABLE customers ADD COLUMN client_progress VARCHAR(50);
ALTER TABLE customers ADD COLUMN target_market VARCHAR(50);

-- ---------- Addition: 4 newly-confirmed real child tables ----------

CREATE TABLE customer_sample_testing (
    id                        SERIAL PRIMARY KEY,
    customer_id                  VARCHAR(140) REFERENCES customers(customer_id),
    test_date                       DATE,
    test_stage                        VARCHAR(140),
    notes                                TEXT
);
CREATE INDEX idx_sample_testing_customer ON customer_sample_testing(customer_id);

CREATE TABLE customer_contacts (
    id                        SERIAL PRIMARY KEY,
    customer_id                  VARCHAR(140) REFERENCES customers(customer_id),
    contact_role                    VARCHAR(140),
    contact_name                       VARCHAR(255),
    contact_email                         VARCHAR(255),
    contact_phone                            VARCHAR(50)
);
CREATE INDEX idx_customer_contacts_customer ON customer_contacts(customer_id);
-- NOTE: may supersede customers.contact_name / contact_email / contact_phone
-- (those showed 0% fill in the sample) — pending confirmation, see mapping doc.

CREATE TABLE customer_project_tasks (
    id                        SERIAL PRIMARY KEY,
    customer_id                  VARCHAR(140) REFERENCES customers(customer_id),
    project_name                    VARCHAR(255),
    device_model                       VARCHAR(140),
    project_stage                         VARCHAR(50),   -- Tender, Sample, POC, Commercial, Project Won
    reason                                    TEXT,
    use_case                                    VARCHAR(255),
    quantity                                       INTEGER,
    unit_price_usd                                    NUMERIC(12,2),
    project_value_usd                                    NUMERIC(14,2)
);
CREATE INDEX idx_customer_project_tasks_customer ON customer_project_tasks(customer_id);

CREATE TABLE customer_activity_details (
    id                        SERIAL PRIMARY KEY,
    customer_id                  VARCHAR(140) REFERENCES customers(customer_id),
    activity_date                   DATE,
    activity_time                      TIME,
    point_of_contact_role                 VARCHAR(140),
    activity_type                            VARCHAR(140),
    activity_scenario                           VARCHAR(140),
    result                                          TEXT,
    status                                             VARCHAR(20),  -- In Progress, Complete, Rejected
    scenario_other_detail                                 TEXT
);
CREATE INDEX idx_customer_activity_customer ON customer_activity_details(customer_id);
CREATE INDEX idx_customer_activity_date ON customer_activity_details(activity_date);
-- NOTE: this is by far the highest-volume custom table (2,329 records
-- confirmed) — likely BoxTech's real primary activity-tracking
-- mechanism, more so than the standard tasks/todos tables.
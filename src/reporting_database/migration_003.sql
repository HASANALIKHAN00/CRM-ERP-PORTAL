-- Migration 003: employee attribution + Quotation table

ALTER TABLE customer_activity_details ADD COLUMN logged_by_user VARCHAR(140);

CREATE TABLE quotations (
    quotation_id       VARCHAR(140) PRIMARY KEY,
    customer_name      VARCHAR(255),
    quotation_to       VARCHAR(50),
    transaction_date   DATE,
    status             VARCHAR(50),
    grand_total        NUMERIC(14,2),
    opportunity_id     VARCHAR(140) REFERENCES opportunities(opportunity_id),
    created_at         TIMESTAMPTZ NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_quotations_opportunity ON quotations(opportunity_id);
-- NOTE: opportunity_id confirmed filled on only 11 of 71 real quotations
-- (15%) — reporting on conversion rate must account for this gap rather
-- than treating it as a complete picture.
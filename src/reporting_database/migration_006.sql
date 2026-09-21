-- Migration 006: rebuild leads table to match the new custom Leads DocType
-- (replaces the standard-Lead-based structure, which was never actually
-- BoxTech's real workflow and had 0 synced records)

DROP TABLE IF EXISTS leads CASCADE;

CREATE TABLE leads (
    lead_id                  VARCHAR(140) PRIMARY KEY,
    client_name               VARCHAR(255),
    country                     VARCHAR(140),
    lead_date                     DATE,
    owner_user                       VARCHAR(140),
    expected_closing_date               DATE,
    probability                            NUMERIC(5,2),
    status                                    VARCHAR(50),
    stage_comments                              TEXT,
    manufacturer                                   VARCHAR(140),
    category                                          VARCHAR(50),
    client_requirement_notes                             TEXT,
    solution                                                TEXT,
    quantity                                                   VARCHAR(50),
    total_value                                                   NUMERIC(14,2),
    base_total_value                                                 NUMERIC(14,2),
    created_at                                                          TIMESTAMPTZ NOT NULL,
    updated_at                                                            TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_updated_at ON leads(updated_at);
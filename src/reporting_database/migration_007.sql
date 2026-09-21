-- Migration 007: dedicated SELECT-only role for the API's database connection
-- Per the AI Model / Query Safety document: the safety boundary should be
-- structural (enforced by the database itself), not just logical
-- (enforced only by application code).

CREATE ROLE reporting_api_readonly WITH LOGIN PASSWORD 'b0x103ch-reportingai';

GRANT CONNECT ON DATABASE boxtech_reporting TO reporting_api_readonly;
GRANT USAGE ON SCHEMA public TO reporting_api_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_api_readonly;

-- Ensure any tables created in the future are also automatically
-- covered, without needing to remember to re-grant each time.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reporting_api_readonly;
\getenv reporting_readonly_password REPORTING_READONLY_PASSWORD
CREATE ROLE reporting_api_readonly WITH LOGIN PASSWORD :'reporting_readonly_password';
GRANT CONNECT ON DATABASE boxtech_reporting TO reporting_api_readonly;
GRANT USAGE ON SCHEMA public TO reporting_api_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_api_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reporting_api_readonly;
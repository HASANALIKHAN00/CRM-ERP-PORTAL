CREATE TABLE activity_log (
    id                SERIAL PRIMARY KEY,
    user_id           VARCHAR(140),
    operation         VARCHAR(50),
    subject           VARCHAR(255),
    logged_at         TIMESTAMPTZ
);
CREATE INDEX idx_activity_log_user ON activity_log(user_id);
CREATE INDEX idx_activity_log_time ON activity_log(logged_at);
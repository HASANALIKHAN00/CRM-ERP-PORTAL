ALTER TABLE customer_activity_details ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE customer_contacts ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE customer_monthly_devices ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE customer_project_tasks ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE customer_sample_testing ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE logistics_entry_items ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE logistics_comments ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
ALTER TABLE imei_details ADD COLUMN erpnext_name VARCHAR(140) UNIQUE;
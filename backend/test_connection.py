from erpnext_client import get_records

customers = get_records("Customer", limit=5)
print(f"Connected successfully. Sample of {len(customers)} customer(s):")
for c in customers:
    print(f"  - {c.get('name')}")
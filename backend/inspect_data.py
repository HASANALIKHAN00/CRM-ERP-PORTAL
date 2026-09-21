import json

data = json.load(open(r'src/app/data/actual-activity-records.json'))
print(f'Total records in dataset: {len(data)}')
print(f'Unique clients: {len(set(r["client"] for r in data))}')
print(f'Total USD Amount: ${sum(r["amount"] for r in data):,.2f}')

# Test Case 1: Phone Call on 2026-08-08 (PDF Verification)
pc = [r for r in data if r['date'] == '2026-08-08' and r['activityType'] == 'Phone Call']
print('\n[Test 1] 2026-08-08 Phone Call:')
print(f'  Count: {len(pc)}')
print(f'  Unique clients: {len(set(r["client"] for r in pc))}')
occ_h = set(r['hourSlot'] for r in pc)
print(f'  Occupied Hours: {len(occ_h)}, Empty Hours (24 - occ): {24 - len(occ_h)}')
occ_hh = set(r['halfHourSlot'] for r in pc)
print(f'  Occupied 30-min: {len(occ_hh)}, Empty 30-min (48 - occ): {48 - len(occ_hh)}')

# Test Case 2: Ahmed in Saudi Arabia
ah_sa = [r for r in data if r['salesperson'] == 'Ahmed' and r['country'] == 'Saudi Arabia']
print('\n[Test 2] Ahmed in Saudi Arabia:')
print(f'  Count: {len(ah_sa)}')
print(f'  Clients: {len(set(r["client"] for r in ah_sa))}')
print(f'  Amount: ${sum(r["amount"] for r in ah_sa):,.2f}')

# Test Case 3: Quotation
q = [r for r in data if r['activityType'] == 'Quotation']
print('\n[Test 3] Quotation:')
print(f'  Count: {len(q)}')
print(f'  Total Value: ${sum(r["amount"] for r in q):,.2f}')

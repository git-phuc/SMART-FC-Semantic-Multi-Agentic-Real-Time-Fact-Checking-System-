import csv

BACKUP = r'E:\Research\Code\NCKH\Multi-Agentic\Evaluation\eval-true-results -- backup.csv'

with open(BACKUP, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows: {len(rows)}")
print(f"Headers: {list(rows[0].keys())}")
print(f"First index: {rows[0].get('index')}")
print(f"Last index: {rows[-1].get('index')}")
empty = sum(1 for r in rows if not r.get('Decision', '').strip())
print(f"Empty Decision: {empty}")
filled = sum(1 for r in rows if r.get('Decision', '').strip())
print(f"Filled Decision: {filled}")

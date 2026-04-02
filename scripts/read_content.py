import csv
with open('Evaluation/vnexpress_crawled.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['index'] in ['5', '12']:
            print(f"--- {row['index']} ---\n{row['title']}\n{row['nội dung']}\n")

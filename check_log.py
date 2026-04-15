with open(r'C:\Users\Phucc\.gemini\antigravity\brain\01f71802-3229-4b00-8afa-a75464138193\.system_generated\logs\overview.txt', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'posetive-news-evaluation.csv.*?THẬT.*?THẬT', text, flags=re.DOTALL)
if matches:
    print('Found reference to positive dataset!')
    print(len(matches[-1]))
else:
    print('Not found in overview.txt')

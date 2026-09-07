import csv, re
csv_path = "automation-input/student-risk-watchlist.example.csv"
with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not any(field.strip() for field in row):
            continue
        if len(row) < 3:
            continue
        sc = row[0].strip()
        if sc.startswith("DEMO-"):
            course_raw = row[2]
            parts = [p.strip() for p in course_raw.replace(': ', '; ').split(';') if p.strip()]
            print('---', sc, '---')
            print(course_raw)
            print(parts)

import csv
from pathlib import Path

for path in [
    Path(r'..\야놀자\yanolja_concerts_tagged.csv'),
    Path(r'..\멜론티켓\melon_concerts_tagged.csv'),
]:
    print(f"\n=== {path.name} ===")
    with open(path, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    print(f"총 {len(rows)}행")
    print(f"컬럼: {list(rows[0].keys())[:6]}")
    first_col = list(rows[0].keys())[0]
    print(f"첫번째 컬럼명: '{first_col}'")
    vals = [r[first_col] for r in rows[:5]]
    print(f"샘플 값: {vals}")
    empty = [r for r in rows if not r[first_col].strip()]
    print(f"비어있는 행: {len(empty)}개")

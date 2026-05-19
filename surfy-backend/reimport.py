"""잘못 들어간 야놀자/멜론 데이터 삭제 후 재임포트."""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/event_db.sqlite3")
conn = sqlite3.connect(DB_PATH)

deleted = conn.execute("DELETE FROM events_event WHERE source IN ('yanolja', 'melon')").rowcount
conn.commit()
print(f"기존 데이터 삭제: {deleted}개")
conn.close()

# 재임포트
from import_concerts import main
main()

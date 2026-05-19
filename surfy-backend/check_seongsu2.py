import sqlite3
from datetime import date
conn = sqlite3.connect(r'data\event_db.sqlite3')
today = date.today().isoformat()

rows = conn.execute("""
    SELECT title, new_sub_category, thumbnail_url, new_mood_tags
    FROM events_event
    WHERE new_main_category='팝업스토어'
    AND (location LIKE '%성수%' OR region LIKE '%성수%')
    AND (end_date IS NULL OR end_date >= ?)
    ORDER BY thumbnail_url DESC
""", (today,)).fetchall()

print(f"현재 활성 성수 팝업: {len(rows)}개\n")
for r in rows:
    has_img = 'O' if r[2] else 'X'
    print(f"[{has_img}] [{r[1]}] {r[0][:45]}")
    print(f"     mood: {r[3]}")

conn.close()

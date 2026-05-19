import sqlite3, json
conn = sqlite3.connect(r'data\event_db.sqlite3')

print("=== 성수 팝업 mood 태그 샘플 ===")
rows = conn.execute("""
    SELECT title, new_mood_tags, mood_tags
    FROM events_event
    WHERE new_main_category='팝업스토어'
    AND (location LIKE '%성수%' OR region LIKE '%성수%')
    LIMIT 15
""").fetchall()
for r in rows:
    print(f"\n제목: {r[0][:40]}")
    print(f"  new_mood: {r[1]}")
    print(f"  mood:     {r[2]}")

conn.close()

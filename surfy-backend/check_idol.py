import sqlite3
conn = sqlite3.connect(r'data\event_db.sqlite3')

print("=== 공연 전체 목록 ===")
rows = conn.execute("""
    SELECT title, source, new_sub_category, music_genre
    FROM events_event
    WHERE new_main_category='공연'
    ORDER BY source
""").fetchall()
print(f"총 {len(rows)}개")
for r in rows:
    print(r)

conn.close()

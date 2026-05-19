import sqlite3
conn = sqlite3.connect(r'data\event_db.sqlite3')

print("=== 카테고리별 이벤트 수 ===")
rows = conn.execute("SELECT new_main_category, COUNT(*) FROM events_event GROUP BY new_main_category").fetchall()
for r in rows:
    print(r)

print("\n=== 공연 목록 (상위 20개) ===")
rows = conn.execute("SELECT title, music_genre, source FROM events_event WHERE new_main_category='공연' LIMIT 20").fetchall()
for r in rows:
    print(r)

print("\n=== 야놀자 공연 ===")
rows = conn.execute("SELECT title, music_genre FROM events_event WHERE source='yanolja' LIMIT 10").fetchall()
for r in rows:
    print(r)

conn.close()

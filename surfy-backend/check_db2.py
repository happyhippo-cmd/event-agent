import sqlite3
conn = sqlite3.connect(r'data\event_db.sqlite3')

print("=== 소스별 이벤트 수 ===")
rows = conn.execute("SELECT source, COUNT(*) FROM events_event GROUP BY source").fetchall()
for r in rows:
    print(r)

print("\n=== 야놀자 공연 목록 ===")
rows = conn.execute("SELECT id, title, new_main_category FROM events_event WHERE source='yanolja'").fetchall()
for r in rows:
    print(r)

print("\n=== 멜론티켓 공연 목록 ===")
rows = conn.execute("SELECT id, title, new_main_category FROM events_event WHERE source='melon'").fetchall()
for r in rows:
    print(r)

conn.close()

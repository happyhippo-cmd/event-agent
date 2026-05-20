import sqlite3
conn = sqlite3.connect(r'data\event_db.sqlite3')

print("=== 장르 분류 결과 샘플 ===")
rows = conn.execute("""
    SELECT title, music_genre FROM events_event
    WHERE new_main_category='공연'
    AND music_genre != '[]' AND music_genre != ''
    ORDER BY source
    LIMIT 20
""").fetchall()
for r in rows:
    print(f"  {r[1]:30} | {r[0][:50]}")

print("\n=== K-pop 아이돌 분류된 공연 ===")
rows = conn.execute("""
    SELECT title FROM events_event
    WHERE music_genre LIKE '%K-pop%' OR music_genre LIKE '%아이돌%'
""").fetchall()
print(f"총 {len(rows)}개")
for r in rows:
    print(f"  {r[0]}")

conn.close()

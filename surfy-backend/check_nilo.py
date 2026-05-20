import chromadb, sqlite3
from pathlib import Path

# DB에서 닐로 장르 확인
conn = sqlite3.connect(r'data\event_db.sqlite3')
row = conn.execute("SELECT id, title, music_genre FROM events_event WHERE title LIKE '%PANORAMA%'").fetchone()
print(f"DB 닐로: {row}")
conn.close()

# Chroma에서 닐로 텍스트 확인
client = chromadb.PersistentClient(path="data/chroma_db")
col = client.get_collection("event_places")
results = col.get(include=["documents", "metadatas"])
for m, d in zip(results["metadatas"], results["documents"]):
    if "PANORAMA" in m.get("title", ""):
        print(f"\nChroma 닐로:")
        print(f"  {d[:300]}")
        break

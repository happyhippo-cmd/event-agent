import chromadb
from pathlib import Path

CHROMA_PATH = Path("data/chroma_db")
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
col = client.get_collection("event_places")

# 닐로 vs IRENE 문서 비교
results = col.get(include=["documents", "metadatas"])
docs_by_title = {m["title"]: d for m, d in zip(results["metadatas"], results["documents"])}

targets = [
    "닐로 단독 콘서트 : 'PANORAMA'",
    "2026 IRENE ASIA TOUR [ I-WILL ] in SEOUL",
    "- The Trilogy I - 2026 SHINee WORLD VIII : [THE INVERT]",
    "RIIZE 1000 DAYS FAN PARTY [RIIZE OFFIICE]",
    "2026 I.O.I Concert Tour: LOOP in SEOUL",
]

print("=== 임베딩 텍스트 확인 ===")
for title in targets:
    for stored_title, doc in docs_by_title.items():
        if title[:20] in stored_title:
            print(f"\n[{stored_title[:50]}]")
            print(f"  {doc[:200]}")
            break

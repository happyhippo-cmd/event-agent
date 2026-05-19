import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.vector_store import query_events

print("=== '아이돌 콘서트' 벡터 검색 top 20 ===")
results = query_events("아이돌 콘서트", top_k=20)
for r in results:
    print(f"  {r['similarity']:.3f} | {r['title']} ({r['category']})")

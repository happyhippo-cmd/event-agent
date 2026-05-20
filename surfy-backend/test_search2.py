"""검색 후보 상위 10개 확인."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import search_events_from_db, _merge_with_vector_search

query = "아이돌 콘서트 추천좀"
results = search_events_from_db(query=query, mood="", limit=20)
merged = _merge_with_vector_search(results, query=query, mood="", limit=20)

print(f"=== LLM에 전달되는 상위 10개 ===")
for i, r in enumerate(merged[:10], 1):
    print(f"{i}. {r.get('title')} | genre={r.get('music_genre')}")

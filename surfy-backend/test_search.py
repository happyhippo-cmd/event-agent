"""검색 테스트."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import search_events_from_db, _merge_with_vector_search, _detect_category

query = "아이돌 콘서트 추천좀"
print(f"=== 키워드 검색: '{query}' ===")
results = search_events_from_db(query=query, mood="", limit=5)
print(f"결과 {len(results)}개:")
for r in results:
    print(f"  - {r.get('title')} ({r.get('new_main_category')})")

print(f"\n=== 벡터 병합 후 ===")
merged = _merge_with_vector_search(results, query=query, mood="", limit=10)
print(f"결과 {len(merged)}개:")
for r in merged:
    print(f"  - {r.get('title')} ({r.get('new_main_category')})")

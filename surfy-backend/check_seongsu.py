import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import search_events_from_db, _merge_with_vector_search

query = "성수 근처 팝업 추천"
results = search_events_from_db(query=query, mood="", limit=20)
merged = _merge_with_vector_search(results, query=query, mood="", limit=20)

print(f"=== LLM 후보 상위 10개 ===")
for i, r in enumerate(merged[:10], 1):
    thumb = r.get('thumbnail_url') or ''
    has_thumb = 'O' if thumb and 'http' in thumb else 'X'
    mood = r.get('new_mood_tags') or r.get('mood_tags') or '[]'
    sub = r.get('new_sub_category') or ''
    print(f"{i}. {has_thumb} [{sub}] {r.get('title')[:40]}")
    print(f"   mood: {mood[:80]}")

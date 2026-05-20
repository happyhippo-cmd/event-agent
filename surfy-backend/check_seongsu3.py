import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import search_events_from_db, _merge_with_vector_search

query = "성수 근처 팝업 추천"
results = search_events_from_db(query=query, mood="", limit=20)

print(f"=== 스코어링 후 상위 10개 ===")
for i, r in enumerate(results[:10], 1):
    has_img = 'O' if r.get('thumbnail_url') else 'X'
    mood = r.get('new_mood_tags') or r.get('mood_tags') or '[]'
    sub = r.get('new_sub_category') or ''
    title = r.get('title', '')
    try:
        print(f"{i}. [{has_img}] [{sub}] {title[:40]}")
        print(f"   mood: {mood[:80]}")
    except UnicodeEncodeError:
        print(f"{i}. [{has_img}] (인코딩 오류)")

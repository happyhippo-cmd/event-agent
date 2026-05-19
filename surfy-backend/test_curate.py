"""실제 curate_events_with_llm 호출 확인."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import search_events_from_db, _merge_with_vector_search
import apps.agents.workers.event.agent as agent_module

# curate 함수 모킹해서 raw 응답 확인
original_curate = agent_module.curate_events_with_llm

def debug_curate(events, query, taste_context, history, top_k):
    from apps.agents.workers.event.agent import (
        _event_attr, _date_range, _listish, _flatten_terms,
    )
    from apps.agents.utils import get_openai_client
    import json

    client = get_openai_client()
    event_summaries = []
    for idx, event in enumerate(events[:10], 1):
        event_summaries.append({
            "index": idx,
            "title": _event_attr(event, "title"),
            "location": _event_attr(event, "location"),
            "date": _date_range(event),
            "category": _event_attr(event, "new_main_category"),
            "subcategory": _event_attr(event, "new_sub_category"),
            "description": str(_event_attr(event, "description") or "")[:200],
            "hashtags": _listish(_event_attr(event, "hashtags"))[:5],
        })

    # 원본 호출
    result = original_curate(events, query, taste_context, history, top_k)
    print(f"\n=== 최종 결과 ({len(result) if result else 'None'}개) ===")
    if result:
        for r in result:
            print(f"  - {r['title']}: {r.get('reason', '')[:100]}")
    return result

agent_module.curate_events_with_llm = debug_curate

query = "아이돌 콘서트 추천좀"
taste_context = {"event_type_keywords": ["콘서트"]}
mood = "콘서트"

# API와 동일한 경로 시뮬레이션
from apps.agents.workers.event.agent import _event_mood_from_taste
mood = _event_mood_from_taste(taste_context)
print(f"mood (from taste): '{mood}'")

results = search_events_from_db(query=query, mood=mood, limit=20)
events = _merge_with_vector_search(results, query=query, mood=mood, limit=20)
print(f"\n=== 후보 10개 ===")
for i, e in enumerate(events[:10], 1):
    print(f"{i}. {e.get('title')}")

curated = debug_curate(events, query, taste_context, [], top_k=3)

"""LLM 응답 직접 확인."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(".env")

from apps.agents.workers.event.agent import (
    search_events_from_db, _merge_with_vector_search,
    _event_attr, _date_range, _listish,
)
from apps.agents.utils import get_openai_client

query = "아이돌 콘서트 추천좀"
results = search_events_from_db(query=query, mood="", limit=20)
events = _merge_with_vector_search(results, query=query, mood="", limit=20)[:10]

event_summaries = []
for idx, event in enumerate(events, 1):
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

print("=== 후보 ===")
for s in event_summaries:
    print(f"{s['index']}. {s['title']}")

client = get_openai_client()
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.3,
    messages=[
        {"role": "system", "content": "너는 K-pop 음악 산업 전문가다. 아티스트/그룹명을 보고 아이돌(K-pop 보이/걸그룹), 인디, 솔로 싱어송라이터, 트로트, 발라드, 록밴드 중 어디에 속하는지 분류한다."},
        {"role": "user", "content": f"아래 콘서트 후보들을 각각 분류해줘. 모르는 건 '모름'으로 표시:\n\n" + "\n".join(f"{s['index']}. {s['title']}" for s in event_summaries) + "\n\nJSON 형식으로 답해: [{\"index\": 1, \"분류\": \"아이돌|인디|솔로|트로트|발라드|록|모름\", \"이유\": \"...\"}]"}
    ],
    response_format={"type": "json_object"},
)
print("\n=== LLM 분류 결과 ===")
print(resp.choices[0].message.content)

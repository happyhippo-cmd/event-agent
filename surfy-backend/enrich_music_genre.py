"""music_genre 결측/분류 미정인 공연을 LLM이 title·description 보고 재태깅.

대상: new_main_category='공연' AND music_genre IN ('[]', '["기타"]', '["모름"]')
배치: 10건씩 묶어서 LLM 1회 호출 → 비용·시간 절감
실패/판단 불가는 ["기타"] 유지 (강제 분류 방지)
"""
import json
import os
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

load_dotenv(".env")

from apps.agents.utils import get_openai_client

KNOWN_GENRES = [
    "K-pop 아이돌", "인디", "해외 아티스트", "솔로 가수",
    "록/밴드", "J-pop", "트로트", "재즈", "EDM", "힙합", "기타",
]

BATCH = 10
DRY_RUN = False  # True면 DB 안 건드림

today = date.today().isoformat()
conn = sqlite3.connect("data/event_db.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute(f"""
  SELECT id, title, description, sub_category
  FROM events_event
  WHERE new_main_category = '공연'
    AND (end_date IS NULL OR end_date >= '{today}')
    AND (music_genre IS NULL OR music_genre IN ('[]', '["기타"]', '["모름"]'))
""").fetchall()

print(f"대상: {len(rows)}건")
client = get_openai_client()
if client is None:
    print("ERR: openai client 없음")
    sys.exit(1)

system = (
    "너는 K-pop·인디·재즈 등 한국 공연 시장의 아티스트 장르를 판단하는 분류기다.\n"
    f"가능한 장르: {', '.join(KNOWN_GENRES)}.\n"
    "사전 지식으로 아티스트명을 보고 장르를 단정할 수 있을 때만 분류하라.\n"
    "확신 없으면 '기타'로 둬라 (틀리는 것보다 보류가 낫다).\n"
    "여러 장르가 섞이면 가장 핵심적인 하나만 고른다."
)

total_updated = 0
total_kept_etc = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i + BATCH]
    items = [
        {
            "id": r["id"],
            "title": (r["title"] or "")[:100],
            "description": (r["description"] or "")[:200],
            "sub_category": r["sub_category"] or "",
        }
        for r in batch
    ]
    user = (
        "다음 공연 목록을 장르로 분류하세요. 각 행에 대해 KNOWN_GENRES 중 하나를 골라요.\n"
        "JSON 배열로만 답해. 형식: [{\"id\": 1, \"genre\": \"K-pop 아이돌\"}, ...]\n\n"
        + json.dumps(items, ensure_ascii=False, indent=2)
    )
    try:
        resp = client.chat.completions.create(
            model=os.getenv("EVENT_AGENT_MODEL", "gpt-4o-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                # JSON object 보장을 위해 wrapper key 사용 — 아래 파싱에서 풀어준다
                {"role": "user", "content": user + '\n\nWrap your array under a "results" key: {"results": [...]}'},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        results = data.get("results") or data.get("classifications") or []
    except Exception as e:
        print(f"  배치 {i//BATCH+1} 실패: {e}")
        continue

    updates = []
    for item in results:
        rid = item.get("id")
        genre = item.get("genre")
        if not isinstance(rid, int) or genre not in KNOWN_GENRES:
            continue
        if genre == "기타":
            total_kept_etc += 1
            continue
        new_mg = json.dumps([genre], ensure_ascii=False)
        updates.append((new_mg, rid))

    if updates and not DRY_RUN:
        cur.executemany("UPDATE events_event SET music_genre = ? WHERE id = ?", updates)
        conn.commit()
    total_updated += len(updates)
    print(f"  배치 {i//BATCH+1} ({len(batch)}건): 재분류 {len(updates)}건, '기타' 유지 {sum(1 for x in results if x.get('genre') == '기타')}건")

print(f"\n전체: 재분류 {total_updated}건 / '기타' 유지 {total_kept_etc}건")
conn.close()

"""공연 카테고리의 hashtags 결측을 LLM이 title·description 보고 생성.

대상: new_main_category='공연' AND hashtags IS NULL/''/' []'
형식: ["#태그1", "#태그2", ...] (깔끔한 JSON 배열)
배치: 10건씩
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

BATCH = 10
today = date.today().isoformat()

conn = sqlite3.connect("data/event_db.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute(f"""
  SELECT id, title, description, sub_category, music_genre
  FROM events_event
  WHERE new_main_category = '공연'
    AND (end_date IS NULL OR end_date >= '{today}')
    AND (hashtags IS NULL OR hashtags = '' OR hashtags = '[]')
""").fetchall()

print(f"대상: {len(rows)}건")
client = get_openai_client()

system = (
    "너는 공연 정보로부터 검색·필터에 유용한 hashtags를 만든다.\n"
    "- 3~5개. 짧고 명확한 단어.\n"
    "- 아티스트명·장르·키워드(예: 콘서트, 단독, 팬미팅, 내한, 페스티벌) 우선.\n"
    "- 추측 금지 — title·description에 없는 사실은 만들지 마.\n"
    "- 각 태그는 #로 시작. 한글 또는 영어. 공백 없이.\n"
    "- 형식: [\"#태그1\", \"#태그2\", ...] JSON 배열."
)

updated = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i + BATCH]
    items = [
        {
            "id": r["id"],
            "title": (r["title"] or "")[:120],
            "description": (r["description"] or "")[:200],
            "sub_category": r["sub_category"] or "",
            "music_genre": r["music_genre"] or "",
        }
        for r in batch
    ]
    user = (
        '다음 공연 목록 각각에 대해 hashtags 3~5개를 생성하세요.\n'
        'JSON 객체로 답하세요. 형식: {"results": [{"id": 1, "tags": ["#X", "#Y"]}, ...]}\n\n'
        + json.dumps(items, ensure_ascii=False, indent=2)
    )
    try:
        resp = client.chat.completions.create(
            model=os.getenv("EVENT_AGENT_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        results = data.get("results") or []
    except Exception as e:
        print(f"  배치 {i//BATCH+1} 실패: {e}")
        continue

    upds = []
    for item in results:
        rid = item.get("id")
        tags = item.get("tags") or []
        if not isinstance(rid, int) or not isinstance(tags, list) or not tags:
            continue
        # # prefix 보장
        clean = [t if t.startswith("#") else f"#{t}" for t in tags if t]
        if clean:
            upds.append((json.dumps(clean, ensure_ascii=False), rid))

    if upds:
        cur.executemany("UPDATE events_event SET hashtags = ? WHERE id = ?", upds)
        conn.commit()
    updated += len(upds)
    print(f"  배치 {i//BATCH+1} ({len(batch)}건): {len(upds)}건 생성")

print(f"\n전체: {updated}건 hashtags 생성")
conn.close()

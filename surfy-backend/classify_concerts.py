"""
공연 이벤트 아티스트 장르 자동 분류 (배치 LLM)
- music_genre가 비어있는 공연을 대상으로 LLM이 아티스트명 보고 분류
- 결과를 music_genre 필드에 저장 후 벡터 DB 재빌드
실행: python classify_concerts.py
"""

import json
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "data" / "event_db.sqlite3"
BATCH_SIZE = 20  # 한 번에 LLM에 보낼 개수

SYSTEM_PROMPT = """너는 한국 음악 산업 전문가다.
공연 제목을 보고 아티스트/그룹의 장르를 분류해.
반드시 아래 중 하나만 사용해:
- "K-pop 아이돌": K-pop 보이/걸그룹 (예: SHINee, NCT, RIIZE, I.O.I, aespa, 2AM, 규현, 재현, 박지훈 등)
- "인디": 인디 밴드 또는 인디 싱어송라이터 (예: 닐로, 문없는집, 검정치마)
- "솔로 가수": 메이저 솔로 가수/발라더 (예: 이무진, 임슬옹, 강승원)
- "트로트": 트로트 가수
- "재즈": 재즈 아티스트
- "록/밴드": 록밴드
- "J-pop": 일본 아티스트
- "해외 아티스트": 한국/일본 외 해외 아티스트
- "기타": 위 분류에 해당 없음
- "모름": 판단 불가

팬미팅(FANMEETING, FAN CONCERT, FAN PARTY, FAN-CON) 이름이 붙은 공연은 대부분 K-pop 아이돌이다."""


def classify_batch(client: OpenAI, titles: list[tuple[int, str]]) -> dict[int, str]:
    """이벤트 ID + 제목 배치를 분류해서 {id: genre} 반환."""
    numbered = "\n".join(f"{i+1}. [ID:{eid}] {title}" for i, (eid, title) in enumerate(titles))
    prompt = f"아래 공연들을 분류해줘:\n\n{numbered}\n\n각 항목에 대해 ID와 분류 결과를 JSON 배열로 반환:\n[{{\"id\": 123, \"genre\": \"K-pop 아이돌\"}}]"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        results = data.get("results") or data.get("classifications") or []
        if not results:
            # 최상위가 배열인 경우
            for v in data.values():
                if isinstance(v, list):
                    results = v
                    break
        return {int(item["id"]): item["genre"] for item in results if "id" in item and "genre" in item}
    except Exception as e:
        print(f"  분류 실패: {e}")
        return {}


def main():
    conn = sqlite3.connect(DB_PATH)
    client = OpenAI()

    # 공연 중 music_genre가 비어있는 것만 대상
    rows = conn.execute("""
        SELECT id, title FROM events_event
        WHERE new_main_category = '공연'
        AND (music_genre IS NULL OR music_genre = '[]' OR music_genre = '')
    """).fetchall()

    print(f"분류 대상: {len(rows)}개 공연\n")

    total_updated = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        print(f"배치 {i//BATCH_SIZE + 1}: {len(batch)}개 처리 중...")

        results = classify_batch(client, batch)

        for event_id, genre in results.items():
            genre_json = json.dumps([genre], ensure_ascii=False)
            conn.execute(
                "UPDATE events_event SET music_genre = ? WHERE id = ?",
                (genre_json, event_id),
            )
            total_updated += 1

        conn.commit()
        print(f"  → {len(results)}개 분류 완료")

        # 샘플 출력
        for event_id, title in batch[:3]:
            genre = results.get(event_id, "분류 실패")
            print(f"    [{event_id}] {title[:40]} → {genre}")
        print()

    conn.close()
    print(f"\n총 {total_updated}개 업데이트 완료")
    print("\n벡터 DB 재빌드 중...")

    from apps.agents.workers.event.vector_store import build_event_vector_db
    import os, sys
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("EVENT_DB_PATH", str(BASE_DIR / "data" / "event_db.sqlite3"))
    count = build_event_vector_db(reset=True)
    print(f"벡터 DB 재빌드 완료: {count}개")


if __name__ == "__main__":
    main()

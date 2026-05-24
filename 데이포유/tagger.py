"""
태깅 스크립트 — popup_stores_tagged_v2 형식으로 태깅
사용법:
    python tagger.py --input 경기/popup_stores.csv --output 경기/popup_stores_tagged.csv
"""

import csv
import json
import time
import argparse
from pathlib import Path
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """너는 팝업스토어·전시·공연 이벤트 데이터 태거야.
이벤트 정보를 보고 아래 JSON 형식으로만 답해. 설명 없이 JSON만 출력해.

{
  "region": "지역명 (성수/홍대/강남/이태원/한남/명동/압구정/청담/잠실/건대/홍대/신촌/여의도/종로/인사동/수원/분당/판교/일산/부천/인천/송도 중 하나, 없으면 빈 문자열)",
  "new_main_category": "팝업스토어 또는 전시 또는 공연 또는 페스티벌 또는 박람회",
  "new_sub_category": "세부 카테고리 (예: 패션, 뷰티, 식음료, 캐릭터, 아트, 음악 등)",
  "exhibition_type": "전시일 경우 유형 (개인전/단체전/브랜드전시/체험전시 등), 아니면 빈 문자열",
  "commerciality": "비상업적 또는 브랜드 또는 쇼핑중심 또는 체험중심 또는 팬덤형",
  "new_mood_tags": ["분위기 태그 (트렌디한/감성적인/힙한/귀여운/럭셔리한/아기자기한/이색적인/포토제닉한 등) 최대 3개"],
  "new_audience_tags": ["대상 태그 (20대/30대/커플/친구/가족/혼자/외국인/팬덤 등) 최대 3개"]
}"""


def tag_event(row: dict) -> dict:
    prompt = f"""제목: {row.get('title', '')}
장소: {row.get('location', '')}
기간: {row.get('date', '')}
설명: {row.get('description', '')[:300]}
해시태그: {row.get('hashtags', '')}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="입력 CSV 경로")
    parser.add_argument("--output", required=True, help="출력 CSV 경로")
    parser.add_argument("--delay", type=float, default=0.3, help="요청 간 딜레이(초)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    with open(input_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"{len(rows)}개 이벤트 태깅 시작...")

    tagged_rows = []
    for i, row in enumerate(rows, 1):
        try:
            tags = tag_event(row)
            row.update({
                "region": tags.get("region", ""),
                "new_main_category": tags.get("new_main_category", ""),
                "new_sub_category": tags.get("new_sub_category", ""),
                "exhibition_type": tags.get("exhibition_type", ""),
                "commerciality": tags.get("commerciality", ""),
                "new_mood_tags": json.dumps(tags.get("new_mood_tags", []), ensure_ascii=False),
                "new_audience_tags": json.dumps(tags.get("new_audience_tags", []), ensure_ascii=False),
            })
        except Exception as e:
            print(f"  [{i}] 실패: {e}")
            row.update({
                "region": "", "new_main_category": "", "new_sub_category": "",
                "exhibition_type": "", "commerciality": "",
                "new_mood_tags": "[]", "new_audience_tags": "[]",
            })

        tagged_rows.append(row)

        if i % 10 == 0:
            print(f"  {i}/{len(rows)} 완료")
        time.sleep(args.delay)

    fieldnames = list(rows[0].keys())
    for f in ["region", "new_main_category", "new_sub_category", "exhibition_type", "commerciality", "new_mood_tags", "new_audience_tags"]:
        if f not in fieldnames:
            fieldnames.append(f)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tagged_rows)

    print(f"\n완료! → {output_path}")


if __name__ == "__main__":
    main()

"""
멜론 티켓 콘서트 크롤러
API: https://ticket.melon.com/performance/ajax/prodList.json

중복 제거 기준:
  1. 서울/경기/인천 지역만 수집
  2. stateFlg가 SS0300(마감)/SS0400(종료)이거나 reserveEndDt가 오늘 이전이면 제외
  3. 같은 장소+날짜 → reserveEndDt 가장 늦은 것 1개만 유지
결과: melon_concerts.json, melon_concerts.csv
"""

import csv
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

import requests

API_URL = "https://ticket.melon.com/performance/ajax/prodList.json"
CDN_BASE = "https://cdnticket.melon.co.kr"
DETAIL_BASE = "https://ticket.melon.com/performance/index.htm?prodId="

TARGET_REGIONS = ["서울", "경기", "인천"]

EXPIRED_FLAGS = {"SS0300", "SS0400"}  # 예매마감, 공연종료

SORT_TYPES = ["HIT", "OPEN", "RECENT"]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Referer": "https://ticket.melon.com/concert/index.htm?genreType=GENRE_CON",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
})


def parse_date(period_info: str):
    """'2026.06.06 - 2026.06.07' → '2026-06-06~ 2026-06-07'"""
    if not period_info:
        return ""
    parts = [p.strip().replace(".", "-") for p in period_info.split("-")]
    start = parts[0] if parts else ""
    end = parts[1] if len(parts) > 1 else ""
    if end and end != start:
        return f"{start}~ {end}"
    return start


def parse_reserve_end_dt(sale_type_json_str: str) -> datetime | None:
    """saleTypeJson에서 가장 늦은 reserveEndDt 추출"""
    if not sale_type_json_str:
        return None
    try:
        data = json.loads(sale_type_json_str) if isinstance(sale_type_json_str, str) else sale_type_json_str
        latest = None
        for poc in data.get("data", {}).get("list", []):
            for sale in poc.get("saleTypeCodeList", []):
                end_str = sale.get("reserveEndDt")
                if end_str:
                    try:
                        dt = datetime.strptime(str(end_str), "%Y%m%d%H%M%S")
                        if latest is None or dt > latest:
                            latest = dt
                    except ValueError:
                        pass
        return latest
    except Exception:
        return None


def is_target_region(region_name: str, place_name: str) -> bool:
    combined = f"{region_name} {place_name}"
    return any(r in combined for r in TARGET_REGIONS)


def is_expired(state_flg: str, reserve_end_dt: datetime | None) -> bool:
    if state_flg in EXPIRED_FLAGS:
        return True
    if reserve_end_dt and reserve_end_dt < datetime.now():
        return True
    return False


def fetch_concerts(sort_type: str) -> list[dict]:
    params = {
        "commCode": "",
        "sortType": sort_type,
        "perfGenreCode": "GENRE_CON_ALL",
        "perfThemeCode": "",
        "filterCode": "FILTER_ALL",
        "v": "1",
    }
    resp = SESSION.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def to_row(item: dict, reserve_end_dt: datetime | None) -> dict:
    prod_id = str(item.get("prodId", ""))
    date_str = parse_date(item.get("periodInfo", "").strip())
    poster_img = item.get("posterImg", "").strip()
    description = item.get("perfDescr") or item.get("summary") or item.get("subTitle") or ""

    return {
        "seq": prod_id,
        "source": "melon",
        "title": item.get("title", "").strip(),
        "location": item.get("placeName", "").strip(),
        "region_name": item.get("regionName", "").strip(),
        "date": date_str,
        "reserve_end_dt": reserve_end_dt.strftime("%Y-%m-%d %H:%M") if reserve_end_dt else "",
        "thumbnail_url": f"{CDN_BASE}{poster_img}" if poster_img else "",
        "detail_url": f"{DETAIL_BASE}{prod_id}",
        "store_url": f"{DETAIL_BASE}{prod_id}",
        "description": str(description)[:500].strip() if description else "",
        "hashtags": "[]",
        "main_category": "공연",
        "sub_category": "콘서트",
        "detail_category": "",
        "music_genre": "[]",
        "mood_tags": "[]",
        "activity_tags": "[]",
        "theme_tags": "[]",
        "space_tags": "[]",
        "emotion_tags": "[]",
        "audience_tags": "[]",
        "vector_summary": "",
    }


def main():
    parser = argparse.ArgumentParser(description="멜론 티켓 콘서트 크롤러")
    parser.add_argument("--out", default=".", help="결과 저장 디렉토리")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # prod_id → (row, reserve_end_dt)
    all_items: dict[str, tuple[dict, datetime | None]] = {}
    # (location, date) → (prod_id, reserve_end_dt)  — 중복 제거용
    dedup: dict[tuple, tuple[str, datetime | None]] = {}

    skipped_region = skipped_expired = skipped_dup = 0

    for sort_type in SORT_TYPES:
        print(f"[수집] sortType={sort_type}")
        items = fetch_concerts(sort_type)
        print(f"  → {len(items)}개 항목")

        for item in items:
            prod_id = str(item.get("prodId", ""))
            if not prod_id:
                continue

            # 1. 지역 필터
            if not is_target_region(item.get("regionName", ""), item.get("placeName", "")):
                skipped_region += 1
                continue

            # 2. 예매 종료 여부
            reserve_end_dt = parse_reserve_end_dt(item.get("saleTypeJson", ""))
            if is_expired(item.get("stateFlg", ""), reserve_end_dt):
                skipped_expired += 1
                continue

            # 3. 중복 처리 (같은 장소+날짜)
            date_str = parse_date(item.get("periodInfo", "").strip())
            dup_key = (item.get("placeName", "").strip(), date_str)

            if dup_key in dedup:
                existing_id, existing_end = dedup[dup_key]
                # reserveEndDt 더 늦은 것으로 교체
                if reserve_end_dt and (existing_end is None or reserve_end_dt > existing_end):
                    del all_items[existing_id]
                    dedup[dup_key] = (prod_id, reserve_end_dt)
                    all_items[prod_id] = (to_row(item, reserve_end_dt), reserve_end_dt)
                else:
                    skipped_dup += 1
                continue

            dedup[dup_key] = (prod_id, reserve_end_dt)
            all_items[prod_id] = (to_row(item, reserve_end_dt), reserve_end_dt)

        time.sleep(0.3)

    items_list = [row for row, _ in all_items.values()]

    print(f"\n=== 수집 결과 ===")
    print(f"  수집: {len(items_list)}개")
    print(f"  제외 (지역): {skipped_region}개")
    print(f"  제외 (예매마감): {skipped_expired}개")
    print(f"  제외 (중복): {skipped_dup}개")

    json_path = out_dir / "melon_concerts.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items_list, f, ensure_ascii=False, indent=2)
    print(f"\n  → JSON 저장: {json_path}")

    if items_list:
        csv_path = out_dir / "melon_concerts.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=items_list[0].keys())
            writer.writeheader()
            writer.writerows(items_list)
        print(f"  → CSV 저장: {csv_path}")

    print("완료!")


if __name__ == "__main__":
    main()

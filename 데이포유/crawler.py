"""
dayforyou.com 팝업스토어 크롤러
- /getScheduleList 에서 전체 목록 수집
- 각 항목: 팝업명, 장소, 기간, 썸네일 URL, 상세 URL
- 결과: popup_stores.json, popup_stores.csv
- 이미지 다운로드: --images 플래그 사용
"""

import requests
import json
import csv
import os
import re
import time
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

BASE_URL = "https://dayforyou.com"
LIST_URL = f"{BASE_URL}/getScheduleList"

SESSION = requests.Session()
SESSION.verify = False  # SSL 인증서 오류 우회
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
})

# SSL 경고 억제
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_list() -> list[dict]:
    """목록 페이지에서 팝업스토어 기본 정보 파싱"""
    print(f"[1/2] 목록 페이지 수집 중: {LIST_URL}")
    resp = SESSION.get(LIST_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    boxes = soup.select("li.schedule_box")
    print(f"     → {len(boxes)}개 항목 발견")

    for box in boxes:
        seq_match = re.search(r"schedule_(\d+)", box.get("id", ""))
        seq = seq_match.group(1) if seq_match else ""

        img_tag = box.select_one("img.thumbnail_img")
        thumbnail = img_tag["src"] if img_tag else ""

        title_tag = box.select_one("li.popupTitle b")
        title = title_tag.get_text(strip=True) if title_tag else ""

        loc_tag = box.select_one("li.popupLocation p")
        if loc_tag:
            # 복사 버튼 텍스트 제거
            for btn in loc_tag.find_all("button"):
                btn.decompose()
            location = loc_tag.get_text(strip=True)
        else:
            location = ""

        date_tag = box.select_one("p.popupDate")
        date = " ".join(date_tag.get_text().split()) if date_tag else ""

        items.append({
            "seq": seq,
            "title": title,
            "location": location,
            "date": date,
            "thumbnail_url": thumbnail,
            "detail_url": f"{BASE_URL}/getDetail?scheduleSeq={seq}" if seq else "",
        })

    return items


def fetch_detail(seq: str) -> dict:
    """상세 페이지에서 추가 정보(설명, 해시태그) 파싱"""
    url = f"{BASE_URL}/getDetail?scheduleSeq={seq}"
    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        detail_div = soup.select_one(".schedule_detail")
        description = detail_div.get_text(" ", strip=True) if detail_div else ""

        hashtags = [tag.get_text(strip=True) for tag in soup.select(".hashtag, .hash-tag, [class*='hash']")]

        return {"description": description, "hashtags": hashtags}
    except Exception as e:
        return {"description": "", "hashtags": [], "_error": str(e)}


def download_image(url: str, save_dir: Path, filename: str) -> str:
    """이미지 다운로드, 저장 경로 반환"""
    if not url:
        return ""
    try:
        resp = SESSION.get(url, timeout=15, stream=True)
        resp.raise_for_status()
        ext = ".jpg"
        ct = resp.headers.get("Content-Type", "")
        if "png" in ct:
            ext = ".png"
        elif "gif" in ct:
            ext = ".gif"
        elif "webp" in ct:
            ext = ".webp"
        path = save_dir / f"{filename}{ext}"
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return str(path)
    except Exception as e:
        return f"ERROR: {e}"


def save_json(data: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → JSON 저장: {path}")


def save_csv(data: list[dict], path: str):
    if not data:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  → CSV 저장: {path}")


def main():
    parser = argparse.ArgumentParser(description="dayforyou.com 팝업스토어 크롤러")
    parser.add_argument("--detail", action="store_true", help="상세 페이지도 수집 (느림)")
    parser.add_argument("--images", action="store_true", help="썸네일 이미지 다운로드")
    parser.add_argument("--limit", type=int, default=0, help="수집 개수 제한 (0=전체)")
    parser.add_argument("--delay", type=float, default=0.3, help="요청 간 딜레이(초)")
    parser.add_argument("--out", default=".", help="결과 저장 디렉토리")
    parser.add_argument("--region", type=str, default="", help="지역 필터 (예: 서울, 부산, 경기)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 목록 수집
    items = fetch_list()
    if args.region:
        before = len(items)
        items = [x for x in items if args.region in x["location"]]
        print(f"     → 지역 필터 '{args.region}': {before}개 → {len(items)}개")
    if args.limit:
        items = items[: args.limit]

    # 2. 이미지 다운로드
    if args.images:
        img_dir = out_dir / "images"
        img_dir.mkdir(exist_ok=True)
        print(f"\n[이미지] {len(items)}개 다운로드 중...")
        for i, item in enumerate(items, 1):
            local_path = download_image(item["thumbnail_url"], img_dir, item["seq"])
            item["thumbnail_local"] = local_path
            if i % 50 == 0:
                print(f"  {i}/{len(items)} 완료")
            time.sleep(args.delay)

    # 3. 상세 페이지 수집 (선택)
    if args.detail:
        print(f"\n[2/2] 상세 페이지 {len(items)}개 수집 중... (딜레이: {args.delay}s)")
        for i, item in enumerate(items, 1):
            detail = fetch_detail(item["seq"])
            item.update(detail)
            if i % 20 == 0:
                print(f"  {i}/{len(items)} 완료")
            time.sleep(args.delay)
    else:
        print("\n[2/2] 상세 수집 생략 (--detail 플래그로 활성화)")

    # 4. 저장
    print(f"\n[저장] {len(items)}개 항목")
    save_json(items, out_dir / "popup_stores.json")
    save_csv(items, out_dir / "popup_stores.csv")
    print("\n완료!")


if __name__ == "__main__":
    main()

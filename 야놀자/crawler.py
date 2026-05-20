"""
야놀자 NOL 콘서트 페이지 크롤러 (Playwright)
https://nol.yanolja.com/ticket/genre/concert

흐름: 지역 선택(서울/경기) → 장르 탭 클릭 → 카드 수집 반복
결과: yanolja_concerts.json, yanolja_concerts.csv
"""

import re
import csv
import json
import asyncio
import argparse
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "https://nol.yanolja.com"
CONCERT_URL = f"{BASE_URL}/ticket/genre/concert"

TARGET_REGIONS = ["서울", "경기"]
TARGET_GENRES = ["랩/힙합", "내한공연", "페스티벌", "팬클럽/팬미팅", "인디"]


def parse_date(d: str) -> str:
    parts = d.strip().split(".")
    if len(parts) == 3:
        return f"20{parts[0]}-{parts[1]}-{parts[2]}"
    return d.strip()


def parse_aria_label(label: str) -> dict:
    date_match = re.search(r"공연 기간:\s*(.+)$", label)
    date_str = date_match.group(1).strip() if date_match else ""

    rest = label[: date_match.start()].rstrip(", ") if date_match else label
    parts = rest.rsplit(", ", 1)
    title = parts[0].strip()
    location = parts[1].strip() if len(parts) > 1 else ""

    start_date = end_date = ""
    if date_str:
        dates = [d.strip() for d in date_str.split("~")]
        start_date = parse_date(dates[0]) if dates else ""
        end_date = parse_date(dates[1]) if len(dates) > 1 else start_date

    return {"title": title, "location": location, "start_date": start_date, "end_date": end_date}


def extract_source_id(href: str) -> str:
    m = re.search(r"/products/(\d+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/ticket/(\d+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/promotions/(\d+)", href)
    if m:
        return f"promo_{m.group(1)}"
    return ""


async def select_region(page, region: str):
    """지역 선택 모달 열고 지역 클릭 (JS 직접 실행)"""
    print(f"  [지역] {region} 선택")

    # 지역 버튼 클릭 (joint-chip__control 클래스)
    opened = await page.evaluate("""
        () => {
            const btn = [...document.querySelectorAll('button')]
                .find(b => b.classList.contains('joint-chip__control'));
            if (btn) { btn.click(); return true; }
            return false;
        }
    """)
    if not opened:
        print("  [경고] 지역 버튼을 찾지 못했습니다")
        return
    await page.wait_for_selector("text=지역 선택", timeout=5000)

    # 모달에서 해당 지역 span 클릭
    clicked = await page.evaluate(f"""
        () => {{
            const span = [...document.querySelectorAll('span')]
                .find(s => s.textContent.trim() === '{region}');
            if (span) {{ span.click(); return true; }}
            return false;
        }}
    """)
    if not clicked:
        print(f"  [경고] '{region}' 항목을 찾지 못했습니다")
    await page.wait_for_timeout(1000)


async def collect_visible_cards(page, genre: str, region: str, results: dict):
    """현재 보이는 카드 수집"""
    all_links = await page.locator("a[aria-label*='공연 기간:']").all()
    visible = [lnk for lnk in all_links if await lnk.is_visible()]
    print(f"    → {len(visible)}개 카드")

    for link in visible:
        label = await link.get_attribute("aria-label") or ""
        href = await link.get_attribute("href") or ""

        source_id = extract_source_id(href)
        if not source_id or source_id in results:
            continue

        parsed = parse_aria_label(label)

        img = link.locator("img").first
        thumbnail_url = ""
        if await img.count():
            thumbnail_url = await img.get_attribute("src") or ""

        detail_url = href if href.startswith("http") else BASE_URL + href

        date_str = parsed["start_date"]
        if parsed["end_date"] and parsed["end_date"] != parsed["start_date"]:
            date_str += f"~ {parsed['end_date']}"

        results[source_id] = {
            "seq": source_id,
            "source": "yanolja",
            "title": parsed["title"],
            "location": parsed["location"],
            "date": date_str,
            "thumbnail_url": thumbnail_url,
            "detail_url": detail_url,
            "store_url": detail_url,
            "description": "",
            "hashtags": "[]",
            "main_category": "공연",
            "sub_category": genre,
            "detail_category": "",
            "music_genre": "[]",
            "mood_tags": "[]",
            "activity_tags": "[]",
            "theme_tags": "[]",
            "space_tags": "[]",
            "emotion_tags": "[]",
            "audience_tags": "[]",
            "vector_summary": "",
            "region_filter": region,  # 어느 지역 필터로 수집했는지
        }


async def scrape(headed: bool = False) -> list[dict]:
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        page = await browser.new_page()

        print(f"[접속] {CONCERT_URL}")
        await page.goto(CONCERT_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        for region in TARGET_REGIONS:
            print(f"\n=== 지역: {region} ===")
            await select_region(page, region)

            for genre in TARGET_GENRES:
                print(f"  [장르] {genre}")
                tab = page.get_by_role("tab", name=genre, exact=True)
                await tab.scroll_into_view_if_needed()
                await tab.click(force=True)
                await page.wait_for_timeout(600)

                await collect_visible_cards(page, genre, region, results)

        await browser.close()

    return list(results.values())


def save_json(data: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → JSON 저장: {path}")


def save_csv(data: list[dict], path: Path):
    if not data:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  → CSV 저장: {path}")


def main():
    parser = argparse.ArgumentParser(description="야놀자 NOL 콘서트 크롤러")
    parser.add_argument("--out", default=".", help="결과 저장 디렉토리")
    parser.add_argument("--headed", action="store_true", help="브라우저 화면 표시")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    items = asyncio.run(scrape(headed=args.headed))
    print(f"\n총 {len(items)}개 수집 완료 (서울 + 경기)")

    save_json(items, out_dir / "yanolja_concerts.json")
    save_csv(items, out_dir / "yanolja_concerts.csv")
    print("완료!")


if __name__ == "__main__":
    main()

"""
야놀자/멜론티켓 CSV를 event_db.sqlite3에 임포트.
실행: python import_concerts.py
"""

import csv
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "event_db.sqlite3"

CSV_FILES = [
    BASE_DIR.parent / "야놀자" / "yanolja_concerts_tagged.csv",
    BASE_DIR.parent / "멜론티켓" / "melon_concerts_tagged.csv",
]


def parse_dates(date_str: str):
    """'2026-05-29~ 2026-05-31' → ('2026-05-29', '2026-05-31')"""
    if not date_str:
        return None, None
    parts = re.split(r"[~\-]{1,2}(?=\s*\d{4})", date_str.replace(" ", ""))
    parts = [p.strip() for p in parts if p.strip()]

    def to_date(s):
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    start = to_date(parts[0]) if parts else None
    end = to_date(parts[1]) if len(parts) > 1 else start
    return start, end


def import_csv(conn: sqlite3.Connection, csv_path: Path) -> tuple[int, int]:
    if not csv_path.exists():
        print(f"  파일 없음: {csv_path}")
        return 0, 0

    inserted = skipped = 0
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source", "").strip()
            source_id = row.get("seq", "").strip()

            # 중복 체크
            exists = conn.execute(
                "SELECT 1 FROM events_event WHERE source=? AND source_id=?",
                (source, source_id),
            ).fetchone()
            if exists:
                skipped += 1
                continue

            start_date, end_date = parse_dates(row.get("date", ""))

            category = row.get("new_main_category") or row.get("main_category") or "공연"
            conn.execute(
                """
                INSERT INTO events_event (
                    title, category, source, source_id, location, start_date, end_date,
                    description, thumbnail_url, detail_url, store_url,
                    hashtags, main_category, sub_category, detail_category,
                    music_genre, mood_tags, activity_tags, theme_tags,
                    space_tags, emotion_tags, vector_summary,
                    commerciality, exhibition_type,
                    new_main_category, new_sub_category, region,
                    new_mood_tags, new_audience_tags, vector_summary_v2,
                    created_at, updated_at
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'',
                    datetime('now'), datetime('now')
                )
                """,
                (
                    row.get("title", ""),
                    category,
                    source,
                    source_id,
                    row.get("location", ""),
                    start_date,
                    end_date,
                    row.get("description", ""),
                    row.get("thumbnail_url", ""),
                    row.get("detail_url", ""),
                    row.get("store_url", ""),
                    row.get("hashtags", "[]"),
                    row.get("main_category", ""),
                    row.get("sub_category", ""),
                    row.get("detail_category", ""),
                    row.get("music_genre", ""),
                    row.get("mood_tags", "[]"),
                    row.get("activity_tags", "[]"),
                    row.get("theme_tags", "[]"),
                    row.get("space_tags", "[]"),
                    row.get("emotion_tags", "[]"),
                    row.get("vector_summary", ""),
                    row.get("commerciality", ""),
                    row.get("exhibition_type", ""),
                    row.get("new_main_category", ""),
                    row.get("new_sub_category", ""),
                    row.get("region", ""),
                    row.get("new_mood_tags", "[]"),
                    row.get("new_audience_tags", "[]"),
                ),
            )
            inserted += 1

    conn.commit()
    return inserted, skipped


def main():
    conn = sqlite3.connect(DB_PATH)

    total_before = conn.execute("SELECT COUNT(*) FROM events_event").fetchone()[0]
    print(f"임포트 전: {total_before}개\n")

    for csv_path in CSV_FILES:
        print(f"처리 중: {csv_path.name}")
        inserted, skipped = import_csv(conn, csv_path)
        print(f"  추가: {inserted}개 / 중복 스킵: {skipped}개")

    total_after = conn.execute("SELECT COUNT(*) FROM events_event").fetchone()[0]
    print(f"\n임포트 후: {total_after}개 (+ {total_after - total_before}개)")
    conn.close()


if __name__ == "__main__":
    main()

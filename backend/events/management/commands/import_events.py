"""
python manage.py import_events --file ../../데이포유/popup_stores.csv
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Event


def parse_date_range(date_str: str):
    """'2026-05-09~ 2026-05-21' → (date, date)"""
    if not date_str:
        return None, None
    parts = [p.strip() for p in date_str.replace('~', '|').split('|')]
    start = end = None
    for i, part in enumerate(parts):
        try:
            d = datetime.strptime(part[:10], '%Y-%m-%d').date()
            if i == 0:
                start = d
            else:
                end = d
        except ValueError:
            pass
    return start, end


def parse_hashtags(raw):
    """JSON 문자열 또는 이미 리스트인 경우 처리"""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [t.strip() for t in str(raw).split(',') if t.strip()]


class Command(BaseCommand):
    help = '팝업스토어 CSV 데이터를 Event 모델에 임포트'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='popup_stores.csv 경로')
        parser.add_argument('--clear', action='store_true', help='임포트 전 기존 데이터 삭제')

    def handle(self, *args, **options):
        csv_path = Path(options['file'])
        if not csv_path.exists():
            raise CommandError(f'파일을 찾을 수 없습니다: {csv_path}')

        if options['clear']:
            deleted, _ = Event.objects.filter(source='dayforyou').delete()
            self.stdout.write(f'기존 데이터 {deleted}개 삭제')

        created = updated = skipped = 0

        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f'{len(rows)}개 행 처리 중...')

        with transaction.atomic():
            for row in rows:
                source_id = row.get('seq', '').strip()
                if not source_id:
                    skipped += 1
                    continue

                start_date, end_date = parse_date_range(row.get('date', ''))

                defaults = {
                    'title': row.get('title', '').strip(),
                    'category': Event.CATEGORY_POPUP,
                    'location': row.get('location', '').strip(),
                    'start_date': start_date,
                    'end_date': end_date,
                    'description': row.get('description', '').strip(),
                    'thumbnail_url': row.get('thumbnail_url', '').strip()[:1000],
                    'detail_url': row.get('detail_url', '').strip()[:1000],
                    'hashtags': parse_hashtags(row.get('hashtags', [])),
                    'main_category': row.get('main_category', '').strip(),
                    'sub_category': row.get('sub_category', '').strip(),
                    'detail_category': row.get('detail_category', '').strip(),
                    'music_genre': parse_hashtags(row.get('music_genre', [])),
                    'mood_tags': parse_hashtags(row.get('mood_tags', [])),
                    'activity_tags': parse_hashtags(row.get('activity_tags', [])),
                    'theme_tags': parse_hashtags(row.get('theme_tags', [])),
                    'space_tags': parse_hashtags(row.get('space_tags', [])),
                    'emotion_tags': parse_hashtags(row.get('emotion_tags', [])),
                    'audience_tags': parse_hashtags(row.get('audience_tags', [])),
                    'vector_summary': row.get('vector_summary', '').strip(),
                    'region': row.get('region', '').strip(),
                    'new_main_category': row.get('new_main_category', '').strip(),
                    'new_sub_category': row.get('new_sub_category', '').strip(),
                    'exhibition_type': row.get('exhibition_type', '').strip(),
                    'commerciality': row.get('commerciality', '').strip(),
                    'new_mood_tags': parse_hashtags(row.get('new_mood_tags', [])),
                    'new_audience_tags': parse_hashtags(row.get('new_audience_tags', [])),
                    'vector_summary_v2': row.get('vector_summary_v2', '').strip(),
                }

                _, was_created = Event.objects.update_or_create(
                    source='dayforyou',
                    source_id=source_id,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'완료 — 생성: {created}, 업데이트: {updated}, 건너뜀: {skipped}'
        ))

"""
python manage.py fetch_store_urls
기존 이벤트의 dayforyou 상세 페이지에서 '팝업스토어 페이지 바로가기' 링크를 수집합니다.
"""

import time
import requests
import urllib3
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from events.models import Event

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
})


def fetch_store_url(detail_url: str) -> str:
    try:
        resp = SESSION.get(detail_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if "바로가기" in text or "페이지" in text:
                return a["href"]
    except Exception:
        pass
    return ""


class Command(BaseCommand):
    help = "dayforyou 상세 페이지에서 팝업스토어 직접 링크 수집"

    def add_arguments(self, parser):
        parser.add_argument("--delay", type=float, default=0.5)
        parser.add_argument("--overwrite", action="store_true", help="이미 있는 store_url도 덮어씀")

    def handle(self, *args, **options):
        qs = Event.objects.filter(detail_url__icontains="dayforyou.com")
        if not options["overwrite"]:
            qs = qs.filter(store_url="")

        total = qs.count()
        self.stdout.write(f"{total}개 이벤트 처리 중...")

        updated = 0
        for i, event in enumerate(qs, 1):
            url = fetch_store_url(event.detail_url)
            if url:
                event.store_url = url
                event.save(update_fields=["store_url"])
                updated += 1

            if i % 20 == 0:
                self.stdout.write(f"  {i}/{total} 완료 (링크 수집: {updated}개)")
            time.sleep(options["delay"])

        self.stdout.write(self.style.SUCCESS(f"완료 — {updated}/{total}개 링크 수집"))

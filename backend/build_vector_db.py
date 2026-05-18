"""
이벤트 임베딩 → ChromaDB 저장 스크립트
사용법: python build_vector_db.py
"""

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from events.models import Event
from django.utils import timezone
from django.db.models import Q
from openai import OpenAI
from django.conf import settings
import chromadb

client = OpenAI(api_key=settings.OPENAI_API_KEY)
chroma = chromadb.PersistentClient(path="./chroma_db")

COLLECTION_NAME = "events"


def make_text(ev: Event) -> str:
    """이벤트를 임베딩할 텍스트로 변환"""
    parts = [
        ev.title,
        ev.location,
        ev.description[:500],
        " ".join(ev.hashtags[:10]) if ev.hashtags else "",
        " ".join(ev.new_mood_tags) if ev.new_mood_tags else "",
        " ".join(ev.new_audience_tags) if ev.new_audience_tags else "",
        ev.new_main_category,
        ev.new_sub_category,
        ev.commerciality,
        ev.region,
    ]
    return " ".join(p for p in parts if p)


def get_embedding(text: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding


def main():
    # 기존 컬렉션 삭제 후 재생성
    try:
        chroma.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma.create_collection(COLLECTION_NAME)

    today = timezone.localdate()
    events = list(Event.objects.filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True)
    ))

    print(f"{len(events)}개 이벤트 임베딩 시작...")

    batch_size = 50
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        texts = [make_text(ev) for ev in batch]
        ids = [str(ev.id) for ev in batch]

        # 배치 임베딩
        resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
        embeddings = [r.embedding for r in resp.data]

        metadatas = [{
            "title": ev.title,
            "location": ev.location,
            "region": ev.region,
            "new_main_category": ev.new_main_category,
            "new_sub_category": ev.new_sub_category,
            "commerciality": ev.commerciality,
        } for ev in batch]

        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        print(f"  {min(i + batch_size, len(events))}/{len(events)} 완료")

    print(f"\n완료! ChromaDB에 {collection.count()}개 저장됨 → ./chroma_db/")


if __name__ == "__main__":
    main()

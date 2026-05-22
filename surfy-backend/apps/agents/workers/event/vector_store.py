"""Event vector store backed by ChromaDB."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
EVENT_DB_PATH = Path(os.getenv("EVENT_DB_PATH", DATA_DIR / "event_db.sqlite3"))
EVENT_TABLE = os.getenv("EVENT_DB_TABLE", "events_event")
CHROMA_PATH = Path(os.getenv("EVENT_CHROMA_PATH", DATA_DIR / "chroma_db"))
COLLECTION_NAME = os.getenv("EVENT_CHROMA_COLLECTION", "event_places")
EMBED_MODEL = os.getenv("EVENT_EMBED_MODEL", "text-embedding-3-small")
BATCH_SIZE = 100


def _openai_client():
    from openai import OpenAI
    return OpenAI()


def make_event_text(row: dict[str, Any]) -> str:
    """이벤트 행을 임베딩용 텍스트로 변환."""
    parts = []
    if row.get("title"):
        parts.append(f"title: {row['title']}")
    main_cat = row.get("new_main_category") or row.get("main_category")
    if main_cat:
        parts.append(f"category: {main_cat}")
    sub_cat = row.get("new_sub_category") or row.get("sub_category")
    if sub_cat:
        sub_cat_text = sub_cat
        if isinstance(sub_cat, str) and sub_cat.strip().startswith("["):
            try:
                parsed = json.loads(sub_cat)
                if isinstance(parsed, list):
                    sub_cat_text = " ".join(str(v) for v in parsed if v)
            except json.JSONDecodeError:
                pass
        if sub_cat_text:
            parts.append(f"subcategory: {sub_cat_text}")
    if row.get("music_genre"):
        parts.append(f"genre: {row['music_genre']}")
    if row.get("description"):
        parts.append(f"description: {str(row['description'])[:300]}")

    for tag_field in ("hashtags", "mood_tags", "new_mood_tags", "audience_tags", "new_audience_tags"):
        value = row.get(tag_field)
        if not value:
            continue
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    parts.append(f"{tag_field}: {' '.join(str(v) for v in parsed[:5])}")
                    continue
            except json.JSONDecodeError:
                pass
            parts.append(f"{tag_field}: {value[:100]}")

    return " | ".join(parts)


def _load_active_event_rows() -> list[dict[str, Any]]:
    if not EVENT_DB_PATH.exists():
        raise FileNotFoundError(f"event DB not found: {EVENT_DB_PATH}")

    conn = sqlite3.connect(EVENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    today = date.today().isoformat()
    rows = conn.execute(
        f"SELECT * FROM {EVENT_TABLE} WHERE end_date IS NULL OR end_date >= ?", (today,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _openai_client()
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def build_event_vector_db(reset: bool = False) -> int:
    """이벤트 DB에서 ChromaDB 컬렉션을 빌드."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))

    existing_names = [c.name for c in chroma.list_collections()]
    if reset and COLLECTION_NAME in existing_names:
        chroma.delete_collection(COLLECTION_NAME)

    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    existing_ids = set(collection.get()["ids"]) if collection.count() else set()

    rows = _load_active_event_rows()
    targets = [row for row in rows if str(row["id"]) not in existing_ids]
    if not targets:
        print(f"이미 최신 상태: {collection.count():,}개")
        return collection.count()

    print(f"임베딩 빌드 중: {len(targets)}개 이벤트...")
    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i: i + BATCH_SIZE]
        documents = [make_event_text(row) for row in batch]
        embeddings = embed_texts(documents)
        ids = [str(row["id"]) for row in batch]
        metadatas = [_metadata(row) for row in batch]
        collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        print(f"  {min(i + BATCH_SIZE, len(targets))}/{len(targets)} 완료")

    total = collection.count()
    print(f"빌드 완료: {total:,}개 -> {CHROMA_PATH}")
    return total


def query_events(query: str, top_k: int = 10, category_filter: str | None = None) -> list[dict[str, Any]]:
    """벡터 유사도로 이벤트 검색."""
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        collection = chroma.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    if collection.count() == 0:
        return []

    q_vec = embed_texts([query])[0]
    where = {"category": category_filter} if category_filter else None

    result = collection.query(
        query_embeddings=[q_vec],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances"],
        where=where,
    )

    rows = []
    for metadata, distance in zip(result["metadatas"][0], result["distances"][0]):
        row = dict(metadata)
        row["similarity"] = round(max(0.0, 1.0 - float(distance)), 4)
        rows.append(row)
    return rows


def get_events_by_ids(event_ids: list[str]) -> list[dict[str, Any]]:
    """벡터 검색 결과 ID로 원본 이벤트 행 조회."""
    if not event_ids or not EVENT_DB_PATH.exists():
        return []

    placeholders = ",".join("?" * len(event_ids))
    conn = sqlite3.connect(EVENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT * FROM {EVENT_TABLE} WHERE id IN ({placeholders})", event_ids
    ).fetchall()
    conn.close()

    row_map = {str(row["id"]): dict(row) for row in rows}
    return [row_map[eid] for eid in event_ids if eid in row_map]


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    sub = row.get("new_sub_category") or row.get("sub_category") or ""
    if isinstance(sub, str) and sub.strip().startswith("["):
        try:
            parsed = json.loads(sub)
            if isinstance(parsed, list):
                sub = ", ".join(str(v) for v in parsed if v)
        except json.JSONDecodeError:
            pass
    return {
        "event_id": str(row.get("id", "")),
        "title": str(row.get("title") or ""),
        "category": str(row.get("new_main_category") or row.get("main_category") or row.get("category") or ""),
        "subcategory": str(sub),
        "location": str(row.get("location") or ""),
        "region": str(row.get("region") or ""),
        "start_date": str(row.get("start_date") or ""),
        "end_date": str(row.get("end_date") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="기존 컬렉션 삭제 후 재빌드")
    args = parser.parse_args()
    build_event_vector_db(reset=args.reset)


if __name__ == "__main__":
    main()

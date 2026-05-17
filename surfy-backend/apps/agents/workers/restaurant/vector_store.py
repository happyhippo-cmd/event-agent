from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
ENRICHED_DB_PATH = Path(
    os.getenv("RESTAURANT_ENRICHED_DB_PATH")
    or os.getenv("ENRICHED_DB_PATH", DATA_DIR / "foodie_enriched.db")
)
CHROMA_PATH = Path(
    os.getenv("RESTAURANT_CHROMA_PATH")
    or os.getenv("FOODIE_CHROMA_PATH", DATA_DIR / "chroma_db")
)
COLLECTION_NAME = (
    os.getenv("RESTAURANT_CHROMA_COLLECTION")
    or os.getenv("FOODIE_CHROMA_COLLECTION", "foodie_places")
)
EMBED_MODEL = os.getenv("RESTAURANT_EMBED_MODEL") or os.getenv("FOODIE_EMBED_MODEL", "text-embedding-3-small")
EMBED_PROVIDER = (os.getenv("RESTAURANT_EMBED_PROVIDER") or os.getenv("FOODIE_EMBED_PROVIDER", "local_hash")).lower()
LOCAL_EMBED_DIM = int(os.getenv("RESTAURANT_LOCAL_EMBED_DIM") or os.getenv("FOODIE_LOCAL_EMBED_DIM", "384"))
BATCH_SIZE = int(os.getenv("RESTAURANT_EMBED_BATCH_SIZE") or os.getenv("FOODIE_EMBED_BATCH_SIZE", "100"))
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣_]+")
DISTRICT_PATTERN = re.compile(r"(서울|경기|인천)\s+([가-힣A-Za-z0-9]+(?:구|군|시))")


def _openai_client():
    from openai import OpenAI

    return OpenAI()


def _mood_dict(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def make_place_text(row: dict[str, Any]) -> str:
    """Convert only mood tags into embedding text.

    Place identity stays in Chroma metadata so similarity is mood-based while
    search results can still be mapped back to a concrete place.
    """

    mood = _mood_dict(row.get("mood_tags"))
    parts: list[str] = []
    for key in ("who", "occasion", "atmosphere", "features", "price_feel"):
        values = mood.get(key) or []
        if values:
            parts.append(f"{key}: {' '.join(str(v) for v in values)}")
    return " | ".join(parts)


def _load_enriched_rows() -> list[dict[str, Any]]:
    if not ENRICHED_DB_PATH.exists():
        raise FileNotFoundError(f"enriched DB not found: {ENRICHED_DB_PATH}")

    conn = sqlite3.connect(ENRICHED_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT kakao_place_id, name, category_name, category_group, gu,
               address, road_address, lat, lng, phone, place_url,
               rating, review_count, price_level, opening_hours,
               COALESCE(mood_tags_naver, mood_tags) AS mood_tags,
               michelin_stars, is_bib_gourmand
        FROM enriched_places
        WHERE COALESCE(mood_tags_naver, mood_tags) IS NOT NULL
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_collection(COLLECTION_NAME)


def build_vector_db(reset: bool = False, limit: int | None = None) -> int:
    """Build or update the Chroma vector DB from the enriched restaurant DB."""

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))

    existing_names = [collection.name for collection in chroma.list_collections()]
    if reset and COLLECTION_NAME in existing_names:
        chroma.delete_collection(COLLECTION_NAME)

    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    existing_ids = set(collection.get()["ids"]) if collection.count() else set()

    rows = _load_enriched_rows()
    if limit is not None:
        rows = rows[:limit]
    targets = [row for row in rows if str(row["kakao_place_id"]) not in existing_ids]
    if not targets:
        return collection.count()

    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i : i + BATCH_SIZE]
        documents = [make_place_text(row) for row in batch]
        embeddings = embed_texts(documents)
        ids = [str(row["kakao_place_id"]) for row in batch]
        metadatas = [_metadata(row) for row in batch]
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    return collection.count()


def query_places(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        raise RuntimeError("restaurant vector DB is empty. Run build_vector_db first.")

    q_vec = embed_texts([query])[0]
    result = collection.query(
        query_embeddings=[q_vec],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    rows: list[dict[str, Any]] = []
    for doc, metadata, distance in zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        row = dict(metadata)
        row["document"] = doc
        row["distance"] = float(distance)
        row["similarity_score"] = max(0.0, min(1.0, 1.0 - float(distance)))
        rows.append(row)
    return rows


def embed_texts(texts: list[str]) -> list[list[float]]:
    if EMBED_PROVIDER == "openai":
        client = _openai_client()
        return [
            item.embedding
            for item in client.embeddings.create(model=EMBED_MODEL, input=texts).data
        ]
    if EMBED_PROVIDER != "local_hash":
        raise ValueError(
            "RESTAURANT_EMBED_PROVIDER/FOODIE_EMBED_PROVIDER must be 'local_hash' or 'openai', "
            f"got {EMBED_PROVIDER!r}"
        )
    return [_local_hash_embedding(text) for text in texts]


def _local_hash_embedding(text: str) -> list[float]:
    vector = [0.0] * LOCAL_EMBED_DIM
    tokens = TOKEN_PATTERN.findall(text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % LOCAL_EMBED_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    address = row.get("road_address") or row.get("address") or ""
    return {
        "kakao_place_id": str(row["kakao_place_id"]),
        "name": row.get("name") or "",
        "category": (row.get("category_name") or "").split(" > ")[-1],
        "gu": _district_from_address(address) or row.get("gu") or "",
        "address": address,
        "lat": row.get("lat") or 0.0,
        "lng": row.get("lng") or 0.0,
        "rating": row.get("rating") or 0.0,
        "review_count": row.get("review_count") or 0,
        "price_level": row.get("price_level")
        if row.get("price_level") is not None
        else -1,
        "michelin_stars": row.get("michelin_stars") or 0,
        "is_bib_gourmand": row.get("is_bib_gourmand") or 0,
        "mood_tags": row.get("mood_tags") or "{}",
    }


def _district_from_address(address: str) -> str:
    match = DISTRICT_PATTERN.search(address or "")
    if match:
        return match.group(2)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    count = build_vector_db(reset=args.reset, limit=args.limit)
    print(
        f"restaurant vector DB ready: {count:,} places -> {CHROMA_PATH} "
        f"(provider={EMBED_PROVIDER})"
    )


if __name__ == "__main__":
    main()

"""
K-Dive Agent 공유 유틸리티
여러 Worker Agent·dummy_server에서 반복 사용되는 함수들을 한 곳에 모아 관리한다.
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

# ============================================================
# 날짜/시간
# ============================================================

_SEOUL_TZ = ZoneInfo("Asia/Seoul")


def get_seoul_now() -> datetime:
    """Asia/Seoul 기준 현재 datetime을 반환한다."""
    return datetime.now(_SEOUL_TZ)


def get_seoul_date_str() -> str:
    """Asia/Seoul 기준 현재 날짜를 'YYYY년 M월 D일' 형식의 문자열로 반환한다."""
    now = get_seoul_now()
    return f"{now.year}년 {now.month}월 {now.day}일"


# ============================================================
# 공유 상수
# ============================================================

# 주소에서 "서울 종로구" 등의 시·구를 추출하는 정규식
DISTRICT_PATTERN = re.compile(r"(서울|경기|인천)\s+([가-힣A-Za-z0-9]+(?:구|군|시))")


# ============================================================
# 좌표 / 거리 계산
# ============================================================

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표(위도·경도) 사이의 거리를 km 단위로 반환한다 (Haversine 공식)."""
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


# ============================================================
# 한국어 조사 헬퍼
# ============================================================

def topic_label(name: str) -> str:
    """이름 뒤에 한국어 토픽 조사(은/는)를 붙인다.

    받침 있으면 '은', 없으면 '는'.
    예) "경복궁" → "경복궁은", "남산서울타워" → "남산서울타워는"
    """
    last = name[-1] if name else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return f"{name}은"
    return f"{name}는"


def object_phrase(text: str) -> str:
    """텍스트 뒤에 한국어 목적격 조사(을/를)를 붙인다.

    받침 있으면 '을', 없으면 '를'.
    예) "카페" → "카페를", "디저트" → "디저트를"
    """
    last = text[-1] if text else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return f"{text}을"
    return f"{text}를"


# ============================================================
# 한국어 수식어 연결
# ============================================================

def preference_modifier(term: str) -> str:
    """취향 키워드를 자연스러운 수식어로 변환한다."""
    mapping = {
        "로컬 느낌": "로컬 느낌이 있는",
        "로컬": "로컬 느낌이 있는",
        "혼자": "혼자 머물기 좋은",
    }
    return mapping.get(term, term)


def to_connective(text: str) -> str:
    """관형형 수식어("~한", "~적인" 등)를 연결형("~하고", "~이고" 등)으로 변환한다."""
    if text.endswith("한"):
        return f"{text[:-1]}하고"
    if text.endswith("적인"):
        return f"{text[:-2]}이고"
    if text.endswith("있는"):
        return f"{text[:-2]}있고"
    if text.endswith("좋은"):
        return f"{text[:-2]}좋고"
    return f"{text}이고"


def join_modifiers(items: list[str]) -> str:
    """여러 수식어를 자연스러운 한국어 연결형으로 합친다.

    예) ["조용한", "감성적인"] → "조용하고 감성적인"
    """
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    converted = [to_connective(item) for item in items[:-1]]
    return " ".join([*converted, items[-1]])


def join_unique(items: list[str]) -> str:
    """중복을 제거하면서 쉼표로 이어 붙인다."""
    return ", ".join(dict.fromkeys(item for item in items if item))


# ============================================================
# taste_context 헬퍼
# ============================================================

def taste_terms(taste_context: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    """taste_context에서 지정한 키들의 값을 평탄화(flatten)하여 중복 없는 리스트로 반환한다."""
    terms: list[str] = []
    for key in keys:
        value = taste_context.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
        elif value:
            terms.append(str(value))
    return list(dict.fromkeys(terms))


# ============================================================
# OpenAI 클라이언트 (싱글턴)
# ============================================================

_openai_client_instance = None


def get_openai_client():
    """OpenAI 클라이언트를 싱글턴으로 반환한다.

    환경변수 OPENAI_API_KEY가 없으면 None.
    """
    global _openai_client_instance
    if _openai_client_instance is not None:
        return _openai_client_instance

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            from django.conf import settings
            api_key = getattr(settings, "OPENAI_API_KEY", None)
        except Exception:
            api_key = None

    if not api_key:
        return None

    try:
        from openai import OpenAI
        _openai_client_instance = OpenAI(api_key=api_key)
        return _openai_client_instance
    except Exception:
        return None

# Supervisor Agent 멘토링 정리 노트
> 브랜치: `feat/supervisor-multiturn-tpo` | 날짜: 2026-05-20

---

## 1. 초기 구현 → 현재 수정 사항

### 초기 구현 (커밋 `24c5616` · `feat: implement initial supervisor agent`)
- supervisor.py 982줄 / state.py 110줄
- `supervisor_intake()` 5단계 파이프라인: 키워드 추출 → 온보딩 매칭 → TPO 충돌 → 취향 객체 → 라우팅
- 멀티턴 없음 (단일 발화 처리만)
- 날짜 개념 없음
- LLM 키워드 추출 결과를 그대로 신뢰 (원문 검증 없음)

### 현재 수정 사항 (미커밋 · 브랜치 로컬 변경)

supervisor.py 1309줄로 확장. 아래 9가지 기능이 추가되었다.

---

#### ① 멀티턴 대화 히스토리 누적 ★ (가장 중요)

**변경 위치:** `supervisor_intake()` 맨 앞 Step 0

```python
# 추가된 코드
conv_messages: list[dict] = list(state.get("messages") or [])
conv_messages.append({"role": "user", "content": state["user_utterance"]})
state["messages"] = conv_messages
```

- `state["messages"]`에 매 턴 발화를 `{"role": "user", "content": ...}` 형태로 누적
- state.py에 `messages: NotRequired[list[dict]]` 필드 추가
- graph.py(신규 파일)의 `MemorySaver`와 결합해 thread_id별 상태 영속성 확보

**관련 신규 파일 — graph.py:**
```python
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
# → 같은 thread_id로 invoke하면 이전 state(messages 포함) 자동 복원
```

---

#### ② 현재 시각 주입 (Asia/Seoul)

```python
seoul_now = get_seoul_now()   # utils.py에 추가된 함수
current_date_str = f"{today.year}년 {today.month}월 {today.day}일"
state["current_datetime"] = current_date_str
```

- `state["current_datetime"]`을 worker agent까지 전달
- 키워드 추출 LLM 프롬프트 앞에 날짜를 주입해 날짜 인식 가능하게 함

---

#### ③ 과거 날짜 감지 및 되물음 (신규 clarification_type: "past_date")

```python
_DATE_PATTERN = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")

# "5월 5일에 카페 추천해줘" → 오늘(5/20) 기준 과거 → 되물음
is_past, detected_date = _detect_past_date(state["user_utterance"], today)
```

- `continue_after_clarification()`에서 응답 처리:
  - "네/응" → 날짜 부분 제거 후 원발화 재처리
  - "5월 25일에" → 날짜 교체 후 원발화 재처리

---

#### ④ 여행 단계 감지 (TravelPhase)

```python
state["travel_phase"] = _detect_travel_phase(state["user_utterance"])
# → "pre_trip" | "during_trip" | "unknown"
```

- state.py에 `TravelPhase = Literal["pre_trip", "during_trip", "unknown"]` 추가
- LLM structured output으로 판단

---

#### ⑤ 키워드 원문 검증 (`_validate_keywords_against_utterance`)

**초기:** LLM 추출 결과를 그대로 반환
```python
return result.keywords  # 초기
```

**현재:** 원문에 없는 사실형 키워드 제거
```python
return _validate_keywords_against_utterance(result.keywords, utterance)  # 현재
```

- `place_type`, `food_type`, `location`, `event_type` 카테고리만 검증
- `mood`, `activity`, `other`는 LLM 정규화 의도이므로 그대로 유지
- location 특별 처리: "혜화역 근처" → "혜화" (꾸밈말 + 역 접미사 제거)

---

#### ⑥ 수도권 지명 보강 로직 수정 (버그 픽스)

**초기 (버그):**
```python
if not any(region in kw.keyword for kw in extracted_keywords):
```
→ 지명이 place_type으로 분류돼도 skip → location 보강 누락

**현재 (수정):**
```python
has_location_match = any(
    kw.category == "location" and region in kw.keyword
    for kw in extracted_keywords
)
if not has_location_match:  # location 카테고리에만 없으면 보강
```

- "혜화", "대학로" 목록 추가도 함께 반영

---

#### ⑦ tourist 의도 보강 (`_scan_tourist_intent_terms`)

```python
_TOURIST_INTENT_TERMS = (
    "관광", "관광지", "명소", "가볼만", "구경",
    "산책", "박물관", "미술관", "공원", "야경", "볼거리",
)
```

- LLM이 "구경", "산책" 같은 동사를 tourist가 아닌 activity/other로 분류하는 경우 보완
- 발화 원문을 직접 스캔 → 해당 어휘가 있으면 tourist 투표 강제 추가

---

#### ⑧ 명시 배제 키워드 결정적 감지 (`_apply_deterministic_taste_boost`)

```python
_EXPLICIT_EXCLUDE_TERMS = ("체인", "프랜차이즈", "스타벅스", "커피빈", ...)
_LOCAL_INTENT_TERMS = ("로컬", "동네", "개인", "독립", "숨은")
```

- LLM이 "스타벅스 말고" 에서 suppressed_keywords를 못 잡을 때 결정적으로 보완
- "로컬/동네" 발화 → "체인" 자동 suppress

---

#### ⑨ 온보딩 anchor 허용 여부 판단 (`_should_allow_onboarding_anchors`)

```python
def _should_allow_onboarding_anchors(utterance, extracted_keywords) -> bool:
    return not any(kw.category == "location" for kw in extracted_keywords)
```

- 사용자가 명시적 지역을 말했으면 온보딩 좌표가 덮어쓰지 않도록 `False` 반환
- `taste_context["allow_onboarding_anchors"]`로 worker에 전달

---

## 2. Supervisor 수정 사항 검증 질문들 (프론트에서 테스트 가능)

아래 질문들을 채팅창에 순서대로 입력해서 동작을 확인한다.

### [검증 A] 멀티턴 대화 히스토리 누적
```
1턴: "홍대 근처 감성 카페 추천해줘"
2턴: "거기서 가까운 맛집도 알려줘"
```
**확인 포인트:** 2턴 응답이 "홍대 근처"라는 맥락을 유지하는가? (location_keywords에 홍대 유지 여부)

### [검증 B] 과거 날짜 감지
```
"5월 5일에 갈 건데 카페 추천해줘"
```
**예상 응답:** "5월 5일은 이미 지난 날짜예요. 현재 날짜 기준으로 추천해드릴까요?"
**이어서:** "응 현재 기준으로" → 정상 카페 추천이 나오는가?

### [검증 C] 여행 단계 감지
```
A. "다음 주에 홍대 갈 건데 카페 추천해줘"   → travel_phase = "pre_trip"
B. "지금 홍대 왔는데 카페 어디 좋아?"       → travel_phase = "during_trip"
```

### [검증 D] 지하철역 정규화
```
"혜화역 근처 조용한 카페 추천해줘"
```
**확인 포인트:** location_keywords에 "혜화" (역 제거됨)가 들어오는가? 주소 매칭이 정상 동작하는가?

### [검증 E] tourist 의도 보강
```
"북촌 구경하고 근처 맛집도 알려줘"
```
**확인 포인트:** target_agents에 tourist AND foodie 둘 다 포함되는가?

### [검증 F] 명시 배제 키워드
```
"체인 말고 홍대 로컬 카페 추천해줘"
```
**확인 포인트:** suppressed_keywords에 "체인"이 포함되는가?

### [검증 G] 복합 의도 멀티 라우팅
```
"성수에서 구경하고 초밥도 먹고 싶어"
```
**확인 포인트:** target_agents = ["tourist", "foodie"] (둘 다 라우팅)

### [검증 H] TPO 충돌 흐름
```
(음악 취향이 힙합/EDM인 사용자가) "조용한 카페에서 책 읽고 싶어"
```
**예상 응답:** "평소 음악 분위기(힙합, EDM)와 지금 찾으시는 곳(조용한)의 느낌이 다른데요! A/B/C 중 선택해주세요"
**이어서:** "C" → 두 그룹 분리 출력이 나오는가?

---

## 3. Multi-turn 구현 판단 — 어떻게 돌아가는가

### 구현 레벨: 두 겹의 멀티턴

```
┌─────────────────────────────────────────────────────┐
│  레벨 1: LangGraph MemorySaver (graph.py)           │
│  → thread_id 동일 → state 전체를 메모리에 복원       │
│    (messages, travel_phase, taste_context 등)        │
├─────────────────────────────────────────────────────┤
│  레벨 2: messages 누적 (supervisor.py)               │
│  → 매 턴 supervisor_intake()에서 직접 append         │
│    state["messages"] = [...이전..., 새 발화]         │
└─────────────────────────────────────────────────────┘
```

### 실제 흐름 (graph.py 사용 시)

```python
graph = build_graph()   # MemorySaver 포함

# 1턴
graph.invoke(
    {"user_utterance": "홍대 카페 추천해줘", "onboarding_data": onboarding},
    config={"configurable": {"thread_id": "user-123"}}
)
# → MemorySaver에 state 저장

# 2턴 (thread_id 동일)
graph.invoke(
    {"user_utterance": "거기서 가까운 맛집도"},
    config={"configurable": {"thread_id": "user-123"}}
    # onboarding_data 생략 가능 — MemorySaver가 이전 state 복원
)
```

### ⚠️ 주의: messages 중복 가능성

supervisor_validation.py (대화형 테스트)는 MemorySaver 없이 `session_messages`를 직접 관리:
```python
session_messages: list[dict] = []   # 세션 내 수동 누적
state = {
    "messages": list(session_messages),   # 직접 주입
    ...
}
result_state = supervisor_intake(state)
session_messages = list(result_state.get("messages") or [])  # 동기화
```

graph.py를 통해 호출할 때는 MemorySaver가 이전 messages를 이미 state에 복원하고,
supervisor가 또 append하므로 **중복 없이** 정상 동작함.
(2턴에 messages 전달 안 해도 MemorySaver가 복원하기 때문)

### 현재 한계점

- `messages`에 assistant 응답이 append되는 부분이 없음
  → user 발화만 쌓이고 AI 응답은 히스토리에 포함되지 않음
  → Worker agent 결과를 받은 후 `messages.append({"role": "assistant", "content": ...})` 로직 필요
- 현재는 "대화 흐름 인식"보다 **state의 taste_context 누적**이 멀티턴의 실질적 효과

---

## 4. Supervisor → Worker Agent 키워드 형식 (자세히)

### 4-1. 키워드 추출 단계별 구조

#### Step 1: LLM 구조화 출력 (`_ExtractedKeyword` Pydantic)

```python
class _ExtractedKeyword(BaseModel):
    keyword: str          # 원문 또는 정규화 표현 (한국어 유지)
    category: str         # 아래 7종 중 하나
    agent_hint: str       # 라우팅 힌트
    is_past_action: bool  # 과거 완료 행동이면 True → 라우팅 투표 제외
```

**category 7종:**

| category | 의미 | 예시 |
|---|---|---|
| `place_type` | 장소 종류 | "카페", "공원", "한옥마을" |
| `mood` | 분위기 | "조용한", "감성적인", "활기찬" |
| `location` | 지역/위치 | "홍대", "성수", "강남" |
| `food_type` | 음식 종류 | "초밥", "디저트", "한식" |
| `event_type` | 이벤트 종류 | "팝업스토어", "전시회", "공연" |
| `activity` | 행동/활동 | "구경", "산책", "책 읽기" |
| `other` | 기타 | "혼자", "조용히" |

**agent_hint 4종:**

| agent_hint | 라우팅 대상 |
|---|---|
| `tourist` | 관광지 Agent |
| `foodie` | 맛집 Agent |
| `event` | 이벤트 Agent |
| `any` | 미분류 (place_type+any → tourist로 귀속) |

#### Step 2: 원문 검증 + 정규화

```python
# 사실형 카테고리만 원문 검증
_FACTUAL_CATEGORIES = {"place_type", "food_type", "location", "event_type"}

# location 정규화 예시
"혜화역 근처" → "혜화"   # 역 접미사 + 근처 제거
"강남 주변"   → "강남"   # 주변 제거
"홍대"        → "홍대"   # 변화 없음
```

#### Step 3: 결정적(deterministic) 보강

```python
# 수도권 지명 보강 (LLM이 놓친 경우)
region → _ExtractedKeyword(keyword=region, category="location", agent_hint="any")

# tourist 의도 보강 (LLM이 activity/other로 분류한 경우)
"구경" → _ExtractedKeyword(keyword="구경", category="activity", agent_hint="tourist")
```

---

### 4-2. Worker에 전달되는 최종 형식

#### `taste_context` (dict) — 가장 핵심 전달값

```python
{
    # ── 현재 발화 키워드 (가중치 ×2.0) ──
    "current_keywords": ["홍대", "카페", "조용한"],
    "current_weight": 2.0,

    # ── 카테고리별 분류 ──
    "mood_keywords": ["조용한"],           # category=mood
    "location_keywords": ["홍대"],         # category=location
    "place_type_keywords": ["카페"],       # category=place_type
    "food_type_keywords": [],              # category=food_type
    "event_type_keywords": [],             # category=event_type

    # ── 온보딩 취향 (가중치 ×1.0) ──
    "preferred_music": ["lo-fi", "어쿠스틱"],
    "preferred_spots": ["북촌한옥마을", "남산서울타워"],
    "preferred_food": ["화덕피자집", "초밥집"],
    "preferred_mood": ["애틋한", "청량한"],
    "companion_type": "혼자",
    "active_time": "저녁",
    "onboarding_weight": 1.0,

    # ── Q7: 이전 턴 반응 반영 ──
    "boosted_keywords": ["감성 카페", "조용한"],   # 이전 긍정 반응 키워드 → 강화
    "suppressed_keywords": ["체인"],               # 이전 부정 반응 + 발화 내 부정 → 억제

    # ── TPO 충돌 선택 (A/B/C) ──
    "tpo_choice": None,
    "onboarding_mood_keywords": [],    # C 선택 시: 온보딩 기준 무드
    "current_mood_keywords": [],       # C 선택 시: 현재 발화 기준 무드

    # ── 온보딩 anchor 허용 여부 ──
    "allow_onboarding_anchors": False, # location_keywords 있으면 False

    # ── 디버깅용 ──
    "keyword_routing_detail": [
        {"keyword": "홍대", "category": "location", "agent_hint": "any"},
        {"keyword": "카페", "category": "place_type", "agent_hint": "foodie"},
        {"keyword": "조용한", "category": "mood", "agent_hint": "any"},
    ]
}
```

#### `keywords_with_reasons` (list[KeywordWithReason]) — 설명 가능성(Q5)

```python
[
    {
        "keyword": "조용한",
        "reason": "온보딩에서 '애틋한' 선택 + 지난 추천에서 좋아하셨던 패턴"
    },
    {
        "keyword": "홍대",
        "reason": "현재 요청 기반"
    },
    ...
]
```

#### Worker가 `taste_context`로 하는 일

restaurant agent 예시:
```python
def build_restaurant_query(taste_context):
    # location + food_type + mood + music + food 선호도를 합쳐 벡터 검색 쿼리 생성
    ordered_parts = []
    for key in ("location_keywords", "food_type_keywords", "mood_keywords",
                "preferred_food", "preferred_music", "boosted_keywords"):
        ordered_parts.extend(taste_context.get(key) or [])
    return " ".join(ordered_parts) or "서울 분위기 좋은 맛집"

# suppressed_keywords → 해당 키워드가 포함된 장소 필터링 제거
# location_keywords → 해당 지역 장소 우선 정렬
# allow_onboarding_anchors → False면 온보딩 장소 좌표로 검색 반경 설정 안 함
```

---

## 요약

| 항목 | 초기 | 현재 |
|---|---|---|
| 멀티턴 | ✗ | ✅ MemorySaver + messages 누적 |
| 날짜 인식 | ✗ | ✅ 서울 기준 현재 날짜 주입 |
| 과거 날짜 감지 | ✗ | ✅ 정규식 + 되물음 |
| 여행 단계 | ✗ | ✅ pre_trip / during_trip / unknown |
| 키워드 원문 검증 | ✗ | ✅ 사실형 카테고리만 필터 |
| tourist 의도 보강 | ✗ | ✅ 결정적 어휘 스캔 |
| 배제 키워드 감지 | LLM 의존 | ✅ 결정적 + LLM 보완 |
| anchor 허용 판단 | ✗ | ✅ location 키워드 유무로 판단 |
| 지하철역 정규화 | ✗ | ✅ "역" 접미사 제거 |

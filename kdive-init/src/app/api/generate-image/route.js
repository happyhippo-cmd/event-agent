// POST /api/generate-image
// body:   { imageBase64, mimeType }
// returns { imageBase64, mimeType, kind, items }
//
// 1) gpt-4o-mini (vision) 로 사진을 보고 JSON 응답: { kind, items }
// 2) 이미지 모델(gpt-image-1) 에 손글씨 + 일러스트를 같이 그리도록 호출

import { NextResponse } from 'next/server';
import { buildPrompt } from '@/utils/prompts';

export const runtime = 'nodejs';

const VISION_MODEL = 'gpt-4o-mini';
const IMAGE_MODEL = 'gpt-image-2';
const CHAT_ENDPOINT = 'https://api.openai.com/v1/chat/completions';
const EDITS_ENDPOINT = 'https://api.openai.com/v1/images/edits';

export async function POST(req) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: 'OPENAI_API_KEY 환경변수가 설정되지 않았어요.' },
      { status: 500 }
    );
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: '유효하지 않은 JSON 본문' }, { status: 400 });
  }

  const { imageBase64, mimeType } = body || {};
  if (!imageBase64 || !mimeType) {
    return NextResponse.json(
      { error: 'imageBase64, mimeType가 필요해요.' },
      { status: 400 }
    );
  }

  // ── 1) vision 분석 ───────────────────────────────────────
  let analyzed;
  try {
    analyzed = await analyzeImage({ apiKey, imageBase64, mimeType });
  } catch (e) {
    return NextResponse.json(
      {
        error: '사진 분석 중 오류',
        detail: e instanceof Error ? e.message : String(e),
      },
      { status: 502 }
    );
  }

  // ── 2) 프롬프트 빌드 ──────────────────────────────────────
  const prompt = buildPrompt(analyzed.kind, analyzed.items);

  // ── 3) 이미지 편집 ────────────────────────────────────────
  const buffer = Buffer.from(imageBase64, 'base64');
  const ext = mimeType.split('/')[1] ?? 'png';
  const fileBlob = new Blob([buffer], { type: mimeType });
  const file = new File([fileBlob], `upload.${ext}`, { type: mimeType });

  const formData = new FormData();
  formData.append('model', IMAGE_MODEL);
  formData.append('image', file);
  formData.append('prompt', prompt);
  formData.append('n', '1');
  formData.append('size', 'auto');
  formData.append('quality', 'high');

  const res = await fetch(EDITS_ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}` },
    body: formData,
  });

  if (!res.ok) {
    const errText = await res.text();
    return NextResponse.json(
      {
        error: `OpenAI 이미지 편집 오류 (${res.status})`,
        detail: errText,
        ...analyzed,
      },
      { status: 502 }
    );
  }

  const data = await res.json();
  const b64 = data?.data?.[0]?.b64_json;
  if (!b64) {
    return NextResponse.json(
      { error: '이미지 응답을 받지 못했어요.', detail: data, ...analyzed },
      { status: 502 }
    );
  }

  return NextResponse.json({
    imageBase64: b64,
    mimeType: 'image/png',
    ...analyzed,
  });
}

// ─────────────────────────────────────────────────────────
// vision 분석: 5종 kind 분류 + 트레이싱 대상 items
async function analyzeImage({ apiKey, imageBase64, mimeType }) {
  const instruction = `
이 사진을 보고 아래 JSON 스키마로만 응답해줘. JSON 외 텍스트/설명/마크다운 금지.

스키마:
{ "kind": "place" | "building" | "ootd" | "group" | "travel", "items": string[] }

[kind 분류 — 정확히 한 개 고르기]

★ 가장 먼저 정해야 할 것: **사진의 "주인공 일행"이 몇 명인가?**
   - "주인공 일행" = 카메라를 의식하고 포즈를 잡거나, 한 그룹으로 묶여서 찍힌 사람들.
   - **배경에 우연히 같이 찍힌 다른 손님 / 옆 테이블 일행 / 지나가는 행인 / 종업원은
     절대 카운트하지 말 것.** (식당·카페·길거리에서 흔히 발생)
   - 예: 1명이 정면을 보고 포즈를 잡고 있고, 뒤쪽 테이블에 다른 손님들이 있어도
     → 주인공 일행은 **1명**.

[5종 분류 기준]
- "ootd": 주인공 일행이 **1명** 이고 의상/스타일링이 메인일 때.
  배경이 평범한 벽/방/거울/길 등 **장소 정보가 약할 때만**.
  (얼굴/전신 코디샷, 거울 셀카)
- "travel": 주인공 일행이 **1명** 이고 배경에 **분명한 장소 정보** (식당/카페/가게 간판·
  인테리어·랜드마크·관광지·명소·특정 건축물·외관 등) 가 함께 있을 때. → 방문/여행 로그.
  **식당 안에서 음식과 함께 찍은 인증샷, 카페에서 분위기 잡은 사진도 travel.**
- "group": 주인공 일행이 **2명 이상** 일 때만 (어깨동무, V포즈, 명확히 같이 카메라 보는 단체샷).
  배경 행인/다른 손님은 인원수에 안 들어감.
- "building": 건축물·외관·한옥·교회·타워·랜드마크가 주피사체이고 **사람이 없거나 매우 작게** 있을 때.
- "place": 위 어디에도 안 맞는 정물·공간·음식·카페 내부·풍경 (사람 없음).

[items 규칙 — kind 별로 다름]
- "ootd"     : 패션 아이템 위주, 3~7개.
  예) ["베이지 코트", "체크 셔츠", "데님 스커트", "흰 스니커즈", "단정하게 묶은 헤어"]
- "travel"   : **주인공 인물 1개 + 배경 장소/랜드마크 3~5개**. 인물은 "주인공 인물 1명" 한 항목.
  예) ["주인공 인물 1명", "에펠탑", "에펠탑 광장 분수", "주변 가로등"]
  ⚠️ **배경에 우연히 찍힌 다른 손님 / 옆 테이블 사람 / 행인 / 종업원은
     items 에 절대 넣지 말 것.** (예: "뒤쪽 손님", "옆 테이블 일행" 같은 항목 금지)
- "group"    : **주인공 일행(여러 명) 묶음 1개 + 배경/장소 디테일 2~4개**. 사람을 한 명씩 쪼개지 말 것.
  예) ["주인공 일행(전체)", "한강 야경", "다리 조명", "강변 벤치"]
  ⚠️ 위와 동일 — 배경 행인/다른 손님은 items 에 넣지 말 것.
- "building" : **건물 윤곽 1개**. 기와·처마·창살로 쪼개지 말 것. 추가는 주변 간판/안내문 1~2개 정도까지만.
  예) ["한옥 건물 전체", "입구 간판"]
- "place"    : 메뉴/소품/식기 등 3~7개로 쪼개기.
  예) ["참치회덮밥", "된장국", "단무지와 김치"]

[공통 가드]
- 사진에 실제로 보이지 않는 사물·인물은 추측해서 넣지 말 것.
- items 는 한국어, 구체적으로.
`.trim();

  const visionBody = {
    model: VISION_MODEL,
    response_format: { type: 'json_object' },
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: instruction },
          {
            type: 'image_url',
            image_url: { url: `data:${mimeType};base64,${imageBase64}` },
          },
        ],
      },
    ],
    max_tokens: 400,
    temperature: 0,
  };

  const res = await fetch(CHAT_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(visionBody),
  });

  if (!res.ok) {
    throw new Error(`vision ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();
  const text = (data?.choices?.[0]?.message?.content ?? '').toString();

  let parsed = {};
  try {
    parsed = JSON.parse(text);
  } catch {
    return { kind: 'place', items: [] };
  }

  const allowed = ['place', 'building', 'ootd', 'group', 'travel'];
  const kind = allowed.includes(parsed.kind) ? parsed.kind : 'place';
  const items = Array.isArray(parsed.items)
    ? parsed.items.filter((s) => typeof s === 'string').slice(0, 7)
    : [];

  return { kind, items };
}
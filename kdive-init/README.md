# K-Dive Next.js 마이그레이션

원본 `k_dive_onboarding.{html,css,js}` 3개 파일을 Next.js (App Router) + React + Tailwind CSS로 옮긴 프로젝트입니다.

## 시작하기

```bash
cd kdive-next
npm install
npm run dev
```

- 개발 서버: http://localhost:3000
- 정적 자산: 앨범 커버 이미지는 `public/assets/album-covers/`에 두면 됩니다. 원본 `assets/album-covers/...` 경로를 그대로 사용했습니다 (코드에서는 `/assets/album-covers/...`).

## 폴더 구조

```
kdive-next/
├── package.json
├── next.config.js
├── tailwind.config.js
├── postcss.config.js
├── jsconfig.json
├── .eslintrc.json
├── .gitignore
└── src/
    ├── app/
    │   ├── layout.jsx         # 전역 레이아웃, 폰트 로드, KdiveProvider 주입
    │   ├── page.jsx           # 메인 페이지 (Nav + Onboarding + Curation + Auth + Surfy)
    │   └── globals.css        # Tailwind 진입점 + 유틸로 표현 어려운 CSS만 보존
    ├── data/
    │   └── albums.js          # ALBUMS 34개, MUST_VISIT_PLACES, 헬퍼 함수
    ├── store/
    │   └── KdiveContext.jsx   # 전역 상태 (Context). 좋아요/섹션 표시/플레이어 등
    └── components/
        ├── nav/
        │   ├── Nav.jsx
        │   ├── ScrollTopDial.jsx
        │   └── TransitionOverlay.jsx
        ├── onboarding/
        │   ├── OnboardingSection.jsx
        │   ├── AlbumCarousel.jsx
        │   ├── AlbumCard.jsx
        │   └── DeckDots.jsx
        ├── player/
        │   ├── PlayerBar.jsx
        │   ├── Waveform.jsx
        │   └── SpotifyControllerPool.jsx
        ├── curation/
        │   ├── CurationSection.jsx
        │   ├── PlaceStrip.jsx
        │   ├── PlaceDetail.jsx
        │   └── FoodSection.jsx
        ├── auth/
        │   └── AuthSection.jsx
        └── surfy/
            ├── SurfyPage.jsx
            ├── SurfySidebar.jsx
            ├── SurfyChat.jsx
            └── surfyChatStore.js
```

## 원본 대비 변경 사항

### 그대로 유지
- 앨범 34개와 각 앨범의 places, vibe 데이터.
- 좋아요(트랙/장소/맛집) 상태와 localStorage 키 (`kdive-liked-tracks`, `kdive-liked-places`, `kdive-liked-foods`).
- 캐러셀 카드 위치/스케일/필터 공식 (`getCarouselStyle`).
- 큐레이션 → 맛집 더 알아보기 → 인증 안내 → 로그인 → Surfy 페이지로 이어지는 동선.
- Surfy의 Django API 호출 (`http://localhost:8000/api/chat/`).

### 단순화한 부분 [추론입니다]
원본 1740줄 중 다음 영역은 React idiom에 맞춰 단순화했고, 시각적 정확도가 100% 동일하지는 않을 수 있습니다.

1. **캐러셀 wraparound 애니메이션**: 원본은 buffer card를 동적으로 DOM에 삽입해 부드러운 무한 캐러셀을 구현했습니다. React 버전은 VISIBLE_OFFSETS(11개)만 렌더하고 currentIdx만 갱신합니다. 인접 1칸 이동은 정상이지만, dot 클릭으로 멀리 점프할 때 원본 같은 다단계 시퀀스 애니메이션(`moveCarouselSequence`)은 적용되지 않습니다.
2. **Waveform 시각화**: 원본 `updateWaveformMotion`은 매 프레임마다 128개 bar의 height를 timestamp 기반으로 미세 조정합니다. React 버전은 height를 정적으로 두고 active/current 클래스만 토글합니다. 음악이 흐르는 듯한 미세 떨림은 줄어듭니다.
3. **WaveSurfer.js**: 원본은 preview URL 로드용이지만 데이터의 `preview`가 모두 빈 문자열이라 실질적으로 mock 파형만 사용됩니다. 따라서 이번 버전에서는 WaveSurfer를 의존성에만 남기고 직접 호출하지 않습니다. 필요하면 `PlayerBar.jsx`에 `useEffect`로 동적 import해 붙일 수 있습니다.
4. **Spotify Iframe API 이중 동기화**: 원본은 WaveSurfer와 Spotify 양쪽을 진실의 원천(source of truth)으로 두고 어느 한쪽이 끝나면 다른 쪽도 정지시키는 로직이 있습니다. React 버전은 KdiveContext의 `isPlaying`을 단일 진실의 원천으로 두고 Spotify 컨트롤러만 제어합니다.
5. **sticky 플레이어 바 위치 동적 이동**: 원본은 스크롤 위치에 따라 sharedPlayerBar를 onboardingSlot과 curationSlot 사이에서 옮깁니다. React 버전은 `playerSlot` 상태로 어디에 렌더할지 결정하지만, 스크롤 위치 기반 자동 전환(`syncSharedPlayerBarLocation`)은 빠져 있습니다.

이 5가지는 시각적 정확도가 중요한 경우 후속 작업으로 다듬어야 합니다.

## 의존성 [팩트]
- `next@^14.2.5`
- `react@^18.3.1`, `react-dom@^18.3.1`
- `wavesurfer.js@^7.8.6` (원본과 동일 메이저 버전. 현재는 미사용 — 위 4번 참고)
- dev: `tailwindcss@^3.4.7`, `postcss@^8.4.39`, `autoprefixer@^10.4.19`, `eslint-config-next@^14.2.5`

## 알려진 TODO
- 캐러셀 multi-step 시퀀스 애니메이션 복원.
- Waveform 프레임별 height 애니메이션 복원.
- sticky 플레이어 자동 슬롯 전환 복원.
- `public/assets/album-covers/`에 실제 이미지 파일 배치 (원본 폴더 그대로 복사).
- TransitionOverlay의 라우팅 트리거 연결 (현재는 정적 렌더만).

이 README는 원본 코드를 분석한 결과로 작성되었습니다.

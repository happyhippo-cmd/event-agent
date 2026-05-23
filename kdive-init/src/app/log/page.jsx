'use client';

// Log 페이지
// - 왼쪽: 방문 장소 카드 그리드
//   · 빈 카드     = 흰 박스 + 📍이름 + 주소 (아이콘 없음)
//   · 사진 있는 카드 = 위쪽 미디어 영역(aspect 4:5, cover) + 아래 이름·주소
//                    + 컨테이너 아래에 다운로드 아이콘
// - 오른쪽: 업로드/미리보기/재생성 패널
//   · 빈 상태             — 안내
//   · 업로드 대기          — Browse
//   · 업로드 미리보기       — 생성 버튼
//   · 생성된 사진 보기 모드  — 사진 크게 + Browse(교체)/재생성

import { useMemo, useRef, useState } from 'react';
import { samplePlaces as initialPlaces } from '@/data/places';
import HandwrittenOverlay from '@/components/log/HandwrittenOverlay';

const NAV = ['Surfy', 'History', 'Log', 'My page'];

const KIND_LABEL = {
  place: 'PLACE (정물/공간)',
  building: 'BUILDING (건축물)',
  ootd: 'OOTD (1인 패션)',
  group: 'GROUP (단체)',
  travel: 'TRAVEL (방문/여행 로그)',
};

export default function LogPage() {
  const [places, setPlaces] = useState(initialPlaces);
  const [selectedId, setSelectedId] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [pendingPreview, setPendingPreview] = useState(null);
  const [pendingMime, setPendingMime] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [lastKind, setLastKind] = useState(null);
  const [lastItems, setLastItems] = useState([]);

  const fileInputRef = useRef(null);
  const selected = useMemo(
    () => places.find((p) => p.id === selectedId) ?? null,
    [places, selectedId]
  );

  function clearPending() {
    setPendingFile(null);
    setPendingPreview(null);
    setPendingMime(null);
  }

  function handleSelectPlace(id) {
    setSelectedId(id);
    clearPending();
    setErrorMsg(null);
    setLastKind(null);
    setLastItems([]);
  }

  function handleFile(file) {
    if (!file) return;
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) {
      setErrorMsg('png, jpg, webp 파일만 업로드할 수 있어요.');
      return;
    }
    setErrorMsg(null);
    setPendingFile(file);
    setPendingMime(file.type);
    const reader = new FileReader();
    reader.onload = () => setPendingPreview(String(reader.result));
    reader.readAsDataURL(file);
  }

  /** 생성 — pendingPreview 가 있으면 그걸로, 없으면 selected.photoUrl(원본)으로 재생성 */
  async function handleGenerate(opts) {
    if (!selected) return;

    let base64 = null;
    let mime = null;

    if (opts?.useExisting) {
      if (!selected.photoUrl || !selected.photoMime) return;
      base64 = selected.photoUrl.split(',')[1] ?? null;
      mime = selected.photoMime;
    } else {
      if (!pendingPreview || !pendingMime) return;
      base64 = pendingPreview.split(',')[1] ?? null;
      mime = pendingMime;
    }
    if (!base64 || !mime) return;

    setIsGenerating(true);
    setErrorMsg(null);
    setLastKind(null);
    setLastItems([]);

    try {
      const res = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageBase64: base64, mimeType: mime }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error ?? `요청 실패 (${res.status})`);
      }

      const { imageBase64, mimeType, kind, items, memos, title } = await res.json();
      const generatedUrl = `data:${mimeType};base64,${imageBase64}`;

      setPlaces((prev) =>
        prev.map((p) =>
          p.id === selected.id
            ? {
                ...p,
                photoUrl: opts?.useExisting ? p.photoUrl : pendingPreview ?? p.photoUrl,
                photoMime: opts?.useExisting ? p.photoMime : pendingMime ?? p.photoMime,
                generatedUrl,
                memos: memos ?? [],
                title: title ?? '',
              }
            : p
        )
      );
      setLastKind(kind);
      setLastItems(items ?? []);
      clearPending();
    } catch (e) {
      setErrorMsg(
        e instanceof Error ? e.message : '이미지 생성 중 오류가 발생했어요.'
      );
    } finally {
      setIsGenerating(false);
    }
  }

  function downloadGenerated(p) {
    if (!p.generatedUrl) return;
    const a = document.createElement('a');
    a.href = p.generatedUrl;
    a.download = `${p.name}-log.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  return (
    <div className="min-h-screen bg-white text-neutral-900">
      {/* Header — kdive-init 의 Nav 와 겹치지 않게 자체 헤더를 별도 페이지 톤으로 둠 */}
      <header className="flex items-center justify-between px-10 py-6">
        <h1 className="text-2xl font-bold tracking-tight">K-Dive</h1>
        <nav className="flex items-center gap-10 text-sm">
          {NAV.map((item) => (
            <span
              key={item}
              className={item === 'Log' ? 'font-bold' : 'text-neutral-500'}
            >
              {item}
            </span>
          ))}
        </nav>
      </header>

      <main className="grid grid-cols-1 items-start gap-10 px-10 pb-16 lg:grid-cols-[1fr_1fr]">
        {/* ───── 왼쪽: 장소 카드 그리드 ───── */}
        <section className="grid grid-cols-2 gap-6 md:grid-cols-3">
          {places.map((place) => (
            <PlaceCard
              key={place.id}
              place={place}
              isSelected={place.id === selectedId}
              onSelect={() => handleSelectPlace(place.id)}
              onDownload={() => downloadGenerated(place)}
            />
          ))}
        </section>

        {/* ───── 오른쪽: 업로드 + 생성 패널 ───── */}
        <section className="flex flex-col gap-3">
          <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
            {!selected ? (
              <EmptyState text="왼쪽에서 방문한 장소 카드를 선택해주세요." />
            ) : selected.generatedUrl && !pendingPreview ? (
              <GeneratedView
                place={selected}
                onPickFile={() => fileInputRef.current?.click()}
                onRegenerate={() => handleGenerate({ useExisting: true })}
                isGenerating={isGenerating}
              />
            ) : (
              <UploadArea
                place={selected}
                pendingPreview={pendingPreview}
                onPickFile={() => fileInputRef.current?.click()}
                onDrop={(file) => handleFile(file)}
                onClear={() => clearPending()}
              />
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />

            <p className="mt-3 text-center text-[11px] text-rose-500">
              *File supported .png, .jpg &amp; .webp
            </p>
          </div>

          {(!selected?.generatedUrl || pendingPreview) && (
            <button
              type="button"
              disabled={!selected || !pendingPreview || isGenerating}
              onClick={() => handleGenerate()}
              className="rounded-2xl border border-neutral-200 bg-white py-6 text-xl font-bold shadow-sm transition hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isGenerating ? '생성 중…' : '로그 사진 생성'}
            </button>
          )}

          {selected && !lastKind && !selected.generatedUrl && (
            <p className="px-2 text-xs text-neutral-500">
              선택된 장소: <b>{selected.name}</b> · 사진을 분석해서 톤을 자동으로
              골라줄게요.
            </p>
          )}
          {lastKind && (
            <div className="space-y-1 px-2 text-xs text-neutral-700">
              <p>
                적용된 톤: <b>{KIND_LABEL[lastKind]}</b>
              </p>
              {lastItems.length > 0 && (
                <p className="text-neutral-500">
                  감지된 오브젝트: {lastItems.join(' · ')}
                </p>
              )}
            </div>
          )}
          {errorMsg && (
            <p className="px-2 text-xs text-rose-500">{errorMsg}</p>
          )}
        </section>
      </main>
    </div>
  );
}

/* ────────── 카드 ────────── */

function PlaceCard({ place, isSelected, onSelect, onDownload }) {
  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={onSelect}
        className={`relative flex w-full flex-col overflow-hidden rounded-2xl bg-white text-left shadow-sm transition ${
          isSelected
            ? 'ring-2 ring-neutral-900'
            : 'border border-neutral-200 hover:border-neutral-400'
        }`}
      >
        {place.generatedUrl || place.photoUrl ? (
          <div className="flex aspect-[4/5] w-full flex-col overflow-hidden">
            <div className="relative flex-1 bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={place.generatedUrl ?? place.photoUrl}
                alt={place.name}
                className="absolute inset-0 h-full w-full object-cover"
              />
            </div>
            <div className="flex flex-col gap-0.5 px-3 py-2">
              <div className="flex items-center gap-1 text-sm font-semibold">
                <PinIcon />
                <span className="truncate">{place.name}</span>
              </div>
              <p className="truncate text-[11px] leading-tight text-neutral-500">
                주소 {place.address}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex aspect-[4/5] w-full flex-col gap-2 p-4">
            <div className="flex items-center gap-1 text-base font-semibold">
              <PinIcon />
              <span>{place.name}</span>
            </div>
            <p className="text-xs leading-relaxed text-neutral-500">
              주소 {place.address}
            </p>
          </div>
        )}

        {!place.generatedUrl && !place.photoUrl && (
          <span className="pointer-events-none absolute bottom-3 right-3 grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white shadow">
            <CheckIcon />
          </span>
        )}
      </button>

      {place.generatedUrl && (
        <div className="flex justify-end pr-1">
          <button
            type="button"
            onClick={onDownload}
            className="text-neutral-600 transition hover:text-neutral-900"
            aria-label={`${place.name} 로그 사진 다운로드`}
            title="다운로드"
          >
            <ShareDownIcon />
          </button>
        </div>
      )}
    </div>
  );
}

/* ────────── 오른쪽 패널들 ────────── */

function UploadArea({ place, pendingPreview, onPickFile, onDrop, onClear }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 px-2 py-4"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(e.dataTransfer.files?.[0]);
      }}
    >
      <p className="text-sm text-neutral-500">
        <b>{place.name}</b> 사진을 업로드해주세요
      </p>

      {pendingPreview ? (
        <div className="relative w-full max-w-md">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={pendingPreview}
            alt="업로드 미리보기"
            className="mx-auto max-h-[420px] w-auto rounded-xl object-contain"
          />
          <button
            type="button"
            onClick={onClear}
            className="absolute right-1 top-1 grid h-7 w-7 place-items-center rounded-full bg-white/90 text-neutral-600 shadow ring-1 ring-neutral-200 hover:text-neutral-900"
            aria-label="미리보기 지우기"
            title="다른 파일 선택"
          >
            <XIcon />
          </button>
        </div>
      ) : (
        <UploadIcon big />
      )}

      <button
        type="button"
        onClick={onPickFile}
        className="rounded-full bg-neutral-200 px-5 py-1.5 text-sm font-medium text-neutral-800 hover:bg-neutral-300"
      >
        Browse
      </button>
      <p className="text-[11px] text-neutral-400">drop a file here</p>
    </div>
  );
}

function GeneratedView({ place, onPickFile, onRegenerate, isGenerating }) {
  return (
    <div className="flex flex-col items-center gap-3 px-2 py-3">
      <p className="text-sm text-neutral-500">
        <b>{place.name}</b> · 생성된 로그 사진
      </p>
      <div className="mx-auto flex w-full max-w-[420px] justify-center">
        <HandwrittenOverlay
          src={place.generatedUrl}
          title={place.title}
          memos={place.memos ?? []}
          alt={place.name}
          className="max-h-[60vh]"
        />
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPickFile}
          disabled={isGenerating}
          className="rounded-full bg-neutral-200 px-4 py-1.5 text-sm font-medium text-neutral-800 hover:bg-neutral-300 disabled:opacity-50"
        >
          Browse (사진 교체)
        </button>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isGenerating || !place.photoUrl}
          className="rounded-full bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {isGenerating ? '재생성 중…' : '재생성'}
        </button>
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="flex min-h-[200px] items-center justify-center text-sm text-neutral-400">
      {text}
    </div>
  );
}

/* ────────── 아이콘들 ────────── */

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden>
      <path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7Zm0 9.2A2.2 2.2 0 1 1 12 6.8a2.2 2.2 0 0 1 0 4.4Z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden>
      <path d="M5 12l5 5L20 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UploadIcon({ big }) {
  const size = big ? 48 : 18;
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={big ? 1.5 : 2} aria-hidden>
      <path d="M12 16V4M6 10l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 20h16" strokeLinecap="round" />
    </svg>
  );
}

function ShareDownIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <path d="M12 4v11" strokeLinecap="round" />
      <path d="M7 10l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 20h16" strokeLinecap="round" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}

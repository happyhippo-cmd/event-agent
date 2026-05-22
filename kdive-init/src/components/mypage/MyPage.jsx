'use client';

import { useState, useEffect } from 'react';
import { useKdive } from '@/store/KdiveContext';

/* ─────────────────────────────────────────────
   미니 컴포넌트
───────────────────────────────────────────── */

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="relative flex-shrink-0 rounded-full transition-colors duration-250 focus:outline-none"
      style={{
        width: 44,
        height: 24,
        background: checked ? '#00A8E8' : 'rgba(0,0,0,0.15)',
        transition: 'background 0.22s',
      }}
    >
      <span
        className="absolute top-[3px] rounded-full bg-white shadow-sm"
        style={{
          width: 18,
          height: 18,
          left: checked ? 23 : 3,
          transition: 'left 0.22s cubic-bezier(0.22,1,0.36,1)',
        }}
      />
    </button>
  );
}

function SectionCard({ icon, title, children }) {
  return (
    <div className="bg-surface rounded-2xl border border-[rgba(0,0,0,0.06)] overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-5 border-b border-[rgba(0,0,0,0.06)]">
        <span className="text-[22px]">{icon}</span>
        <h2 className="font-pretendard text-[15px] font-bold text-text tracking-[-0.01em]">
          {title}
        </h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

function InputField({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <div className="flex items-center gap-4 py-2">
      <span
        className="font-pretendard text-[13px] text-muted flex-shrink-0"
        style={{ minWidth: 72 }}
      >
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 h-9 px-3 rounded-lg text-[13px] text-text font-pretendard bg-white border border-[rgba(0,0,0,0.08)] focus:border-[rgba(0,168,232,0.4)] outline-none transition-all"
        style={{ maxWidth: 280 }}
      />
    </div>
  );
}

function StatCard({ count, label, color }) {
  return (
    <div
      className="flex-1 rounded-xl px-4 py-4 flex flex-col items-center gap-1"
      style={{ background: color, minWidth: 0 }}
    >
      <span className="font-serif text-[1.8rem] leading-none text-text">{count}</span>
      <span className="font-pretendard text-[11px] text-muted text-center leading-tight">{label}</span>
    </div>
  );
}

/* ─────────────────────────────────────────────
   아바타 이니셜 색상 (이름 기반)
───────────────────────────────────────────── */
const AVATAR_PALETTES = [
  ['#C8EEFF', '#0070A0'],
  ['#D6F5EB', '#0A7A55'],
  ['#FFF0D6', '#A06400'],
  ['#EDE8FF', '#5A3FC0'],
  ['#FFE8F0', '#B03060'],
];

function getAvatarPalette(name) {
  if (!name) return AVATAR_PALETTES[0];
  const code = [...name].reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return AVATAR_PALETTES[code % AVATAR_PALETTES.length];
}

/* ─────────────────────────────────────────────
   MyPage 본체
───────────────────────────────────────────── */
export default function MyPage() {
  const { loggedIn, activeAppPage, likedTrackIds, likedPlaceKeys, likedFoodKeys } = useKdive();

  // ── 프로필
  const [name, setName] = useState('');
  const [nickname, setNickname] = useState('');
  const [contact, setContact] = useState('');
  const [birthday, setBirthday] = useState('');
  const [gender, setGender] = useState('');

  // ── 설정
  const [language, setLanguage] = useState('ko');
  const [surferOn, setSurferOn] = useState(true);

  // ── 알림 설정 (신규)
  const [emailNotif, setEmailNotif] = useState(true);
  const [pushNotif, setPushNotif] = useState(false);
  const [marketingNotif, setMarketingNotif] = useState(false);

  // ── 비밀번호 변경
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwMsg, setPwMsg] = useState('');

  // ── 회원탈퇴
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // ── 프로필 편집 모드
  const [editing, setEditing] = useState(false);

  // localStorage 영속화
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const saved = JSON.parse(localStorage.getItem('kdive-mypage') || '{}');
      if (saved.name)      setName(saved.name);
      if (saved.nickname)  setNickname(saved.nickname);
      if (saved.contact)   setContact(saved.contact);
      if (saved.birthday)  setBirthday(saved.birthday);
      if (saved.gender)    setGender(saved.gender);
      if (saved.language)  setLanguage(saved.language);
      if (typeof saved.surferOn === 'boolean') setSurferOn(saved.surferOn);
      if (typeof saved.emailNotif === 'boolean') setEmailNotif(saved.emailNotif);
      if (typeof saved.pushNotif === 'boolean')  setPushNotif(saved.pushNotif);
      if (typeof saved.marketingNotif === 'boolean') setMarketingNotif(saved.marketingNotif);
    } catch {}
  }, []);

  const saveToStorage = () => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem('kdive-mypage', JSON.stringify({
        name, nickname, contact, birthday, gender,
        language, surferOn, emailNotif, pushNotif, marketingNotif,
      }));
    } catch {}
  };

  const handleSaveProfile = () => {
    saveToStorage();
    setEditing(false);
  };

  const handleChangePw = (e) => {
    e.preventDefault();
    if (!currentPw || !newPw || !confirmPw) {
      setPwMsg('모든 항목을 입력해 주세요.');
      return;
    }
    if (newPw !== confirmPw) {
      setPwMsg('새 비밀번호가 일치하지 않아요.');
      return;
    }
    if (newPw.length < 8) {
      setPwMsg('비밀번호는 8자 이상이어야 해요.');
      return;
    }
    setPwMsg('✓ 비밀번호가 변경되었어요.');
    setCurrentPw('');
    setNewPw('');
    setConfirmPw('');
  };

  const [bg, fg] = getAvatarPalette(nickname || name);
  const initials = (nickname || name || '?').slice(0, 2).toUpperCase();

  if (!loggedIn || activeAppPage !== 'mypage') return null;

  return (
    <section
      id="myPage"
      className="h-[100dvh] overflow-hidden bg-white max-[760px]:h-auto max-[760px]:min-h-screen max-[760px]:overflow-visible"
    >
      <div className="mx-auto flex h-full w-[min(960px,calc(100%-96px))] flex-col gap-[clamp(12px,1.6vh,20px)] pb-[3vh] pt-[max(84px,8vh)] max-[760px]:h-auto max-[760px]:w-[calc(100%-32px)] max-[760px]:gap-5 max-[760px]:pb-8 max-[760px]:pt-[78px]">

        {/* ── 페이지 헤더 ── */}
        <header className="flex items-center justify-between gap-5 max-[760px]:flex-col max-[760px]:items-start">
          <h1 className="text-[20px] font-bold uppercase tracking-[0.12em] text-accent">My Page</h1>
        </header>

        {/* ── 스크롤 영역 ── */}
        <div className="kd-history-scroll min-h-0 flex-1 overflow-y-auto pr-3 pt-2 scroll-pt-2 max-[760px]:h-auto max-[760px]:overflow-visible max-[760px]:pr-0">
        <div className="flex flex-col gap-4 pb-8">

        {/* ── 프로필 헤더 카드 ── */}
        <div
          className="bg-surface rounded-2xl border border-[rgba(0,0,0,0.06)] px-6 py-6 flex items-center gap-5"
        >
          {/* 아바타 */}
          <div
            className="flex-shrink-0 rounded-full flex items-center justify-center font-serif text-[1.3rem] font-bold select-none"
            style={{
              width: 68,
              height: 68,
              background: bg,
              color: fg,
              letterSpacing: '-0.02em',
            }}
          >
            {initials}
          </div>

          <div className="flex-1 min-w-0">
            <p className="font-pretendard text-[17px] font-bold text-text leading-tight truncate">
              {nickname || name || '이름을 설정해 주세요'}
            </p>
            <p className="font-pretendard text-[12px] text-muted mt-0.5 truncate">
              {contact || '연락처 미설정'}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            className="flex-shrink-0 h-8 px-4 rounded-full border font-pretendard text-[12px] font-medium transition-all"
            style={{
              borderColor: editing ? '#00A8E8' : 'rgba(0,0,0,0.12)',
              color: editing ? '#00A8E8' : '#555',
              background: editing ? 'rgba(0,168,232,0.07)' : 'white',
            }}
          >
            {editing ? '취소' : '편집'}
          </button>
        </div>

        {/* ── 나의 K-Dive 활동 통계 (신규) ── */}
        <div>
          <p className="font-pretendard text-[11px] font-bold tracking-[0.1em] uppercase text-muted mb-2.5 px-1">
            My K-Dive
          </p>
          <div className="flex gap-3">
            <StatCard
              count={likedTrackIds?.size ?? 0}
              label={'좋아한\n트랙'}
              color="rgba(0,168,232,0.08)"
            />
            <StatCard
              count={likedPlaceKeys?.size ?? 0}
              label={'저장한\n명소'}
              color="rgba(0,168,232,0.06)"
            />
            <StatCard
              count={likedFoodKeys?.size ?? 0}
              label={'저장한\n음식점'}
              color="rgba(0,168,232,0.04)"
            />
          </div>
        </div>

        {/* ── 프로필 설정 ── */}
        <div>
          <SectionCard icon="👤" title="프로필 설정">
            <div className="flex flex-col">
              <InputField label="이름" value={name} onChange={setName} placeholder="이름 입력" />
              <InputField label="닉네임" value={nickname} onChange={setNickname} placeholder="닉네임 입력" />
              <InputField label="연락처" value={contact} onChange={setContact} type="tel" placeholder="010-0000-0000" />
              <InputField label="생년월일" value={birthday} onChange={setBirthday} type="date" />

              {/* 성별 */}
              <div className="flex items-center gap-4 py-2">
                <span className="font-pretendard text-[13px] text-muted" style={{ minWidth: 72 }}>성별</span>
                <div className="flex gap-3">
                  {['여성', '남성', '미선택'].map((g) => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => setGender(g)}
                      className="h-8 px-4 rounded-full font-pretendard text-[12px] font-medium border transition-all"
                      style={{
                        borderColor: gender === g ? '#00A8E8' : 'rgba(0,0,0,0.10)',
                        color: gender === g ? '#00A8E8' : '#888',
                        background: gender === g ? 'rgba(0,168,232,0.08)' : 'white',
                      }}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              {editing && (
                <div className="mt-4 pt-4 border-t border-[rgba(0,0,0,0.06)] flex justify-end">
                  <button
                    type="button"
                    onClick={handleSaveProfile}
                    className="h-9 px-5 rounded-full font-pretendard text-[13px] font-bold text-white transition-all hover:-translate-y-px"
                    style={{ background: '#00A8E8' }}
                  >
                    저장하기
                  </button>
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        {/* ── 언어 설정 ── */}
        <div>
          <SectionCard icon="🌐" title="언어 설정">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-pretendard text-[13px] text-text font-medium">
                  {language === 'ko' ? '한국어' : 'English'}
                </p>
                <p className="font-pretendard text-[12px] text-muted mt-0.5">
                  앱 표시 언어를 선택하세요
                </p>
              </div>
              <div className="flex items-center gap-2.5">
                <span
                  className="font-pretendard text-[12px] font-medium"
                  style={{ color: language === 'ko' ? '#00A8E8' : '#aaa' }}
                >
                  한국어
                </span>
                <Toggle
                  checked={language === 'en'}
                  onChange={(v) => { setLanguage(v ? 'en' : 'ko'); saveToStorage(); }}
                />
                <span
                  className="font-pretendard text-[12px] font-medium"
                  style={{ color: language === 'en' ? '#00A8E8' : '#aaa' }}
                >
                  English
                </span>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* ── Surfer 설정 ── */}
        <div>
          <SectionCard icon="🤖" title="Surfer 설정">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-pretendard text-[13px] text-text font-medium">
                  Surfer AI 어시스턴트
                </p>
                <p className="font-pretendard text-[12px] text-muted mt-0.5">
                  {surferOn
                    ? 'Surfer가 활성화되어 있어요 — 여행 가이드를 도와드려요'
                    : 'Surfer가 비활성화되어 있어요'}
                </p>
              </div>
              <div className="flex items-center gap-2.5">
                <span
                  className="font-pretendard text-[12px] font-medium"
                  style={{ color: surferOn ? '#00A8E8' : '#aaa' }}
                >
                  {surferOn ? 'ON' : 'OFF'}
                </span>
                <Toggle
                  checked={surferOn}
                  onChange={(v) => { setSurferOn(v); saveToStorage(); }}
                />
              </div>
            </div>
          </SectionCard>
        </div>

        {/* ── 알림 설정 (신규) ── */}
        <div>
          <SectionCard icon="🔔" title="알림 설정">
            <div className="flex flex-col gap-4">
              {[
                {
                  key: 'email',
                  label: '이메일 알림',
                  desc: '새로운 큐레이션 업데이트 알림',
                  checked: emailNotif,
                  onChange: (v) => { setEmailNotif(v); saveToStorage(); },
                },
                {
                  key: 'push',
                  label: '푸시 알림',
                  desc: 'K-Dive 새 소식을 푸시로 받아요',
                  checked: pushNotif,
                  onChange: (v) => { setPushNotif(v); saveToStorage(); },
                },
                {
                  key: 'marketing',
                  label: '마케팅 수신 동의',
                  desc: '프로모션 및 이벤트 정보 수신',
                  checked: marketingNotif,
                  onChange: (v) => { setMarketingNotif(v); saveToStorage(); },
                },
              ].map((item) => (
                <div key={item.key} className="flex items-center justify-between">
                  <div>
                    <p className="font-pretendard text-[13px] text-text font-medium">{item.label}</p>
                    <p className="font-pretendard text-[12px] text-muted mt-0.5">{item.desc}</p>
                  </div>
                  <Toggle checked={item.checked} onChange={item.onChange} />
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        {/* ── 비밀번호 변경 ── */}
        <div>
          <SectionCard icon="🔒" title="비밀번호 변경">
            <form onSubmit={handleChangePw} className="flex flex-col gap-0">
              <InputField
                label="현재 비밀번호"
                value={currentPw}
                onChange={setCurrentPw}
                type="password"
                placeholder="현재 비밀번호 입력"
              />
              <InputField
                label="새 비밀번호"
                value={newPw}
                onChange={setNewPw}
                type="password"
                placeholder="새 비밀번호 (8자 이상)"
              />
              <InputField
                label="비밀번호 확인"
                value={confirmPw}
                onChange={setConfirmPw}
                type="password"
                placeholder="새 비밀번호 재입력"
              />

              {pwMsg && (
                <p
                  className="font-pretendard text-[12px] mt-2 ml-[88px]"
                  style={{ color: pwMsg.startsWith('✓') ? '#00A8E8' : '#EC3535' }}
                >
                  {pwMsg}
                </p>
              )}

              <div className="mt-4 pt-4 border-t border-[rgba(0,0,0,0.06)] flex justify-end">
                <button
                  type="submit"
                  className="h-9 px-5 rounded-full font-pretendard text-[13px] font-bold text-white transition-all hover:-translate-y-px"
                  style={{ background: '#00A8E8' }}
                >
                  변경하기
                </button>
              </div>
            </form>
          </SectionCard>
        </div>

        {/* ── 회원 탈퇴 ── */}
        <div>
          <SectionCard icon="⚠️" title="회원 탈퇴">
            {!deleteConfirm ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-pretendard text-[13px] text-text font-medium">계정 삭제</p>
                  <p className="font-pretendard text-[12px] text-muted mt-0.5">
                    탈퇴 시 모든 데이터가 삭제되며 복구할 수 없어요
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setDeleteConfirm(true)}
                  className="h-8 px-4 rounded-full border font-pretendard text-[12px] font-medium transition-all hover:bg-red-50"
                  style={{ borderColor: 'rgba(236,53,53,0.3)', color: '#EC3535' }}
                >
                  탈퇴하기
                </button>
              </div>
            ) : (
              <div className="rounded-xl bg-red-50 border border-red-100 p-4">
                <p className="font-pretendard text-[13px] text-[#EC3535] font-bold mb-1">
                  정말 탈퇴하시겠어요?
                </p>
                <p className="font-pretendard text-[12px] text-[#c0392b] mb-4 leading-relaxed">
                  좋아한 음악, 저장한 장소, 방문 기록 등 모든 데이터가<br />
                  영구 삭제되며 복구할 수 없어요.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(false)}
                    className="h-8 px-4 rounded-full border border-[rgba(0,0,0,0.12)] font-pretendard text-[12px] text-[#555] bg-white transition-all hover:bg-gray-50"
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    className="h-8 px-4 rounded-full font-pretendard text-[12px] font-bold text-white transition-all"
                    style={{ background: '#EC3535' }}
                  >
                    탈퇴 확인
                  </button>
                </div>
              </div>
            )}
          </SectionCard>
        </div>

        </div>{/* flex flex-col gap-4 */}
        </div>{/* kd-history-scroll */}
      </div>
    </section>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';
import { loginUser, registerUser } from '@/utils/authApi';

/* ─── 인풋 공통 스타일 ─────────────────────── */
const inputStyle = {
  width: '100%',
  height: 48,
  padding: '0 16px',
  fontSize: 14,
  border: '1px solid rgba(0,0,0,0.12)',
  borderRadius: 10,
  outline: 'none',
  background: '#fafafa',
  color: '#111111',
  transition: 'border-color 0.15s, box-shadow 0.15s',
  boxSizing: 'border-box',
};

function Input({ label, type = 'text', value, onChange, placeholder, autoComplete }) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#555555', letterSpacing: '0.03em' }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          ...inputStyle,
          borderColor: focused ? '#00A8E8' : 'rgba(0,0,0,0.12)',
          boxShadow: focused ? '0 0 0 3px rgba(0,168,232,0.12)' : 'none',
          background: focused ? '#ffffff' : '#fafafa',
        }}
      />
    </div>
  );
}

/* ─── 메인 컴포넌트 ────────────────────────── */
export default function AuthSection() {
  const { authVisible, authInitialTab, guestMode, loggedIn, loginToSurfy } = useKdive();

  const [tab, setTab] = useState(authInitialTab);

  // 외부에서 탭이 바뀌면 (로그인하기 / 회원가입하기 버튼) 동기화
  useEffect(() => { setTab(authInitialTab); }, [authInitialTab]);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (loggedIn || guestMode || !authVisible) return null;

  const clearError = () => setError('');

  const switchTab = (next) => {
    setTab(next);
    setError('');
    setPassword('');
    setConfirm('');
  };

  /* 로그인 */
  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) { setError('이메일과 비밀번호를 입력해주세요.'); return; }
    setLoading(true);
    setError('');
    try {
      const data = await loginUser({ email, password });
      loginToSurfy(data.user ?? { email });
    } catch (err) {
      setError('이메일 또는 비밀번호를 확인해주세요.');
    } finally {
      setLoading(false);
    }
  };

  /* 회원가입 */
  const handleSignup = async (e) => {
    e.preventDefault();
    if (!email || !password || !confirm) { setError('모든 항목을 입력해주세요.'); return; }
    if (password.length < 8) { setError('비밀번호는 8자 이상이어야 합니다.'); return; }
    if (password !== confirm) { setError('비밀번호가 일치하지 않습니다.'); return; }
    setLoading(true);
    setError('');
    try {
      const data = await registerUser({ name, email, password });
      loginToSurfy(data.user ?? { name, email });
    } catch (err) {
      setError(err.message === 'request_failed'
        ? '회원가입에 실패했습니다. 잠시 후 다시 시도해주세요.'
        : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      id="authSection"
      className="scroll-mt-[70px]"
      style={{
        minHeight: 'calc(100vh - 61px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'clamp(48px,8vh,96px) clamp(20px,5vw,48px)',
        background: '#ffffff',
      }}
    >
      {/* 섹션 헤더 */}
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <p
          className="font-mono"
          style={{
            fontSize: 12,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: '#00A8E8',
            marginBottom: 12,
          }}
        >
          Keep exploring K-Dive
        </p>
        <h2
          className="font-serif"
          style={{ fontSize: 36, lineHeight: 1.1, color: '#111111', marginBottom: 10 }}
        >
          {tab === 'login' ? 'Welcome back' : 'Join K-Dive'}
        </h2>
        <p style={{ fontSize: 16, color: '#888888', lineHeight: 1.6 }}>
          {tab === 'login'
            ? '계속해서 나만의 한국 여행을 이어가세요.'
            : '가입하고 K-Pop에서 시작하는 여행을 경험해보세요.'}
        </p>
      </div>

      {/* 카드 */}
      <div
        style={{
          width: '100%',
          maxWidth: 440,
          background: '#ffffff',
          border: '1px solid rgba(0,0,0,0.08)',
          borderRadius: 20,
          boxShadow: '0 8px 40px rgba(0,0,0,0.06)',
          overflow: 'hidden',
        }}
      >
        {/* 탭 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            borderBottom: '1px solid rgba(0,0,0,0.08)',
          }}
        >
          {[
            { key: 'login', label: '로그인' },
            { key: 'signup', label: '회원가입' },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => switchTab(key)}
              style={{
                height: 52,
                border: 'none',
                background: 'transparent',
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
                color: tab === key ? '#00A8E8' : '#aaaaaa',
                borderBottom: tab === key ? '2px solid #00A8E8' : '2px solid transparent',
                transition: 'color 0.15s, border-color 0.15s',
                letterSpacing: '0.02em',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 폼 */}
        <div style={{ padding: 'clamp(24px,4vh,36px) 32px 32px' }}>
          <form
            onSubmit={tab === 'login' ? handleLogin : handleSignup}
            style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
          >
            {/* 이름 — 회원가입 전용 */}
            {tab === 'signup' && (
              <Input
                label="이름 (선택)"
                value={name}
                onChange={(e) => { setName(e.target.value); clearError(); }}
                placeholder="홍길동"
                autoComplete="name"
              />
            )}

            <Input
              label="이메일"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); clearError(); }}
              placeholder="hello@kdive.com"
              autoComplete="email"
            />

            <Input
              label="비밀번호"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clearError(); }}
              placeholder={tab === 'login' ? '비밀번호 입력' : '8자 이상'}
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            />

            {/* 비밀번호 확인 — 회원가입 전용 */}
            {tab === 'signup' && (
              <Input
                label="비밀번호 확인"
                type="password"
                value={confirm}
                onChange={(e) => { setConfirm(e.target.value); clearError(); }}
                placeholder="비밀번호 재입력"
                autoComplete="new-password"
              />
            )}

            {/* 에러 메시지 */}
            {error && (
              <p style={{ fontSize: 12, color: '#EC3535', marginTop: -4 }}>
                {error}
              </p>
            )}

            {/* 제출 버튼 */}
            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: 8,
                height: 50,
                width: '100%',
                borderRadius: 12,
                border: 'none',
                background: loading ? '#88d4f5' : 'linear-gradient(135deg, #00A8E8, #006FE8)',
                color: '#ffffff',
                fontSize: 15,
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'opacity 0.15s, transform 0.15s',
                letterSpacing: '0.02em',
              }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.opacity = '0.9'; }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
            >
              {loading
                ? (tab === 'login' ? '로그인 중...' : '가입 중...')
                : (tab === 'login' ? '로그인' : '회원가입')}
            </button>
          </form>

          {/* 탭 전환 링크 */}
          <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: '#888888' }}>
            {tab === 'login' ? '아직 계정이 없으신가요? ' : '이미 계정이 있으신가요? '}
            <button
              type="button"
              onClick={() => switchTab(tab === 'login' ? 'signup' : 'login')}
              style={{
                border: 'none',
                background: 'none',
                color: '#00A8E8',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
                padding: 0,
              }}
            >
              {tab === 'login' ? '회원가입' : '로그인'}
            </button>
          </p>
        </div>
      </div>
    </section>
  );
}

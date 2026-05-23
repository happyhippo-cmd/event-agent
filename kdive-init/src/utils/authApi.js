/**
 * Auth API
 *
 * NEXT_PUBLIC_USE_MOCK_AUTH=true 이면 백엔드 없이 localStorage로 동작합니다.
 * 실제 백엔드 연결 시 .env.local 에서 해당 변수를 제거하거나 false로 바꾸세요.
 *
 *   NEXT_PUBLIC_AUTH_API_URL=http://localhost:8000
 *   NEXT_PUBLIC_USE_MOCK_AUTH=true   ← 목 모드 활성화
 */

/* ─── Mock (localStorage 기반) ─────────────────────── */

const MOCK_USERS_KEY = 'kdive-mock-users';

function getMockUsers() {
  try {
    return JSON.parse(localStorage.getItem(MOCK_USERS_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveMockUsers(users) {
  localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(users));
}

function delay(ms = 600) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function mockLogin({ email, password }) {
  await delay();
  const users = getMockUsers();
  const user = users.find((u) => u.email === email);
  if (!user) throw new Error('이메일 또는 비밀번호를 확인해주세요.');
  if (user.password !== password) throw new Error('이메일 또는 비밀번호를 확인해주세요.');
  return { user: { email: user.email, name: user.name } };
}

async function mockRegister({ name, email, password }) {
  await delay();
  const users = getMockUsers();
  if (users.find((u) => u.email === email)) {
    throw new Error('이미 사용 중인 이메일입니다.');
  }
  users.push({ name: name || '', email, password });
  saveMockUsers(users);
  return { user: { email, name: name || '' } };
}

async function mockLogout() {
  await delay(200);
}

/* ─── Real API ──────────────────────────────────────── */

const BASE_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_AUTH_API_URL) ||
  'http://localhost:8000';

async function request(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message =
      data.detail || data.message || data.non_field_errors?.[0] || 'request_failed';
    throw new Error(message);
  }

  return data;
}

/* ─── 환경변수로 mock/real 전환 ─────────────────────── */

const USE_MOCK =
  typeof process !== 'undefined' &&
  process.env.NEXT_PUBLIC_USE_MOCK_AUTH === 'true';

export function loginUser({ email, password }) {
  return USE_MOCK
    ? mockLogin({ email, password })
    : request('/api/auth/login/', { email, password });
}

export function registerUser({ name, email, password }) {
  return USE_MOCK
    ? mockRegister({ name, email, password })
    : request('/api/auth/register/', { name, email, password });
}

export function logoutUser() {
  return USE_MOCK
    ? mockLogout()
    : fetch(`${BASE_URL}/api/auth/logout/`, { method: 'POST', credentials: 'include' });
}

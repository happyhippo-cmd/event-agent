'use client';

import { getSurfyApiUrl } from './surfyApi';

const HISTORY_ITEMS_PATH = '/api/history-items/';

async function requestHistory(path, options = {}) {
  const response = await fetch(getSurfyApiUrl(path), {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`history_api_${response.status}`);
  }

  if (response.status === 204) return null;

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function getHistoryItemPath(key) {
  return `${HISTORY_ITEMS_PATH}${encodeURIComponent(key)}/`;
}

export function fetchHistoryItems(options = {}) {
  return requestHistory(HISTORY_ITEMS_PATH, {
    method: 'GET',
    signal: options.signal,
  });
}

export function postHistoryItem(payload) {
  return requestHistory(HISTORY_ITEMS_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteHistoryItem(itemKey) {
  return requestHistory(getHistoryItemPath(itemKey), {
    method: 'DELETE',
  });
}

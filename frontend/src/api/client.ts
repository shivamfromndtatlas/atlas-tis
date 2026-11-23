/**
 * Thin fetch wrapper for the TIS API.
 * - Auth is httpOnly cookies, so every call sends credentials.
 * - Unsafe methods echo the CSRF cookie in X-CSRFToken.
 * - A 401 triggers one silent refresh (single-flight) and a retry.
 */
import type { components } from './schema';

export type Schemas = components['schemas'];

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown };
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, body: Partial<ApiErrorBody> | null) {
    super(body?.error?.message ?? `Request failed (${status})`);
    this.status = status;
    this.code = body?.error?.code ?? 'ERROR';
    this.details = body?.error?.details ?? null;
  }

  /** Field errors from a VALIDATION_ERROR response, flattened to strings. */
  fieldErrors(): Record<string, string> {
    if (!this.details || typeof this.details !== 'object' || Array.isArray(this.details)) return {};
    return Object.fromEntries(
      Object.entries(this.details as Record<string, unknown>).map(([k, v]) => [
        k,
        Array.isArray(v) ? v.join(' ') : String(v),
      ]),
    );
  }
}

const BASE = '/api/v1';
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const NO_REFRESH = ['/auth/login/', '/auth/refresh/', '/auth/otp/', '/auth/mfa/verify/', '/auth/password/'];

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

let csrfReady: Promise<void> | null = null;
async function ensureCsrf(): Promise<string> {
  if (!readCookie('csrftoken')) {
    csrfReady ??= fetch(`${BASE}/auth/csrf/`, { credentials: 'include' }).then(() => undefined);
    await csrfReady;
    csrfReady = null;
  }
  return readCookie('csrftoken') ?? '';
}

let refreshing: Promise<boolean> | null = null;
async function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    const csrf = await ensureCsrf();
    const res = await fetch(`${BASE}/auth/refresh/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': csrf },
    });
    return res.ok;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** Listeners notified when the session is definitively gone (refresh failed). */
const sessionLostListeners = new Set<() => void>();
export function onSessionLost(fn: () => void): () => void {
  sessionLostListeners.add(fn);
  return () => sessionLostListeners.delete(fn);
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const method = (opts.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = { Accept: 'application/json' };
  let body: BodyInit | undefined;

  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  if (UNSAFE.has(method)) headers['X-CSRFToken'] = await ensureCsrf();

  const url = new URL(`${BASE}${path}`, window.location.origin);
  Object.entries(opts.query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  });

  const res = await fetch(url.toString().replace(window.location.origin, ''), {
    method,
    headers,
    body,
    credentials: 'include',
    signal: opts.signal,
  });

  if (res.status === 401 && !retried && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) return api<T>(path, opts, true);
    sessionLostListeners.forEach((fn) => fn());
  }
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

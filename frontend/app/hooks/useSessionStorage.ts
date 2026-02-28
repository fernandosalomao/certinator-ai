"use client";

/**
 * useSessionStorage — Generic sessionStorage-backed useState hook.
 *
 * Reads the initial value from sessionStorage (falling back to the provided
 * default), and writes every state update back to sessionStorage so data
 * survives page reloads.
 *
 * Features (G15 — Frontend Error Resilience):
 *  - Graceful degradation: if sessionStorage is unavailable (SSR, private
 *    browsing quota exceeded) the hook behaves like plain useState.
 *  - Staleness guard: an optional `maxAgeMs` parameter causes the stored
 *    value to be ignored if older than the specified duration.
 *  - `clear()` helper to explicitly remove the key.
 */

import { useState, useCallback, useEffect, useRef } from "react";

/** Wrapper stored in sessionStorage to track age. */
interface StorageEntry<T> {
  value: T;
  timestamp: number;
}

/** Default max age: 30 minutes. */
const DEFAULT_MAX_AGE_MS = 30 * 60 * 1000;

/**
 * Safe sessionStorage read — returns `undefined` if anything fails.
 */
function readStorage<T>(key: string, maxAgeMs: number): T | undefined {
  try {
    const raw = globalThis.sessionStorage?.getItem(key);
    if (raw == null) return undefined;

    const entry: StorageEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.timestamp > maxAgeMs) {
      globalThis.sessionStorage?.removeItem(key);
      return undefined;
    }
    return entry.value;
  } catch {
    return undefined;
  }
}

/**
 * Safe sessionStorage write — silently no-ops if storage is unavailable.
 */
function writeStorage<T>(key: string, value: T): void {
  try {
    const entry: StorageEntry<T> = { value, timestamp: Date.now() };
    globalThis.sessionStorage?.setItem(key, JSON.stringify(entry));
  } catch {
    // Quota exceeded or private browsing — ignore.
  }
}

/**
 * Safe sessionStorage remove.
 */
function removeStorage(key: string): void {
  try {
    globalThis.sessionStorage?.removeItem(key);
  } catch {
    // Ignore.
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

type UseSessionStorageReturn<T> = [
  /** Current value. */
  T,
  /** Setter — mirrors React's useState setter. */
  (value: T | ((prev: T) => T)) => void,
  /** Explicitly remove the stored value and reset to `initialValue`. */
  () => void,
];

export function useSessionStorage<T>(
  key: string,
  initialValue: T,
  maxAgeMs: number = DEFAULT_MAX_AGE_MS,
): UseSessionStorageReturn<T> {
  // Lazy initialiser reads from sessionStorage once (client-side only).
  const [state, setState] = useState<T>(() => {
    if (typeof window === "undefined") return initialValue;
    return readStorage<T>(key, maxAgeMs) ?? initialValue;
  });

  // Keep key/maxAge refs stable for the write effect.
  const keyRef = useRef(key);
  const maxAgeRef = useRef(maxAgeMs);
  keyRef.current = key;
  maxAgeRef.current = maxAgeMs;

  // Persist whenever state changes (after initial mount).
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    writeStorage(keyRef.current, state);
  }, [state]);

  const clear = useCallback(() => {
    removeStorage(keyRef.current);
    setState(initialValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValue]);

  return [state, setState, clear];
}

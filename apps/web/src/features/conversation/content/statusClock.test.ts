import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { currentSeconds, getNowSeconds, subscribe } from "./statusClock";

const BASE_MS = Date.parse("2026-09-01T12:00:00.000Z");
const BASE_SECONDS = Math.floor(BASE_MS / 1000);

const attached: (() => void)[] = [];

function attach(listener: () => void): () => void {
  const unsubscribe = subscribe(listener);
  attached.push(unsubscribe);
  return unsubscribe;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(BASE_MS);
});

afterEach(() => {
  while (attached.length > 0) attached.pop()?.();
  vi.useRealTimers();
});

describe("the shared status clock", () => {
  it("reads the wall clock in whole seconds", () => {
    expect(currentSeconds()).toBe(BASE_SECONDS);
  });

  it("catches up to the wall clock when the first listener arrives", () => {
    vi.setSystemTime(BASE_MS + 600_000);
    attach(() => {});
    expect(getNowSeconds()).toBe(BASE_SECONDS + 600);
  });

  it("advances one second per tick while a listener is attached", () => {
    attach(() => {});
    vi.advanceTimersByTime(3000);
    expect(getNowSeconds()).toBe(BASE_SECONDS + 3);
  });

  it("notifies every listener on each tick from a single interval", () => {
    const first = vi.fn();
    const second = vi.fn();
    attach(first);
    attach(second);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(2000);
    expect(first).toHaveBeenCalledTimes(2);
    expect(second).toHaveBeenCalledTimes(2);
  });

  it("stops the interval when the last listener leaves", () => {
    const stopFirst = attach(() => {});
    attach(() => {});
    stopFirst();
    expect(vi.getTimerCount()).toBe(1);
    attached.pop()?.();
    expect(vi.getTimerCount()).toBe(0);
  });
});

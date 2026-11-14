/** The HTTP transport's event handler against a fake EventSource (audit B-04): the job's "error" event and the
 *  browser's own connection "error" share one name; only the server's message may reach the app. */
import { afterEach, expect, it, vi } from "vitest";
import { httpTransport } from "../src/api/client";

class FakeES {
  static last: FakeES;
  static CLOSED = 2;
  readyState = 0;
  onerror: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  listeners: Record<string, ((e: Event) => void)[]> = {};
  constructor(public url: string) { FakeES.last = this; }
  addEventListener(t: string, f: (e: Event) => void) { (this.listeners[t] ??= []).push(f); }
  close() { this.readyState = 2; }
  fire(t: string, e: Event) { for (const f of this.listeners[t] ?? []) f(e); if (t === "error") this.onerror?.(); }
}

afterEach(() => { vi.unstubAllGlobals(); });

it("passes the server's error message through and ignores connection-error events", () => {
  vi.stubGlobal("EventSource", FakeES);
  const events: unknown[] = [];
  const errors: Error[] = [];
  httpTransport.events("/jobs/j/events", (e) => events.push(e), (e) => errors.push(e));
  const es = FakeES.last;
  es.fire("planned", new MessageEvent("planned", { data: JSON.stringify({ n: 3 }) }));
  es.fire("error", new MessageEvent("error", { data: JSON.stringify({ message: "job timed out after 300 s" }) }));
  es.fire("error", new Event("error"));            // the connection closing right after: no data
  expect(events).toEqual([{ type: "planned", n: 3 }, { type: "error", message: "job timed out after 300 s" }]);
  expect(errors).toEqual([]);
});

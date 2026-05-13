import { useEffect, useRef, useState } from "react";

type Story = {
  id: string;
  position: number;
  title: string;
  status: string;
  type: string;
  planned_duration: number;
  script_body?: string;
};

type Snap = {
  live_story: Story | null;
  elapsed_seconds: number;
  stories: Story[];
};

function wsUrl() {
  const p = location.protocol === "https:" ? "wss:" : "ws:";
  return `${p}//${location.host}/ws?client=prompter`;
}

type Mirror = "normal" | "h" | "v" | "hv";

const mirrorClass: Record<Mirror, string> = {
  normal: "",
  h: "mirror-h",
  v: "mirror-v",
  hv: "mirror-hv",
};

function fmtMmSs(totalSec: number) {
  const s = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m.toString().padStart(2, "0")}:${r.toString().padStart(2, "0")}`;
}

/** Avoid React state for script/title so live edits do not re-render the scroll column (scroll jitter). */
function applyIfChanged(
  el: HTMLElement | null,
  prevSig: { current: string | null },
  nextSig: string,
  text: string,
) {
  if (!el || prevSig.current === nextSig) return;
  prevSig.current = nextSig;
  el.textContent = text;
}

export default function App() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const scriptElRef = useRef<HTMLDivElement>(null);
  const titleElRef = useRef<HTMLDivElement>(null);
  const velocityRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const elapsedBaseRef = useRef(0);
  const wallAtRef = useRef(performance.now());
  const plannedRef = useRef(0);
  const timeElRef = useRef<HTMLDivElement>(null);
  const scriptSigRef = useRef<string | null>(null);
  const titleSigRef = useRef<string | null>(null);
  const lastStoryId = useRef<string | null>(null);

  const [mirror, setMirror] = useState<Mirror>("normal");
  const [stories, setStories] = useState<Story[]>([]);

  useEffect(() => {
    const tick = () => {
      const el = scrollRef.current;
      if (el && velocityRef.current !== 0) {
        el.scrollTop += velocityRef.current;
      }
      const displayElapsed =
        elapsedBaseRef.current + (performance.now() - wallAtRef.current) / 1000;
      const remaining = Math.max(0, plannedRef.current - Math.floor(displayElapsed));
      const t = timeElRef.current;
      if (t) {
        t.textContent = `Elapsed ${fmtMmSs(displayElapsed)} · Remaining ${fmtMmSs(remaining)}`;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        velocityRef.current += 0.35;
        e.preventDefault();
      }
      if (e.key === "ArrowUp") {
        velocityRef.current -= 0.35;
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl());
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);
      if (msg.type === "bootstrap" || msg.type === "rundown") {
        const snap = (msg.type === "bootstrap" ? msg.rundown : msg.payload) as Snap;
        setStories(Array.isArray(snap.stories) ? snap.stories : []);
        const live = snap.live_story;
        const sid = live?.id ?? null;
        if (sid && sid !== lastStoryId.current) {
          lastStoryId.current = sid;
          velocityRef.current = 0;
          if (scrollRef.current) scrollRef.current.scrollTop = 0;
          scriptSigRef.current = null;
          titleSigRef.current = null;
          applyIfChanged(
            scriptElRef.current,
            scriptSigRef,
            `${sid}\n${live?.script_body ?? ""}`,
            live?.script_body || "",
          );
          applyIfChanged(titleElRef.current, titleSigRef, `${sid}\n${live?.title ?? ""}`, live?.title || "");
          plannedRef.current = live?.planned_duration || 0;
        } else if (live) {
          applyIfChanged(
            scriptElRef.current,
            scriptSigRef,
            `${live.id}\n${live.script_body ?? ""}`,
            live.script_body || "",
          );
          applyIfChanged(titleElRef.current, titleSigRef, `${live.id}\n${live.title}`, live.title);
          plannedRef.current = live.planned_duration || 0;
        } else {
          lastStoryId.current = null;
          velocityRef.current = 0;
          if (scrollRef.current) scrollRef.current.scrollTop = 0;
          scriptSigRef.current = null;
          titleSigRef.current = null;
          applyIfChanged(scriptElRef.current, scriptSigRef, "__idle__", "Waiting for rundown…");
          applyIfChanged(titleElRef.current, titleSigRef, "__idle__", "");
          plannedRef.current = 0;
        }
        elapsedBaseRef.current = snap.elapsed_seconds || 0;
        wallAtRef.current = performance.now();
      }
    };
    return () => ws.close();
  }, []);

  const liveId = stories.find((s) => s.status === "live")?.id ?? null;

  return (
    <>
      <style>{`
        .mirror-h { transform: scaleX(-1); }
        .mirror-v { transform: scaleY(-1); }
        .mirror-hv { transform: scale(-1, -1); }
      `}</style>
      <div className="layout">
        <aside className="segments" aria-label="Rundown segments">
          {stories.length === 0 ? (
            <div className="segments-empty">No rundown loaded</div>
          ) : (
            stories.map((s) => (
              <div
                key={s.id}
                className={
                  "seg" +
                  (s.id === liveId ? " seg-live" : "") +
                  (s.status === "done" ? " seg-done" : "")
                }
              >
                <span className="seg-pos">{s.position}</span>
                <span className="seg-title">{s.title}</span>
                <span className="seg-meta">{s.type}</span>
              </div>
            ))
          )}
        </aside>
        <div className="main-col">
          <div className="hud">
            <div>
              <div>
                <strong ref={titleElRef}>—</strong>
              </div>
              <div ref={timeElRef}>Elapsed 00:00 · Remaining 00:00</div>
            </div>
            <div className="controls">
              {(["normal", "h", "v", "hv"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={mirror === m ? "active" : ""}
                  onClick={() => setMirror(m)}
                >
                  {m === "normal" ? "Normal" : m === "h" ? "Mirror H" : m === "v" ? "Mirror V" : "Mirror HV"}
                </button>
              ))}
            </div>
          </div>
          <div ref={scrollRef} className={`scroll-wrap ${mirrorClass[mirror]}`}>
            <div ref={scriptElRef} className="script" />
          </div>
        </div>
      </div>
    </>
  );
}

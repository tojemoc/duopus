import { useEffect, useMemo, useState } from "react";

type Beat = { category: string; duration: number; note: string };
type Poll = { story_id: number; label: string; segment: string; beats: Beat[]; body: string; updated_at: string };

function storyIdFromPath() {
  const m = window.location.pathname.match(/\/prompter\/(\d+)/);
  return m ? Number(m[1]) : null;
}

function fmtMmSs(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function App() {
  const storyId = storyIdFromPath();
  const [data, setData] = useState<Poll | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!storyId) {
      setErr("Missing story id.");
      return;
    }
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(`/api/prompter/${storyId}`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load script.");
        const j = (await res.json()) as Poll;
        if (alive) {
          setData(j);
          setErr(null);
        }
      } catch (e: any) {
        if (alive) setErr(e?.message || "Failed to load script.");
      }
    };
    void tick();
    const t = window.setInterval(tick, 3000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [storyId]);

  const total = useMemo(() => (data?.beats || []).reduce((a, b) => a + (b.duration || 0), 0), [data]);

  return (
    <div className="wrap">
      <div className="topbar">
        <div className="title">{data ? `${data.segment} · ${data.label}` : "Prompter"}</div>
        <div className="meta">{data ? `Total ${fmtMmSs(total)}` : ""}</div>
      </div>
      {err ? (
        <div className="err">{err}</div>
      ) : (
        <div className="script" aria-label="Script">
          {data?.body || ""}
        </div>
      )}
    </div>
  );
}

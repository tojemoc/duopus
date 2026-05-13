import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type { Beat, BeatCategory, Rundown, Script, Story } from "../types";
import { BeatStrip } from "../components/BeatStrip";
import { useAuth } from "../useAuth";

function fmtMmSs(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

const ALLOWED_BEAT: ReadonlySet<BeatCategory> = new Set(["VO", "ILU", "SYN"]);

function parseBeats(raw: unknown): Beat[] {
  let arr: unknown[] = [];
  if (typeof raw === "string") {
    try {
      const p = JSON.parse(raw || "[]");
      arr = Array.isArray(p) ? p : [];
    } catch {
      return [];
    }
  } else if (Array.isArray(raw)) {
    arr = raw;
  } else {
    return [];
  }
  return arr.map((x: any) => {
    const id = typeof x?.id === "string" && x.id ? x.id : crypto.randomUUID();
    const rawCat = String(x?.category ?? "");
    const category: BeatCategory = ALLOWED_BEAT.has(rawCat as BeatCategory) ? (rawCat as BeatCategory) : "VO";
    let duration = Number(x?.duration);
    if (!Number.isFinite(duration) || duration < 0) duration = 0;
    const note = x?.note == null ? "" : String(x.note);
    return { id, category, duration, note };
  });
}

function defaultBeat(cat: BeatCategory): Beat {
  return { id: crypto.randomUUID(), category: cat, duration: 0, note: "" };
}

export function RundownEditorPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { me } = useAuth();

  const rundownId = Number(id || 0);
  const [rundown, setRundown] = useState<Rundown | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [scripts, setScripts] = useState<Record<number, Script | null>>({});
  const [err, setErr] = useState<string | null>(null);

  const [openStoryId, setOpenStoryId] = useState<number | null>(null);
  const [lockMsg, setLockMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [editBeats, setEditBeats] = useState<Beat[]>([]);
  const [editBeatId, setEditBeatId] = useState<string | null>(null);
  const [editOverride, setEditOverride] = useState<number | "">("");
  const [editTitleIn, setEditTitleIn] = useState(0);
  const [editTitleDur, setEditTitleDur] = useState(5);
  const [editBody, setEditBody] = useState("");

  const load = async () => {
    setErr(null);
    const data = await api<{ rundown: Rundown; stories: any[] }>(`/api/rundowns/${rundownId}/full`);
    setRundown(data.rundown);
    const st: Story[] = data.stories.map((s: any) => ({
      ...s,
      beats: parseBeats(s.beats),
    }));
    setStories(st);
    const sc: Record<number, Script | null> = {};
    for (const s of data.stories) {
      sc[s.id] = s.script || null;
    }
    setScripts(sc);
  };

  useEffect(() => {
    if (!rundownId) return;
    load().catch((e: any) => setErr(e?.message || "Failed to load rundown."));
  }, [rundownId]);

  const totals = useMemo(() => {
    const total = stories.reduce((a, s) => a + (s.planned_duration || 0), 0);
    const ready = stories.filter((s) => s.ready).length;
    return { total, ready, count: stories.length };
  }, [stories]);

  const openEditor = async (storyId: number) => {
    setLockMsg(null);
    setBusy(true);
    try {
      const lr = await api<{ ok: boolean; locked_by_name?: string | null }>(`/api/stories/${storyId}/lock`, {
        method: "POST",
      });
      if (!lr.ok) {
        setLockMsg(`Being edited by ${lr.locked_by_name || "another user"}.`);
        setOpenStoryId(null);
        return;
      }
      const s = stories.find((x) => x.id === storyId);
      if (!s) {
        try {
          await api(`/api/stories/${storyId}/lock`, { method: "DELETE" });
        } catch (e) {
          console.error("Failed to release lock after story disappeared", e);
        }
        setErr("That story is no longer available.");
        return;
      }
      setOpenStoryId(storyId);
      setEditBeats(s.beats);
      setEditBeatId(null);
      setEditOverride(s.planned_duration_override ?? "");
      setEditTitleIn(s.title_in || 0);
      setEditTitleDur(s.title_duration || 5);
      setEditBody(scripts[storyId]?.body || "");
    } catch (e: any) {
      setErr(e?.message || "Failed to lock story.");
    } finally {
      setBusy(false);
    }
  };

  const closeEditor = async () => {
    if (!openStoryId) return;
    try {
      await api(`/api/stories/${openStoryId}/lock`, { method: "DELETE" });
    } catch (e) {
      console.error("Unlock failed", e);
    }
    setOpenStoryId(null);
    setEditBeatId(null);
    await load();
  };

  const saveEditor = async () => {
    if (!openStoryId) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/stories/${openStoryId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          beats: editBeats,
          planned_duration_override: editOverride === "" ? null : Number(editOverride),
          title_in: editTitleIn,
          title_duration: editTitleDur,
        }),
      });
      await api(`/api/scripts/${openStoryId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: editBody }),
      });
      try {
        await api(`/api/stories/${openStoryId}/lock`, { method: "DELETE" });
      } catch (e) {
        console.error("Unlock after save failed", e);
      }
      setOpenStoryId(null);
      await load();
    } catch (e: any) {
      setErr(e?.message || "Failed to save.");
    } finally {
      setBusy(false);
    }
  };

  const beatBeingEdited = editBeats.find((b) => b.id === editBeatId) || null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
          onClick={() => nav("/")}
        >
          ← Rundowns
        </button>
        <div>
          <div className="text-lg font-semibold">{rundown?.title || "Rundown"}</div>
          <div className="text-sm text-slate-600">
            {rundown?.show_date} · {totals.ready}/{totals.count} ready · total {fmtMmSs(totals.total)}
          </div>
        </div>
        <div className="ml-auto">
          <div className="h-2 w-56 rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full bg-emerald-500"
              style={{ width: totals.count ? `${(totals.ready / totals.count) * 100}%` : "0%" }}
            />
          </div>
        </div>
      </div>

      {lockMsg && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {lockMsg}
        </div>
      )}
      {err && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {err}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">Segment</th>
              <th className="px-3 py-2 text-left">Beats</th>
              <th className="px-3 py-2 text-left w-24">Plan</th>
              <th className="px-3 py-2 text-left w-24">Ready</th>
              <th className="px-3 py-2 text-left w-40">Lock</th>
              <th className="px-3 py-2 text-left w-36"></th>
            </tr>
          </thead>
          <tbody>
            {stories.map((s) => {
              const isIntro = s.segment === "Intro";
              return (
                <tr key={s.id} className={isIntro ? "bg-slate-50" : ""}>
                  <td className="px-3 py-2 text-slate-600">{s.position}</td>
                  <td className="px-3 py-2">
                    <div className="font-semibold text-slate-900">{s.segment}</div>
                    <div className="text-xs text-slate-600">{s.label}</div>
                    {isIntro && (
                      <span className="mt-1 inline-flex rounded-full bg-slate-200 px-2 py-0.5 text-[11px] text-slate-700">
                        Tech
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <BeatStrip beats={s.beats} onChange={() => {}} onEditBeat={() => {}} />
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-700">{fmtMmSs(s.planned_duration)}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium ring-1",
                        s.ready
                          ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                          : "bg-slate-50 text-slate-700 ring-slate-200",
                      ].join(" ")}
                      onClick={async () => {
                        await api(`/api/stories/${s.id}/ready`, {
                          method: "PATCH",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ ready: !s.ready }),
                        });
                        await load();
                      }}
                    >
                      {s.ready ? "✓ Ready" : "Mark ready"}
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    {s.locked_by ? (
                      <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">
                        <span className="h-2 w-2 rounded-full bg-amber-500" />
                        Locked
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-2">
                      <a
                        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50"
                        href={`/prompter/${s.id}`}
                        target="_blank"
                        rel="noreferrer"
                        title="Open prompter"
                      >
                        Prompter
                      </a>
                      <button
                        type="button"
                        className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        disabled={busy}
                        onClick={() => openEditor(s.id)}
                      >
                        Edit
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {openStoryId && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
          <div className="flex items-center gap-3">
            <div className="font-semibold">Edit story</div>
            <div className="text-sm text-slate-600">
              {stories.find((s) => s.id === openStoryId)?.label}
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
                onClick={closeEditor}
                disabled={busy}
              >
                Close
              </button>
              <button
                type="button"
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                onClick={saveEditor}
                disabled={busy}
              >
                Save
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium text-slate-700">Beat strip</div>
            <BeatStrip
              beats={editBeats}
              onChange={setEditBeats}
              onEditBeat={(bid) => setEditBeatId(bid)}
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                onClick={() => setEditBeats((b) => [...b, defaultBeat("VO")])}
              >
                + VO
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                onClick={() => setEditBeats((b) => [...b, defaultBeat("ILU")])}
              >
                + ILU
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                onClick={() => setEditBeats((b) => [...b, defaultBeat("SYN")])}
              >
                + SYN
              </button>
              <div className="ml-auto text-xs text-slate-500">
                Drag chips to reorder. Click a chip to edit.
              </div>
            </div>
          </div>

          {beatBeingEdited && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm font-medium">Edit beat</div>
              <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700">Category</label>
                  <select
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                    value={beatBeingEdited.category}
                    onChange={(e) => {
                      const v = e.target.value as BeatCategory;
                      setEditBeats((prev) => prev.map((b) => (b.id === beatBeingEdited.id ? { ...b, category: v } : b)));
                    }}
                  >
                    {(["VO", "ILU", "SYN"] as const).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Duration (seconds)</label>
                  <input
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                    type="number"
                    value={beatBeingEdited.duration}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setEditBeats((prev) => prev.map((b) => (b.id === beatBeingEdited.id ? { ...b, duration: v } : b)));
                    }}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Note</label>
                  <input
                    className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                    value={beatBeingEdited.note}
                    onChange={(e) => {
                      const v = e.target.value;
                      setEditBeats((prev) => prev.map((b) => (b.id === beatBeingEdited.id ? { ...b, note: v } : b)));
                    }}
                  />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                  onClick={() => {
                    setEditBeats((prev) => prev.filter((b) => b.id !== beatBeingEdited.id));
                    setEditBeatId(null);
                  }}
                >
                  Remove
                </button>
                <button
                  type="button"
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                  onClick={() => setEditBeatId(null)}
                >
                  Done
                </button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700">Title in (s)</label>
              <input
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                type="number"
                value={editTitleIn}
                onChange={(e) => setEditTitleIn(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Title duration (s)</label>
              <input
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                type="number"
                value={editTitleDur}
                onChange={(e) => setEditTitleDur(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Manual duration override (s)</label>
              <input
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
                type="number"
                value={editOverride}
                onChange={(e) => setEditOverride(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="(auto from beats)"
              />
              <div className="mt-1 text-xs text-slate-500">Used only if all beat durations are 0.</div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Script</label>
            <textarea
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono min-h-[240px]"
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
            />
          </div>
        </div>
      )}
    </div>
  );
}


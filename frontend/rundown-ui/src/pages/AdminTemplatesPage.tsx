import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type Beat = { id: string; category: "VO" | "ILU" | "SYN"; duration: number; note: string };
type Template = {
  id: number;
  name: string;
  recurrence: "daily" | "weekdays" | "weekly";
  recurrence_day: number | null;
  auto_generate_days_ahead: number;
};

type Slot = {
  position: number;
  label: string;
  segment: string;
  planned_duration: number;
  title_in: number;
  title_duration: number;
  notes: string;
  beats: Beat[];
};

const VALID_BEAT_CATEGORIES = new Set<Beat["category"]>(["VO", "ILU", "SYN"]);

function localYmd(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function makeBeatSeq(categories: string): Beat[] {
  const tokens = categories
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const cats = tokens.filter((t): t is Beat["category"] => VALID_BEAT_CATEGORIES.has(t as Beat["category"]));
  return cats.map((c) => ({ id: crypto.randomUUID(), category: c, duration: 0, note: "" }));
}

export function AdminTemplatesPage() {
  const [rows, setRows] = useState<Template[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [recurrence, setRecurrence] = useState<Template["recurrence"]>("daily");
  const [recDay, setRecDay] = useState<number | "">("");
  const [ahead, setAhead] = useState(1);
  const [slots, setSlots] = useState<Slot[]>([]);

  const load = async () => {
    setErr(null);
    const data = await api<Template[]>("/api/templates");
    setRows(data);
  };

  useEffect(() => {
    load().catch((e: any) => setErr(e?.message || "Failed to load templates."));
  }, []);

  const addSlot = () => {
    const pos = (slots.at(-1)?.position || 0) + 1;
    setSlots((s) => [
      ...s,
      {
        position: pos,
        label: `Story ${pos}`,
        segment: "Story",
        planned_duration: 0,
        title_in: 0,
        title_duration: 5,
        notes: "",
        beats: makeBeatSeq("VO SYN VO"),
      },
    ]);
  };

  const create = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api("/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          recurrence,
          recurrence_day: recurrence === "weekly" ? (recDay === "" ? null : Number(recDay)) : null,
          auto_generate_days_ahead: ahead,
          slots,
        }),
      });
      setName("");
      setSlots([]);
      await load();
    } catch (e: any) {
      setErr(e?.message || "Failed to create template.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold">Templates</div>
        <div className="text-sm text-slate-600 mt-1">Defines default slot list and beat sequences.</div>
      </div>

      {err && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {err}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <div className="font-medium">Create template</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-slate-700">Name</label>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Večerné správy 18:00"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Recurrence</label>
            <select
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
              value={recurrence}
              onChange={(e) => setRecurrence(e.target.value as any)}
            >
              <option value="daily">daily</option>
              <option value="weekdays">weekdays</option>
              <option value="weekly">weekly</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Days ahead</label>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              type="number"
              value={ahead}
              onChange={(e) => setAhead(Number(e.target.value))}
            />
          </div>
        </div>
        {recurrence === "weekly" && (
          <div className="max-w-xs">
            <label className="block text-xs font-medium text-slate-700">Weekly day (0=Mon…6=Sun)</label>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              type="number"
              value={recDay}
              onChange={(e) => setRecDay(e.target.value === "" ? "" : Number(e.target.value))}
            />
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="text-sm font-medium">Slots</div>
          <button
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
            type="button"
            onClick={addSlot}
          >
            + Slot
          </button>
        </div>

        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-2 py-2 text-left w-14">Pos</th>
                <th className="px-2 py-2 text-left">Label</th>
                <th className="px-2 py-2 text-left w-40">Segment</th>
                <th className="px-2 py-2 text-left w-44">Beats (cats)</th>
                <th className="px-2 py-2 text-left w-16"></th>
              </tr>
            </thead>
            <tbody>
              {slots.map((s, idx) => (
                <tr key={idx} className="border-t border-slate-100">
                  <td className="px-2 py-2">
                    <input
                      className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                      type="number"
                      value={s.position}
                      onChange={(e) =>
                        setSlots((prev) => prev.map((x, i) => (i === idx ? { ...x, position: Number(e.target.value) } : x)))
                      }
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                      value={s.label}
                      onChange={(e) => setSlots((prev) => prev.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)))}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                      value={s.segment}
                      onChange={(e) => setSlots((prev) => prev.map((x, i) => (i === idx ? { ...x, segment: e.target.value } : x)))}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm font-mono"
                      value={s.beats.map((b) => b.category).join(" ")}
                      onChange={(e) =>
                        setSlots((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, beats: makeBeatSeq(e.target.value) } : x)),
                        )
                      }
                    />
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button
                      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50"
                      type="button"
                      onClick={() => setSlots((prev) => prev.filter((_, i) => i !== idx))}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <button
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          type="button"
          onClick={create}
          disabled={busy || !name.trim()}
        >
          Create template
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 text-left w-16">ID</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left w-28">Rule</th>
              <th className="px-3 py-2 text-left w-28">Ahead</th>
              <th className="px-3 py-2 text-left w-52"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <TemplateRow key={t.id} t={t} onChange={load} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TemplateRow({ t, onChange }: { t: Template; onChange: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [dateStr, setDateStr] = useState(() => localYmd());

  const gen = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/templates/${t.id}/generate?date=${encodeURIComponent(dateStr)}`, { method: "POST" });
      await onChange();
    } catch (e: any) {
      setErr(e?.message || "Failed to generate.");
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!confirm(`Delete template ${t.name}?`)) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/templates/${t.id}`, { method: "DELETE" });
      await onChange();
    } catch (e: any) {
      setErr(e?.message || "Failed to delete.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-t border-slate-100">
      <td className="px-3 py-2 text-slate-600">{t.id}</td>
      <td className="px-3 py-2 font-medium">{t.name}</td>
      <td className="px-3 py-2 text-slate-700">{t.recurrence}</td>
      <td className="px-3 py-2 text-slate-700">{t.auto_generate_days_ahead}</td>
      <td className="px-3 py-2">
        <div className="flex items-center justify-end gap-2">
          <input
            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
            type="date"
            value={dateStr}
            onChange={(e) => setDateStr(e.target.value)}
          />
          <button
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
            type="button"
            onClick={gen}
            disabled={busy}
          >
            Generate
          </button>
          <button
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
            type="button"
            onClick={del}
            disabled={busy}
          >
            Delete
          </button>
        </div>
        {err && <div className="mt-1 text-xs text-rose-700 text-right">{err}</div>}
      </td>
    </tr>
  );
}


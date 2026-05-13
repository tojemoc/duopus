import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Rundown } from "../types";

function localYmd(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function RundownListPage() {
  const [rows, setRows] = useState<Rundown[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Rundown[]>("/api/rundowns")
      .then(setRows)
      .catch((e: any) => setErr(e?.message || "Failed to load rundowns."));
  }, []);

  const today = localYmd();
  const { todayItems, futureItems, pastItems } = useMemo(() => {
    const todayItems = rows.filter((r) => r.show_date === today);
    const futureItems = rows.filter((r) => r.show_date > today);
    const pastItems = rows.filter((r) => r.show_date < today);
    return { todayItems, futureItems, pastItems };
  }, [rows, today]);

  return (
    <div className="space-y-6">
      <div>
        <div className="text-lg font-semibold">Rundowns</div>
        <div className="text-sm text-slate-600 mt-1">Today first, everything else collapsible.</div>
      </div>

      {err && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {err}
        </div>
      )}

      <section>
        <div className="flex items-center justify-between">
          <div className="font-medium">Today</div>
        </div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {todayItems.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
              No rundown for today yet.
            </div>
          ) : (
            todayItems.map((r) => (
              <Link
                key={r.id}
                to={`/rundown/${r.id}`}
                className="rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300"
              >
                <div className="flex items-center gap-2">
                  <div className="font-semibold">{r.title}</div>
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{r.status}</span>
                </div>
                <div className="mt-1 text-sm text-slate-600">{r.show_date}</div>
              </Link>
            ))
          )}
        </div>
      </section>

      <details className="group rounded-xl border border-slate-200 bg-white p-4" open={futureItems.length > 0}>
        <summary className="cursor-pointer select-none font-medium">
          Future <span className="text-slate-500 text-sm">({futureItems.length})</span>
        </summary>
        <div className="mt-3 space-y-2">
          {futureItems.map((r) => (
            <Link key={r.id} to={`/rundown/${r.id}`} className="block rounded-lg px-3 py-2 hover:bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="font-medium">{r.title}</div>
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{r.status}</span>
                <div className="ml-auto text-sm text-slate-600">{r.show_date}</div>
              </div>
            </Link>
          ))}
        </div>
      </details>

      <details className="group rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer select-none font-medium">
          Past <span className="text-slate-500 text-sm">({pastItems.length})</span>
        </summary>
        <div className="mt-3 space-y-2">
          {pastItems.map((r) => (
            <Link key={r.id} to={`/rundown/${r.id}`} className="block rounded-lg px-3 py-2 hover:bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="font-medium">{r.title}</div>
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{r.status}</span>
                <div className="ml-auto text-sm text-slate-600">{r.show_date}</div>
              </div>
            </Link>
          ))}
        </div>
      </details>
    </div>
  );
}


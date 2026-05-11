import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  type DragEndEvent,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import type { Rundown, RundownSnapshot, Story } from "./types";

const api = (path: string, init?: RequestInit) => fetch(path, init);

function wsUrl(client: string) {
  const p = location.protocol === "https:" ? "wss:" : "ws:";
  return `${p}//${location.host}/ws?client=${encodeURIComponent(client)}`;
}

function SortableRow({
  story,
  selected,
  onSelect,
}: {
  story: Story;
  selected: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: story.id,
  });
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };
  const cls =
    story.status === "live"
      ? "row-live"
      : story.status === "done"
        ? "row-done"
        : "";
  return (
    <tr
      ref={setNodeRef}
      style={style}
      className={`${cls} ${selected ? "row-selected" : ""}`}
      onClick={onSelect}
    >
      <td {...attributes} {...listeners} style={{ cursor: "grab", width: 36 }}>
        ⋮
      </td>
      <td>{story.position}</td>
      <td>{story.title}</td>
      <td>
        <span className="badge">{story.type}</span>
      </td>
      <td>{story.vmix_input ?? "—"}</td>
      <td>{story.planned_duration}s</td>
      <td>{story.status}</td>
    </tr>
  );
}

export default function App() {
  const [rundowns, setRundowns] = useState<Rundown[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  const [snap, setSnap] = useState<RundownSnapshot | null>(null);
  const [vmix, setVmix] = useState<Record<string, unknown> | null>(null);
  const [title, setTitle] = useState("");
  const [showDate, setShowDate] = useState(() => new Date().toISOString().slice(0, 10));

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadRundowns = useCallback(() => {
    api("/api/rundowns")
      .then((r) => r.json())
      .then(setRundowns);
  }, []);

  const loadStories = useCallback((rid: string) => {
    api(`/api/rundowns/${rid}/stories`)
      .then((r) => r.json())
      .then((rows: Story[]) => setStories([...rows].sort((a, b) => a.position - b.position)));
  }, []);

  useEffect(() => {
    loadRundowns();
  }, [loadRundowns]);

  useEffect(() => {
    if (!activeId) return;
    loadStories(activeId);
  }, [activeId, loadStories]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl("rundown-ui"));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);
      if (msg.type === "bootstrap") {
        setSnap(msg.rundown as RundownSnapshot);
        setVmix(msg.vmix as Record<string, unknown>);
      }
      if (msg.type === "rundown") {
        setSnap(msg.payload as RundownSnapshot);
      }
      if (msg.type === "vmix") {
        setVmix((prev) => ({ ...(prev || {}), tally: msg.payload }));
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!snap?.stories?.length || !activeId) return;
    setStories((prev) => {
      const byId = new Map(snap.stories.map((s) => [s.id, s] as const));
      if (!prev.length) return snap.stories;
      return prev.map((p) => {
        const u = byId.get(p.id);
        if (!u) return p;
        return {
          ...p,
          status: u.status,
          title: u.title,
          type: u.type,
          planned_duration: u.planned_duration,
          vmix_input: u.vmix_input,
          script_body: p.script_body ?? u.script_body,
        };
      });
    });
  }, [snap, activeId]);

  useEffect(() => {
    if (!selectedStoryId) return;
    api(`/api/stories/${selectedStoryId}/script`)
      .then((r) => r.json())
      .then((d: { body: string }) =>
        setStories((prev) =>
          prev.map((s) => (s.id === selectedStoryId ? { ...s, script_body: d.body } : s)),
        ),
      );
  }, [selectedStoryId]);

  const selectedStory = useMemo(
    () => stories.find((s) => s.id === selectedStoryId) || null,
    [stories, selectedStoryId],
  );

  const onDragEnd = async (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = stories.findIndex((s) => s.id === active.id);
    const newIndex = stories.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(stories, oldIndex, newIndex).map((s, i) => ({ ...s, position: i + 1 }));
    setStories(next);
    await Promise.all(
      next.map((s) =>
        api(`/api/stories/${s.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ position: s.position }),
        }),
      ),
    );
  };

  const openCreate = async () => {
    await api("/api/rundowns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "New show", show_date: showDate }),
    });
    setTitle("");
    loadRundowns();
  };

  const activate = async () => {
    if (!activeId) return;
    await api(`/api/rundowns/${activeId}/activate`, { method: "POST" });
  };

  const saveStoryPanel = async () => {
    if (!selectedStory) return;
    await api(`/api/stories/${selectedStory.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: selectedStory.title,
        type: selectedStory.type,
        planned_duration: selectedStory.planned_duration,
        vmix_input: selectedStory.vmix_input,
      }),
    });
    await api(`/api/stories/${selectedStory.id}/script`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: selectedStory.script_body || "" }),
    });
    if (activeId) loadStories(activeId);
  };

  const tally = (vmix as { tally?: { program_input?: number; preview_input?: number } } | null)
    ?.tally;

  return (
    <>
      <header className="topbar">
        <div>
          <strong>Duopus</strong> Rundown
        </div>
        {snap?.active_rundown && (
          <span>
            Active: <strong>{snap.active_rundown.title}</strong>
          </span>
        )}
        {snap?.live_story && (
          <span>
            On air: <strong>{snap.live_story.title}</strong> · {snap.elapsed_seconds}s
          </span>
        )}
        <span style={{ marginLeft: "auto", fontSize: "0.85rem" }}>
          vMix tally: PGM {tally?.program_input ?? "—"} / PVW {tally?.preview_input ?? "—"}
        </span>
      </header>
      {!activeId ? (
        <div className="panel">
          <h2>Shows</h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <input type="date" value={showDate} onChange={(e) => setShowDate(e.target.value)} />
            <button className="primary" type="button" onClick={openCreate}>
              Create
            </button>
          </div>
          <ul>
            {rundowns.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => setActiveId(r.id)}>
                  {r.title}
                </button>{" "}
                <span className="badge">{r.status}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="layout">
          <div className="panel">
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button type="button" onClick={() => setActiveId(null)}>
                ← Shows
              </button>
              <button className="primary" type="button" onClick={activate}>
                Set active rundown
              </button>
            </div>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
              <SortableContext items={stories.map((s) => s.id)} strategy={verticalListSortingStrategy}>
                <table>
                  <thead>
                    <tr>
                      <th />
                      <th>#</th>
                      <th>Title</th>
                      <th>Type</th>
                      <th>vMix</th>
                      <th>Plan</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stories.map((s) => (
                      <SortableRow
                        key={s.id}
                        story={s}
                        selected={selectedStoryId === s.id}
                        onSelect={() => setSelectedStoryId(s.id)}
                      />
                    ))}
                  </tbody>
                </table>
              </SortableContext>
            </DndContext>
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                onClick={async () => {
                  await api(`/api/rundowns/${activeId}/stories`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title: "New story" }),
                  });
                  loadStories(activeId);
                }}
              >
                Add story
              </button>
            </div>
          </div>
          <aside className="panel side">
            {selectedStory ? (
              <>
                <h3>Edit story</h3>
                <label>Title</label>
                <input
                  value={selectedStory.title}
                  onChange={(e) =>
                    setStories((prev) =>
                      prev.map((x) => (x.id === selectedStory.id ? { ...x, title: e.target.value } : x)),
                    )
                  }
                />
                <label>Type</label>
                <select
                  value={selectedStory.type}
                  onChange={(e) =>
                    setStories((prev) =>
                      prev.map((x) => (x.id === selectedStory.id ? { ...x, type: e.target.value } : x)),
                    )
                  }
                >
                  {["package", "live", "break", "intro"].map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <label>Planned duration (s)</label>
                <input
                  type="number"
                  value={selectedStory.planned_duration}
                  onChange={(e) =>
                    setStories((prev) =>
                      prev.map((x) =>
                        x.id === selectedStory.id ? { ...x, planned_duration: Number(e.target.value) } : x,
                      ),
                    )
                  }
                />
                <label>vMix input</label>
                <input
                  type="number"
                  value={selectedStory.vmix_input ?? ""}
                  onChange={(e) =>
                    setStories((prev) =>
                      prev.map((x) =>
                        x.id === selectedStory.id
                          ? { ...x, vmix_input: e.target.value === "" ? null : Number(e.target.value) }
                          : x,
                      ),
                    )
                  }
                />
                <label>Script</label>
                <textarea
                  value={selectedStory.script_body || ""}
                  onChange={(e) =>
                    setStories((prev) =>
                      prev.map((x) =>
                        x.id === selectedStory.id ? { ...x, script_body: e.target.value } : x,
                      ),
                    )
                  }
                />
                <button className="primary" type="button" onClick={saveStoryPanel} style={{ marginTop: 8 }}>
                  Save
                </button>
              </>
            ) : (
              <p>Select a story row.</p>
            )}
          </aside>
        </div>
      )}
    </>
  );
}

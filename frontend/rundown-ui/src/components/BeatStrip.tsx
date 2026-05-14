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
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMemo } from "react";
import type { Beat, BeatCategory } from "../types";

const CAT_STYLES: Record<BeatCategory, { bg: string; text: string; ring: string }> = {
  VO: { bg: "bg-blue-50", text: "text-blue-800", ring: "ring-blue-200" },
  ILU: { bg: "bg-amber-50", text: "text-amber-800", ring: "ring-amber-200" },
  SYN: { bg: "bg-emerald-50", text: "text-emerald-800", ring: "ring-emerald-200" },
};

function fmtMmSs(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

function BeatChip({
  beat,
  onClick,
}: {
  beat: Beat;
  onClick: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: beat.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const st = CAT_STYLES[beat.category];
  return (
    <button
      ref={setNodeRef}
      type="button"
      style={style}
      className={[
        "inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ring-1",
        st.bg,
        st.text,
        st.ring,
        isDragging ? "opacity-70" : "",
      ].join(" ")}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      <span>{beat.category}</span>
      <span className="text-slate-500">·</span>
      <span>{fmtMmSs(beat.duration || 0)}</span>
    </button>
  );
}

export function BeatStrip({
  beats,
  onChange,
  onEditBeat,
}: {
  beats: Beat[];
  onChange: (beats: Beat[]) => void;
  onEditBeat: (id: string) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const total = useMemo(() => beats.reduce((a, b) => a + (b.duration || 0), 0), [beats]);

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = beats.findIndex((b) => b.id === active.id);
    const newIndex = beats.findIndex((b) => b.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    onChange(arrayMove(beats, oldIndex, newIndex));
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={beats.map((b) => b.id)} strategy={horizontalListSortingStrategy}>
          {beats.map((b) => (
            <BeatChip key={b.id} beat={b} onClick={() => onEditBeat(b.id)} />
          ))}
        </SortableContext>
      </DndContext>
      <span className="text-xs text-slate-600">→ total {fmtMmSs(total)}</span>
    </div>
  );
}


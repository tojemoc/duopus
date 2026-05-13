export type Rundown = {
  id: string;
  title: string;
  show_date: string;
  status: string;
  template_id: number | null;
};

export type Story = {
  id: number;
  position: number;
  label: string;
  segment: string;
  planned_duration: number;
  status: string;
  ready: boolean;
  beats: Beat[];
  planned_duration_override: number | null;
  title_in: number;
  title_duration: number;
  locked_by: number | null;
  locked_at: string | null;
};

export type BeatCategory = "VO" | "ILU" | "SYN";

export type Beat = {
  id: string;
  category: BeatCategory;
  duration: number;
  note: string;
};

export type Script = {
  story_id: number;
  body: string;
  updated_at: string;
  updated_by: number | null;
};

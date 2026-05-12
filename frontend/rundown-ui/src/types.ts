export type Rundown = {
  id: string;
  title: string;
  show_date: string;
  status: string;
  created_at?: string;
};

export type Story = {
  id: string;
  position: number;
  title: string;
  type: string;
  planned_duration: number;
  actual_duration: number | null;
  vmix_input: number | null;
  status: string;
  script_body?: string;
};

export type RundownSnapshot = {
  active_rundown: { id: string; title: string; show_date: string; status: string } | null;
  stories: Story[];
  live_story: Story | null;
  elapsed_seconds: number;
};

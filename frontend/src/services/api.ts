/**
 * API client. All backend access goes through here so components never build
 * URLs themselves.
 *
 * By default we call the backend directly at http://localhost:8000 (the backend
 * enables CORS for any localhost port), so it works whether you run the Vite dev
 * server, `vite preview`, or any static server — no proxy required.
 *
 * Override with VITE_API_BASE when needed:
 *   - Docker / nginx:           VITE_API_BASE=/api
 *   - backend on another host:  VITE_API_BASE=http://my-host:8000
 */
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface MeetingSummary {
  meeting_id: string;
  title: string;
  date: string;
  duration: number | null;
  project_id: number | null;
}

export interface ProjectSummary {
  project_id: number;
  meetings: number;
  titles: string[];
}

export interface Entity {
  name: string;
  type: "person" | "task" | "date";
}

export interface GraphEdge {
  source: string;
  relation: string;
  target: string;
}

export interface Chunk {
  chunk_index: number;
  speaker: string | null;
  content: string;
}

export interface ActionItem {
  id: number;
  owner: string | null;
  task: string;
  due: string | null;
  status: string;
}

export interface MeetingDetail extends MeetingSummary {
  raw_transcript: string;
  chunks: Chunk[];
  entities: Entity[];
  edges: GraphEdge[];
  action_items: ActionItem[];
}

export interface IngestionResult {
  meeting_id: string;
  chunks: number;
  entities: number;
  edges: number;
  action_items: number;
}

export interface GraphFact {
  source: string;
  relation: string;
  target: string;
  meeting_id: string | null;
}

export interface VectorHit {
  content: string;
  speaker: string | null;
  meeting_id: string | null;
  score: number;
}

export interface EmailSummary {
  id: string;
  sender: string;
  subject: string;
  received: string;
  preview: string;
}

export interface ChatResponse {
  answer: string;
  provider: string;
  action: "rag" | "mail_fetch" | "mail_send" | "mail_help";
  emails: EmailSummary[] | null;
  context: { query: string; graph_facts: GraphFact[]; vector_hits: VectorHit[] };
}

export interface DashboardStats {
  meetings: number;
  chunks: number;
  graph_edges: number;
  open_action_items: number;
  hermes_provider: string;
  vector_backend: string;
}

export interface Insight {
  text: string;
  evidence: string | null;
  source: string | null;
}

export interface ProjectReport {
  title: string;
  scope_type: "weekly" | "meeting";
  scope_label: string;
  generated_at: string;
  period_start: string | null;
  period_end: string | null;
  meetings: { meeting_id: string; title: string; date: string }[];
  stats: {
    meetings: number;
    people: number;
    tasks: number;
    graph_edges: number;
    open_action_items: number;
    done_action_items: number;
  };
  responsibilities: { owner: string; tasks: string[] }[];
  merits: Insight[];
  demerits: Insight[];
  action_items: ActionItem[];
  executive_summary: string;
  provider: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error(
      `Cannot reach the backend at ${BASE}. Is it running? ` +
        `Start it with: uvicorn app.main:app --reload (from the backend folder).`
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    if (res.status === 404) {
      throw new Error(
        `Endpoint not found (404) at ${BASE}${path}. ` +
          `Check the backend is running on the expected URL (VITE_API_BASE).`
      );
    }
    const rawDetail = detail?.detail ?? detail;
    const errorMsg = typeof rawDetail === "object" && rawDetail !== null
      ? (rawDetail.message || rawDetail.error || JSON.stringify(rawDetail))
      : (rawDetail ?? `Request failed (${res.status})`);
    throw new Error(errorMsg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => request<DashboardStats>("/dashboard/stats"),
  listMeetings: () => request<MeetingSummary[]>("/meetings"),
  listProjects: () => request<ProjectSummary[]>("/meetings/projects"),
  getMeeting: (id: string) => request<MeetingDetail>(`/meetings/${id}`),
  actionItems: (id: string) =>
    request<ActionItem[]>(`/meetings/${id}/action-items`),
  uploadMeeting: (body: {
    meeting_id: string;
    title: string;
    transcript: string;
    duration?: number | null;
    project_id?: number | null;
  }) =>
    request<IngestionResult>("/meetings/upload", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  editMeeting: (
    id: string,
    body: {
      title?: string;
      duration?: number | null;
      transcript?: string;
      append_transcript?: string;
    }
  ) =>
    request<IngestionResult>(`/meetings/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteMeeting: (id: string) =>
    fetch(`${BASE}/meetings/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok && r.status !== 204) throw new Error("Delete failed");
    }),
  chat: (body: {
    query: string;
    meeting_id?: string | null;
    project_id?: number | null;
    top_k?: number;
  }) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // --- reports ---
  meetingReportPreview: (id: string) =>
    request<ProjectReport>(`/reports/meeting/${id}/preview`),
  projectReportPreview: (pid: number) =>
    request<ProjectReport>(`/reports/project/${pid}/preview`),
  projectReportPdfUrl: (pid: number) => `${BASE}/reports/project/${pid}`,
  emailReport: (body: {
    scope: string;
    meeting_id?: string | null;
    project_id?: number | null;
    date?: string | null;
    to: string;
    subject?: string;
    message?: string;
    via?: string;
    email_provider?: string;
    gstack?: boolean;
  }) =>
    request<{ ok: boolean; output: string; file?: string; to?: string; via?: string }>(
      "/reports/email",
      { method: "POST", body: JSON.stringify(body) }
    ),
  sendMeetingEmail: (
    meetingId: string,
    body: { to: string; provider?: string; subject?: string; message?: string }
  ) =>
    request<{ action?: string; data?: unknown }>(
      `/comms/send-meeting/${meetingId}`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  weeklyReportPreview: (date?: string) =>
    request<ProjectReport>(
      `/reports/weekly/preview${date ? `?date=${date}` : ""}`
    ),
  // Direct download URLs (used as <a href> so the browser saves the PDF).
  meetingReportPdfUrl: (id: string) => `${BASE}/reports/meeting/${id}`,
  weeklyReportPdfUrl: (date?: string) =>
    `${BASE}/reports/weekly${date ? `?date=${date}` : ""}`,

  // --- contact / composio ---
  commsStatus: () =>
    request<{
      enabled: boolean;
      entity_id: string;
      connections: { id: string; app: string; status: string }[];
      error: string | null;
    }>("/comms/status"),
  commsEmails: (provider: string, limit = 10) =>
    request<{ action: string; data: unknown; raw: unknown }>(
      `/comms/emails?provider=${provider}&limit=${limit}`
    ),
  commsEvents: (provider: string, limit = 10) =>
    request<{ action: string; data: unknown; raw: unknown }>(
      `/comms/events?provider=${provider}&limit=${limit}`
    ),
  commsSend: (body: {
    provider: string;
    to: string;
    subject: string;
    body: string;
  }) =>
    request<{ action: string; data: unknown; raw: unknown }>("/comms/send", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // --- hermes agent control (read-only CLI) ---
  agentStatus: () =>
    request<{ available: boolean; cli_path: string; actions: string[] }>(
      "/agent/status"
    ),
  agentRun: (action: string) =>
    request<{
      action: string;
      command: string;
      exit_code: number;
      output: string;
      ok: boolean;
    }>(`/agent/run/${action}`),
  agentChat: (message: string) =>
    request<{
      action: string;
      command: string;
      exit_code: number;
      output: string;
      ok: boolean;
    }>("/agent/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  agentSaveMeeting: (meetingId: string) =>
    request<{
      action: string;
      command: string;
      exit_code: number;
      output: string;
      ok: boolean;
      note?: string;
    }>(`/agent/save-meeting/${meetingId}`, { method: "POST" }),
  agentSkills: () =>
    request<{
      curated: {
        id: string;
        label: string;
        category: string;
        produces_file: boolean;
        ext: string | null;
        description: string;
        mandatory: boolean;
      }[];
      installed: { name: string; category: string; status: string }[];
    }>("/agent/skills"),
  agentRunSkill: (skillId: string, meetingId: string) =>
    request<{
      ok: boolean;
      output: string;
      skill: string;
      command: string;
      produced_file?: string | null;
    }>("/agent/skills/run", {
      method: "POST",
      body: JSON.stringify({ skill_id: skillId, meeting_id: meetingId }),
    }),

  // --- auto-send settings ---
  getAutoSendSettings: () =>
    request<{
      enabled: boolean;
      target_email: string;
      email_provider: string;
    }>("/reports/settings"),
  setAutoSendSettings: (body: {
    enabled: boolean;
    target_email: string;
    email_provider: string;
  }) =>
    request<{
      enabled: boolean;
      target_email: string;
      email_provider: string;
    }>("/reports/settings", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // --- autoplan review ---
  agentAutoplan: (meetingId: string) =>
    request<{
      ok: boolean;
      output: string;
      reviews?: Record<string, string>;
    }>("/agent/autoplan", {
      method: "POST",
      body: JSON.stringify({ meeting_id: meetingId }),
    }),
  runSkill: (body: { skill_name: string; meeting_id: string }) =>
    request<{ ok: boolean; markdown: string; pdf_url: string }>("/reports/run-skill", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  skillReportPdfUrl: (skillName: string, meetingId: string) =>
    `${BASE}/reports/skills/download?skill_name=${skillName}&meeting_id=${meetingId}`,
  meetingReportGStackPdfUrl: (id: string) => `${BASE}/reports/meeting/${id}/gstack`,
  projectReportGStackPdfUrl: (pid: number) => `${BASE}/reports/project/${pid}/gstack`,
  weeklyReportGStackPdfUrl: (date?: string) => `${BASE}/reports/weekly/gstack${date ? `?date=${date}` : ""}`,

  // --- auto-ingest settings ---
  getAutoIngestSettings: () =>
    request<{ enabled: boolean }>("/meetings/auto-ingest"),
  setAutoIngestSettings: (body: { enabled: boolean }) =>
    request<{ enabled: boolean }>("/meetings/auto-ingest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

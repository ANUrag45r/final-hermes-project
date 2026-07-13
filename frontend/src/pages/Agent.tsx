import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Cpu,
  MessagesSquare,
  Send,
  Sparkles,
  Terminal,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, MeetingSummary } from "@/services/api";

type Status = Awaited<ReturnType<typeof api.agentStatus>>;
type RunResult = Awaited<ReturnType<typeof api.agentRun>>;
type View = "chat" | "skills" | "control";

const ACTION_LABELS: Record<string, string> = {
  status: "Status",
  sessions: "Sessions",
  profiles: "Profiles",
  insights: "Token usage",
  logs: "Logs",
  mcp: "MCP servers",
};

export function Agent() {
  const [status, setStatus] = useState<Status | null>(null);
  const [view, setView] = useState<View>("chat");
  const [active, setActive] = useState<string>("status");
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.agentStatus().then(setStatus).catch(() => void 0);
  }, []);

  async function run(action: string) {
    setActive(action);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.agentRun(action));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Command failed");
    } finally {
      setLoading(false);
    }
  }

  const actions = status?.actions ?? ["status", "sessions", "profiles", "insights", "logs", "mcp"];

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Hermes Agent" />
      <div className="flex min-h-0 flex-1 flex-col px-8 py-6">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
              status?.available
                ? "border-recall/40 bg-recall-soft text-ink"
                : "border-slate-line text-ink/45"
            }`}
          >
            {status?.available ? (
              <Wifi className="h-3.5 w-3.5" />
            ) : (
              <WifiOff className="h-3.5 w-3.5" />
            )}
            {status?.available ? "Hermes CLI detected" : "Hermes CLI not found"}
          </span>
          {status && (
            <span className="font-mono text-xs text-ink/45">
              <Cpu className="mr-1 inline h-3.5 w-3.5" />
              {status.cli_path}
            </span>
          )}
          <div className="ml-auto flex gap-1 rounded-lg border border-slate-line p-1">
            <button
              onClick={() => setView("chat")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === "chat" ? "bg-ink text-paper" : "text-ink/60 hover:bg-ink/5"
              }`}
            >
              <MessagesSquare className="h-4 w-4" /> Chat
            </button>
            <button
              onClick={() => setView("skills")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === "skills" ? "bg-ink text-paper" : "text-ink/60 hover:bg-ink/5"
              }`}
            >
              <Sparkles className="h-4 w-4" /> Skills
            </button>
            <button
              onClick={() => setView("control")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === "control" ? "bg-ink text-paper" : "text-ink/60 hover:bg-ink/5"
              }`}
            >
              <Terminal className="h-4 w-4" /> Control
            </button>
          </div>
        </div>

        {view === "chat" ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <p className="mb-3 text-sm text-ink/55">
              Type a message — it runs through your Hermes CLI
              (<code className="rounded bg-ink/5 px-1">hermes chat -q …</code>) and
              the agent's output comes straight back.
            </p>
            <CliChat available={status?.available !== false} />
          </div>
        ) : view === "skills" ? (
          <SkillsView />
        ) : (
          <ControlView
            status={status}
            actions={actions}
            active={active}
            result={result}
            loading={loading}
            error={error}
            onRun={run}
          />
        )}
      </div>
    </div>
  );
}

function ControlView({
  status,
  actions,
  active,
  result,
  loading,
  error,
  onRun,
}: {
  status: Status | null;
  actions: string[];
  active: string;
  result: RunResult | null;
  loading: boolean;
  error: string | null;
  onRun: (a: string) => void;
}) {
  return (
    <div className="overflow-y-auto">
      {status && !status.available && (
        <Card className="mb-6 border-recall/40">
          <CardContent className="pt-5 text-sm text-ink/80">
            No <code className="rounded bg-ink/5 px-1">hermes</code> executable
            found. Set <code className="rounded bg-ink/5 px-1">HERMES_CLI_PATH</code>{" "}
            in <code className="rounded bg-ink/5 px-1">backend/.env</code> to your
            hermes binary and restart the backend.
          </CardContent>
        </Card>
      )}

      <div className="mb-5 flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button
            key={a}
            variant={active === a ? "primary" : "ghost"}
            size="sm"
            onClick={() => onRun(a)}
            disabled={loading}
          >
            {ACTION_LABELS[a] ?? a}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-synapse" />
            {result ? result.command : "Run a command"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm text-ink/55">Running…</p>}
          {error && <p className="text-sm text-recall">{error}</p>}
          {!loading && !error && !result && (
            <p className="text-sm text-ink/45">
              Pick a command above to query your local Hermes agent.
            </p>
          )}
          {result && (
            <>
              {!result.ok && (
                <p className="mb-2 text-xs text-recall">
                  exit code {result.exit_code}
                </p>
              )}
              <pre className="max-h-[28rem] overflow-auto rounded-lg bg-ink/5 p-3 font-mono text-xs leading-relaxed text-ink/85">
                {result.output}
              </pre>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

type Turn = { you: string; agent?: string; ok?: boolean; pending?: boolean };

function CliChat({ available }: { available: boolean }) {
  const [turns, setTurns] = useState<Turn[]>(() => {
    try {
      const saved = localStorage.getItem("hermes-chat-history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem("hermes-chat-history", JSON.stringify(turns));
    } catch (e) {
      console.error("Failed to save chat history", e);
    }
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  function clearChat() {
    setTurns([]);
    try {
      localStorage.removeItem("hermes-chat-history");
    } catch (e) {
      console.error("Failed to clear chat history", e);
    }
  }

  async function send() {
    const msg = input.trim();
    if (!msg || busy) return;
    setInput("");
    setBusy(true);
    const idx = turns.length;
    setTurns((t) => [...t, { you: msg, pending: true }]);
    try {
      const res = await api.agentChat(msg);
      setTurns((t) =>
        t.map((turn, i) =>
          i === idx ? { ...turn, agent: res.output, ok: res.ok, pending: false } : turn
        )
      );
    } catch (e) {
      setTurns((t) =>
        t.map((turn, i) =>
          i === idx
            ? {
                ...turn,
                agent: e instanceof Error ? e.message : "Request failed",
                ok: false,
                pending: false,
              }
            : turn
        )
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-slate-line bg-surface">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {turns.length === 0 && (
          <p className="text-sm text-ink/45">
            Try “give my last 3 mails”, “what’s on my calendar tomorrow”, or any
            question for your agent.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-ink px-3 py-2 text-sm text-paper">
                {t.you}
              </div>
            </div>
            <div className="flex justify-start">
              <div className="max-w-[90%] rounded-2xl rounded-bl-sm border border-slate-line bg-paper px-3 py-2">
                {t.pending ? (
                  <span className="text-sm text-ink/45">Hermes is thinking…</span>
                ) : (
                  <>
                    {t.ok === false && (
                      <span className="mb-1 block text-xs text-recall">error</span>
                    )}
                    <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-ink/85">
                      {t.agent}
                    </pre>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="flex items-center gap-2 border-t border-slate-line p-3">
        {turns.length > 0 && (
          <Button variant="outline" onClick={clearChat} disabled={busy} className="h-10">
            Clear Chat
          </Button>
        )}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={available ? "Message your Hermes agent…" : "Hermes CLI not found"}
          disabled={busy || !available}
          className="h-10 flex-1 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall disabled:opacity-50"
        />
        <Button variant="recall" onClick={send} disabled={busy || !available || !input.trim()}>
          <Send className="h-4 w-4" />
          {busy ? "…" : "Send"}
        </Button>
      </div>
    </div>
  );
}

type SkillsData = Awaited<ReturnType<typeof api.agentSkills>>;

function SkillsView() {
  const [data, setData] = useState<SkillsData | null>(null);
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [meetingId, setMeetingId] = useState<string>("");
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<{ skill: string; output: string; ok: boolean; file?: string | null } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.agentSkills().then(setData).catch(() => void 0);
    api.listMeetings().then((m) => {
      setMeetings(m);
      if (m.length) setMeetingId(m[0].meeting_id);
    }).catch(() => void 0);
  }, []);

  async function run(skillId: string) {
    if (!meetingId) {
      setErr("Add or select a meeting first.");
      return;
    }
    setRunning(skillId);
    setErr(null);
    setResult(null);
    try {
      const res = await api.agentRunSkill(skillId, meetingId);
      setResult({ skill: res.skill, output: res.output, ok: res.ok, file: res.produced_file });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Skill run failed");
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="overflow-y-auto pb-8">
      <p className="mb-4 text-sm text-ink/55">
        Run a gstack skill (via Hermes) on a meeting. The app builds the meeting
        content and Hermes invokes the chosen skill — PDF generation is the
        primary one.
      </p>

      <div className="mb-5 flex items-center gap-2">
        <label className="text-sm text-ink/60">Meeting:</label>
        <select
          value={meetingId}
          onChange={(e) => setMeetingId(e.target.value)}
          className="h-9 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
        >
          {meetings.length === 0 && <option value="">No meetings yet</option>}
          {meetings.map((m) => (
            <option key={m.meeting_id} value={m.meeting_id}>
              {m.meeting_id} — {m.title}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {(data?.curated ?? []).map((s) => (
          <Card key={s.id} className={s.mandatory ? "border-recall/40" : ""}>
            <CardContent className="pt-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-display text-base font-medium text-ink">
                      {s.label}
                    </span>
                    {s.mandatory && (
                      <span className="rounded-full bg-recall-soft px-2 py-0.5 text-[10px] font-medium text-ink">
                        primary
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-ink/55">{s.description}</p>
                  <span className="mt-1 inline-block font-mono text-[10px] text-synapse">
                    skill: {s.id}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant={s.mandatory ? "recall" : "primary"}
                  onClick={() => run(s.id)}
                  disabled={running !== null || !meetingId}
                >
                  {running === s.id ? "Running…" : "Run"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {err && <p className="mt-4 text-sm text-recall">{err}</p>}

      {result && (
        <Card className="mt-5">
          <CardHeader>
            <CardTitle className="text-sm">
              {result.ok ? "Result" : "Result (with errors)"} — {result.skill}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {result.file && (
              <p className="mb-2 text-xs text-ink/70">
                Saved file: <span className="font-mono">{result.file}</span>
              </p>
            )}
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-ink/5 p-3 font-mono text-xs leading-relaxed text-ink/85">
              {result.output}
            </pre>
          </CardContent>
        </Card>
      )}

      <h3 className="mb-2 mt-8 font-display text-sm font-medium text-ink/70">
        All installed gstack skills{" "}
        {data?.installed?.length ? `(${data.installed.length})` : ""}
      </h3>
      {data?.installed?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {data.installed.map((s) => (
            <span
              key={s.name}
              title={s.category}
              className="rounded-md border border-slate-line px-2 py-1 font-mono text-[11px] text-ink/65"
            >
              {s.name}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-ink/45">
          Could not read the skill catalogue (is the Hermes CLI on PATH?). The
          curated skills above still work.
        </p>
      )}
    </div>
  );
}

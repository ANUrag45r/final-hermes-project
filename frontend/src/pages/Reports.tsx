import * as React from "react";
import { useEffect, useState } from "react";
import { Clock, Download, FileText, Mail, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, MeetingSummary, ProjectReport, ProjectSummary } from "@/services/api";

type Scope = "weekly" | "meeting" | "project";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

export function Reports() {
  const [scope, setScope] = useState<Scope>("weekly");
  const [date, setDate] = useState(isoToday());
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [meetingId, setMeetingId] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [report, setReport] = useState<ProjectReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoSend, setAutoSend] = useState({
    enabled: false,
    target_email: "",
    email_provider: "gmail",
  });
  const [autoSendResult, setAutoSendResult] = useState<string | null>(null);

  const [useGStackPdf, setUseGStackPdf] = useState<boolean>(() => {
    return localStorage.getItem("governance_brain_use_gstack_pdf") === "true";
  });

  const [scheduleEnabled, setScheduleEnabled] = useState<boolean>(() => {
    return localStorage.getItem("governance_brain_schedule_enabled") === "true";
  });

  const [scheduleIntervalDays, setScheduleIntervalDays] = useState<number>(() => {
    return Number(localStorage.getItem("governance_brain_schedule_interval_days") || "1");
  });

  const [scheduleIntervalHours, setScheduleIntervalHours] = useState<number>(() => {
    return Number(localStorage.getItem("governance_brain_schedule_interval_hours") || "0");
  });

  const [scheduleIntervalMinutes, setScheduleIntervalMinutes] = useState<number>(() => {
    return Number(localStorage.getItem("governance_brain_schedule_interval_minutes") || "0");
  });

  const [scheduleEmails, setScheduleEmails] = useState<string>(() => {
    return localStorage.getItem("governance_brain_schedule_emails") || "";
  });

  const [scheduleVia, setScheduleVia] = useState<"composio" | "hermes">((() => {
    return (localStorage.getItem("governance_brain_schedule_via") || "composio") as "composio" | "hermes";
  }));

  const [scheduleEmailProvider, setScheduleEmailProvider] = useState<"gmail" | "outlook">((() => {
    return (localStorage.getItem("governance_brain_schedule_email_provider") || "gmail") as "gmail" | "outlook";
  }));

  const [nextRunTimestamp, setNextRunTimestamp] = useState<number | null>(() => {
    const val = localStorage.getItem("governance_brain_schedule_next_run");
    return val ? Number(val) : null;
  });

  const [timeLeftMs, setTimeLeftMs] = useState<number>(0);
  const [scheduleStatusMsg, setScheduleStatusMsg] = useState<string | null>(null);

  function formatTimeLeft(ms: number) {
    if (ms <= 0) return "0s";
    const seconds = Math.floor((ms / 1000) % 60);
    const minutes = Math.floor((ms / (1000 * 60)) % 60);
    const hours = Math.floor((ms / (1000 * 60 * 60)) % 24);
    const days = Math.floor(ms / (1000 * 60 * 60 * 24));

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0 || days > 0) parts.push(`${hours}h`);
    if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
    parts.push(`${seconds}s`);

    return parts.join(" ");
  }

  async function triggerScheduledReport() {
    if (!scheduleEmails.trim()) {
      setScheduleStatusMsg("Scheduled run skipped: No target emails specified.");
      return;
    }
    const emails = scheduleEmails
      .split(",")
      .map((e) => e.trim())
      .filter((e) => e.length > 0);

    if (emails.length === 0) {
      setScheduleStatusMsg("Scheduled run skipped: No target emails specified.");
      return;
    }

    setScheduleStatusMsg(`Scheduled run triggered at ${new Date().toLocaleTimeString()}...`);

    try {
      const currentMeetings = await api.listMeetings();
      if (currentMeetings.length === 0) {
        setScheduleStatusMsg("Scheduled run skipped: No meetings found.");
        return;
      }
      
      const sorted = [...currentMeetings].sort((a, b) => b.date.localeCompare(a.date));
      const lastMeeting = sorted[0];

      const sentSuccessful: string[] = [];
      const sentFailed: string[] = [];

      for (const email of emails) {
        try {
          const res = await api.emailReport({
            scope: "meeting",
            meeting_id: lastMeeting.meeting_id,
            to: email,
            subject: `Scheduled Report: Last Meeting (${lastMeeting.title})`,
            message: `Please find attached the scheduled management report for the last meeting: ${lastMeeting.title} held on ${lastMeeting.date}.`,
            via: scheduleVia,
            email_provider: scheduleEmailProvider,
            gstack: useGStackPdf,
          });
          if (res.ok) {
            sentSuccessful.push(email);
          } else {
            sentFailed.push(`${email} (${res.output})`);
          }
        } catch (err) {
          console.error(`Failed to send scheduled report to ${email}:`, err);
          sentFailed.push(`${email} (${err instanceof Error ? err.message : String(err)})`);
        }
      }

      if (sentFailed.length === 0) {
        setScheduleStatusMsg(`Scheduled run finished. Sent report for last meeting "${lastMeeting.title}" to: ${sentSuccessful.join(", ")}`);
      } else {
        setScheduleStatusMsg(`Scheduled run finished with errors. Success: ${sentSuccessful.join(", ") || "None"}. Failures: ${sentFailed.join("; ")}`);
      }
    } catch (fetchErr) {
      console.error("Failed to list meetings for scheduled report:", fetchErr);
      setScheduleStatusMsg(`Scheduled run failed: Could not fetch meetings list.`);
    }
  }

  useEffect(() => {
    if (!scheduleEnabled || !nextRunTimestamp) {
      setTimeLeftMs(0);
      return;
    }

    const intervalId = setInterval(() => {
      const diff = nextRunTimestamp - Date.now();
      if (diff <= 0) {
        triggerScheduledReport();
        const intervalMs = Math.max(60000, (scheduleIntervalDays * 24 * 60 * 60 + scheduleIntervalHours * 60 * 60 + scheduleIntervalMinutes * 60) * 1000);
        const nextTarget = Date.now() + intervalMs;
        setNextRunTimestamp(nextTarget);
        localStorage.setItem("governance_brain_schedule_next_run", String(nextTarget));
        setTimeLeftMs(nextTarget - Date.now());
      } else {
        setTimeLeftMs(diff);
      }
    }, 1000);

    const diff = nextRunTimestamp - Date.now();
    if (diff <= 0) {
      triggerScheduledReport();
      const intervalMs = Math.max(60000, (scheduleIntervalDays * 24 * 60 * 60 + scheduleIntervalHours * 60 * 60 + scheduleIntervalMinutes * 60) * 1000);
      const nextTarget = Date.now() + intervalMs;
      setNextRunTimestamp(nextTarget);
      localStorage.setItem("governance_brain_schedule_next_run", String(nextTarget));
      setTimeLeftMs(nextTarget - Date.now());
    } else {
      setTimeLeftMs(diff);
    }

    return () => clearInterval(intervalId);
  }, [
    scheduleEnabled,
    nextRunTimestamp,
    scheduleIntervalDays,
    scheduleIntervalHours,
    scheduleIntervalMinutes,
    useGStackPdf,
    scheduleEmails,
    scheduleVia,
    scheduleEmailProvider,
  ]);

  useEffect(() => {
    api.listMeetings().then((m) => {
      setMeetings(m);
      if (m[0]) setMeetingId(m[0].meeting_id);
    });
    api.listProjects().then((p) => {
      setProjects(p);
      if (p[0]) setProjectId(p[0].project_id);
    });
    api.getAutoSendSettings().then(setAutoSend).catch(() => void 0);
  }, []);

  async function updateAutoSend(updated: Partial<typeof autoSend>) {
    const next = { ...autoSend, ...updated };
    setAutoSend(next);
    try {
      await api.setAutoSendSettings(next);
    } catch (e) {
      console.error("Failed to save auto-send settings:", e);
    }
  }

  async function preview() {
    setLoading(true);
    setError(null);
    setReport(null);
    setAutoSendResult(null);
    try {
      let r: ProjectReport;
      if (scope === "weekly") r = await api.weeklyReportPreview(date);
      else if (scope === "meeting") r = await api.meetingReportPreview(meetingId);
      else r = await api.projectReportPreview(projectId ?? 0);
      setReport(r);

      // Auto-send logic if enabled
      if (autoSend.enabled && autoSend.target_email.trim()) {
        setAutoSendResult("Auto-sending report PDF in background...");
        try {
          const res = await api.emailReport({
            scope,
            meeting_id: scope === "meeting" ? meetingId : undefined,
            project_id: scope === "project" ? projectId : undefined,
            date: scope === "weekly" ? date : undefined,
            to: autoSend.target_email.trim(),
            subject: `Auto-send: Management report for ${r.scope_label}`,
            message: `Please find attached the automatically sent management report for ${r.scope_label}.`,
            via: "composio",
            email_provider: autoSend.email_provider,
            gstack: useGStackPdf,
          });
          if (res.ok) {
            setAutoSendResult(`Successfully auto-sent to ${autoSend.target_email} via Composio.`);
          } else {
            setAutoSendResult(`Auto-send failed: ${res.output}`);
          }
        } catch (sendErr) {
          setAutoSendResult(`Auto-send failed: ${sendErr instanceof Error ? sendErr.message : String(sendErr)}`);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not build report");
    } finally {
      setLoading(false);
    }
  }

  const pdfUrl = useGStackPdf
    ? (scope === "weekly"
      ? api.weeklyReportGStackPdfUrl(date)
      : scope === "meeting"
      ? api.meetingReportGStackPdfUrl(meetingId)
      : api.projectReportGStackPdfUrl(projectId ?? 0))
    : (scope === "weekly"
      ? api.weeklyReportPdfUrl(date)
      : scope === "meeting"
      ? api.meetingReportPdfUrl(meetingId)
      : api.projectReportPdfUrl(projectId ?? 0));

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Reports" />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {/* Auto-Scheduling Dashboard */}
        <Card className="mb-6 border-synapse/30 bg-synapse/5 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-ink">
              <Clock className="h-5 w-5 text-synapse animate-pulse" /> Auto-Scheduling Dashboard
            </CardTitle>
            <p className="text-xs text-ink/70">
              Set up automatic generation and emailing of your management reports at a regular interval.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-6">
              {/* Toggle switch */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    const nextVal = !scheduleEnabled;
                    setScheduleEnabled(nextVal);
                    localStorage.setItem("governance_brain_schedule_enabled", String(nextVal));
                    if (nextVal) {
                      const intervalMs = Math.max(60000, (scheduleIntervalDays * 24 * 60 * 60 + scheduleIntervalHours * 60 * 60 + scheduleIntervalMinutes * 60) * 1000);
                      const target = Date.now() + intervalMs;
                      setNextRunTimestamp(target);
                      localStorage.setItem("governance_brain_schedule_next_run", String(target));
                    } else {
                      localStorage.removeItem("governance_brain_schedule_next_run");
                      setNextRunTimestamp(null);
                    }
                  }}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-synapse ${
                    scheduleEnabled ? "bg-synapse" : "bg-slate-line"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-paper shadow ring-0 transition duration-200 ease-in-out ${
                      scheduleEnabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
                <span className="text-sm font-medium text-ink">
                  {scheduleEnabled ? "Scheduling Active" : "Scheduling Inactive"}
                </span>
              </div>

              {/* Countdown / Status display */}
              {scheduleEnabled && nextRunTimestamp && (
                <div className="flex items-center gap-2 rounded-lg bg-surface border border-slate-line px-3 py-1.5 text-sm font-mono text-ink">
                  <span className="text-xs text-ink/60">Next run in:</span>
                  <span className="font-semibold text-synapse">{formatTimeLeft(timeLeftMs)}</span>
                </div>
              )}
            </div>

            {/* Inputs grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <label className="text-xs font-mono uppercase tracking-wider text-ink/60 block mb-1">
                  Interval
                </label>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="number"
                      min={0}
                      value={scheduleIntervalDays}
                      onChange={(e) => {
                        const val = Math.max(0, Number(e.target.value));
                        setScheduleIntervalDays(val);
                        localStorage.setItem("governance_brain_schedule_interval_days", String(val));
                        if (scheduleEnabled) {
                          const ms = Math.max(60000, (val * 24 * 60 * 60 + scheduleIntervalHours * 60 * 60 + scheduleIntervalMinutes * 60) * 1000);
                          const target = Date.now() + ms;
                          setNextRunTimestamp(target);
                          localStorage.setItem("governance_brain_schedule_next_run", String(target));
                        }
                      }}
                      disabled={!scheduleEnabled}
                      className="w-20 bg-surface"
                    />
                    <span className="text-xs text-ink/70">Days</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Input
                      type="number"
                      min={0}
                      max={23}
                      value={scheduleIntervalHours}
                      onChange={(e) => {
                        const val = Math.max(0, Math.min(23, Number(e.target.value)));
                        setScheduleIntervalHours(val);
                        localStorage.setItem("governance_brain_schedule_interval_hours", String(val));
                        if (scheduleEnabled) {
                          const ms = Math.max(60000, (scheduleIntervalDays * 24 * 60 * 60 + val * 60 * 60 + scheduleIntervalMinutes * 60) * 1000);
                          const target = Date.now() + ms;
                          setNextRunTimestamp(target);
                          localStorage.setItem("governance_brain_schedule_next_run", String(target));
                        }
                      }}
                      disabled={!scheduleEnabled}
                      className="w-20 bg-surface"
                    />
                    <span className="text-xs text-ink/70">hr</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Input
                      type="number"
                      min={0}
                      max={59}
                      value={scheduleIntervalMinutes}
                      onChange={(e) => {
                        const val = Math.max(0, Math.min(59, Number(e.target.value)));
                        setScheduleIntervalMinutes(val);
                        localStorage.setItem("governance_brain_schedule_interval_minutes", String(val));
                        if (scheduleEnabled) {
                          const ms = Math.max(60000, (scheduleIntervalDays * 24 * 60 * 60 + scheduleIntervalHours * 60 * 60 + val * 60) * 1000);
                          const target = Date.now() + ms;
                          setNextRunTimestamp(target);
                          localStorage.setItem("governance_brain_schedule_next_run", String(target));
                        }
                      }}
                      disabled={!scheduleEnabled}
                      className="w-20 bg-surface"
                    />
                    <span className="text-xs text-ink/70">min</span>
                  </div>
                </div>
              </div>

              <div>
                <label className="text-xs font-mono uppercase tracking-wider text-ink/60 block mb-1">
                  Target Email(s) (comma-separated)
                </label>
                <Input
                  placeholder="e.g. manager@corp.com, team@corp.com"
                  value={scheduleEmails}
                  onChange={(e) => {
                    const val = e.target.value;
                    setScheduleEmails(val);
                    localStorage.setItem("governance_brain_schedule_emails", val);
                  }}
                  className="bg-surface"
                />
              </div>
            </div>

            {/* Delivery channel settings */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-slate-line/50 pt-4">
              <div>
                <label className="text-xs font-mono uppercase tracking-wider text-ink/60 block mb-1">
                  Send via
                </label>
                <select
                  value={scheduleVia}
                  onChange={(e) => {
                    const val = e.target.value as "composio" | "hermes";
                    setScheduleVia(val);
                    localStorage.setItem("governance_brain_schedule_via", val);
                  }}
                  disabled={!scheduleEnabled}
                  className="h-10 w-full rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-synapse"
                >
                  <option value="composio">Composio (direct)</option>
                  <option value="hermes">Hermes</option>
                </select>
              </div>

              {scheduleVia === "composio" && (
                <div>
                  <label className="text-xs font-mono uppercase tracking-wider text-ink/60 block mb-1">
                    Email Account / Provider
                  </label>
                  <select
                    value={scheduleEmailProvider}
                    onChange={(e) => {
                      const val = e.target.value as "gmail" | "outlook";
                      setScheduleEmailProvider(val);
                      localStorage.setItem("governance_brain_schedule_email_provider", val);
                    }}
                    disabled={!scheduleEnabled}
                    className="h-10 w-full rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-synapse"
                  >
                    <option value="gmail">Gmail</option>
                    <option value="outlook">Outlook</option>
                  </select>
                </div>
              )}
            </div>

            {scheduleStatusMsg && (
              <div className="text-xs text-synapse font-mono bg-surface border border-slate-line/50 rounded p-2">
                {scheduleStatusMsg}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardContent className="flex flex-wrap items-end gap-4 pt-5">
            <div>
              <Label>Scope</Label>
              <div className="flex gap-1 rounded-lg border border-slate-line p-1">
                {(["weekly", "meeting", "project"] as Scope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                      scope === s ? "bg-ink text-paper" : "text-ink/60 hover:bg-ink/5"
                    }`}
                  >
                    {s === "meeting"
                      ? "By meeting"
                      : s === "project"
                      ? "By project"
                      : "Weekly"}
                  </button>
                ))}
              </div>
            </div>

            {scope === "weekly" && (
              <div>
                <Label>Week of (any day)</Label>
                <Input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-44"
                />
              </div>
            )}
            {scope === "meeting" && (
              <div>
                <Label>Meeting</Label>
                <select
                  value={meetingId}
                  onChange={(e) => setMeetingId(e.target.value)}
                  className="h-10 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
                >
                  {meetings.map((m) => (
                    <option key={m.meeting_id} value={m.meeting_id}>
                      {m.meeting_id} — {m.title}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {scope === "project" && (
              <div>
                <Label>Project</Label>
                <select
                  value={projectId ?? ""}
                  onChange={(e) => setProjectId(Number(e.target.value))}
                  className="h-10 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
                >
                  {projects.length === 0 && <option value="">No projects yet</option>}
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      Project {p.project_id} ({p.meetings})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="h-10 flex items-center gap-2 select-none">
              <input
                id="use-gstack-pdf"
                type="checkbox"
                checked={useGStackPdf}
                onChange={(e) => {
                  const val = e.target.checked;
                  setUseGStackPdf(val);
                  localStorage.setItem("governance_brain_use_gstack_pdf", String(val));
                }}
                className="h-4 w-4 rounded border-slate-line text-recall focus:ring-recall cursor-pointer"
              />
              <label
                htmlFor="use-gstack-pdf"
                className="text-sm font-medium text-ink cursor-pointer"
              >
                Use GStack Premium PDF Render
              </label>
            </div>

            <Button onClick={preview} disabled={loading}>
              <FileText className="h-4 w-4" />
              {loading ? "Building…" : "Preview"}
            </Button>
            <a href={pdfUrl} target="_blank" rel="noreferrer">
              <Button variant="recall" type="button">
                <Download className="h-4 w-4" />
                Download PDF
              </Button>
            </a>
          </CardContent>
        </Card>

        {error && (
          <div className="rounded-lg border border-recall/40 bg-recall-soft px-4 py-3 text-sm text-ink">
            {error}
          </div>
        )}

        {autoSendResult && (
          <div className="mb-4 rounded-lg border border-synapse/40 bg-recall-soft px-4 py-3 text-sm text-ink">
            {autoSendResult}
          </div>
        )}

        {report && <ReportPreview report={report} />}

        {report && (
          <EmailReportCard
            scope={scope}
            meetingId={meetingId}
            projectId={projectId}
            date={date}
            label={report.scope_label}
            autoSend={autoSend}
            updateAutoSend={updateAutoSend}
            useGStackPdf={useGStackPdf}
          />
        )}
      </div>
    </div>
  );
}

function EmailReportCard({
  scope,
  meetingId,
  projectId,
  date,
  label,
  autoSend,
  updateAutoSend,
  useGStackPdf,
}: {
  scope: Scope;
  meetingId: string;
  projectId: number | null;
  date: string;
  label: string;
  autoSend: { enabled: boolean; target_email: string; email_provider: string };
  updateAutoSend: (updated: Partial<typeof autoSend>) => void;
  useGStackPdf: boolean;
}) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState(`Management report: ${label}`);
  const [message, setMessage] = useState(
    `Please find attached the management report for ${label}.`
  );
  const [via, setVia] = useState<"composio" | "hermes">("composio");
  const [provider, setProvider] = useState<"gmail" | "outlook">("gmail");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);

  async function send() {
    if (!to.trim() || busy) return;
    setBusy(true);
    setResult(null);
    setOk(null);
    try {
      const res = await api.emailReport({
        scope,
        meeting_id: scope === "meeting" ? meetingId : undefined,
        project_id: scope === "project" ? projectId : undefined,
        date: scope === "weekly" ? date : undefined,
        to: to.trim(),
        subject,
        message,
        via,
        email_provider: provider,
        gstack: useGStackPdf,
      });
      setOk(res.ok);
      setResult(res.output);
    } catch (e) {
      setOk(false);
      setResult(e instanceof Error ? e.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-synapse" /> Email this report via Hermes
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Auto-send Section */}
        <div className="flex flex-col gap-3 rounded-lg border border-slate-line bg-paper p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium text-sm text-ink">Auto-email report</h4>
              <p className="text-xs text-ink/55">
                Automatically email the PDF when preview is built.
              </p>
            </div>
            <button
              type="button"
              onClick={() => updateAutoSend({ enabled: !autoSend.enabled })}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-recall ${
                autoSend.enabled ? "bg-recall" : "bg-slate-line"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-paper shadow ring-0 transition duration-200 ease-in-out ${
                  autoSend.enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {autoSend.enabled && (
            <div className="mt-2 space-y-3 border-t border-slate-line/50 pt-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-medium text-ink/75 block mb-1">
                    Auto-send recipient email:
                  </label>
                  <Input
                    placeholder="Recipient email for auto-send"
                    value={autoSend.target_email}
                    onChange={(e) => updateAutoSend({ target_email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-ink/75 block mb-1">
                    Email Account / Provider:
                  </label>
                  <select
                    value={autoSend.email_provider}
                    onChange={(e) => updateAutoSend({ email_provider: e.target.value })}
                    className="h-10 w-full rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
                  >
                    <option value="gmail">Gmail</option>
                    <option value="outlook">Outlook</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="text-sm text-ink/55">
          Generates the PDF and emails it as an attachment. Send directly via
          Composio (your connected account) or via Hermes.
        </p>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-1.5">
            <span className="text-ink/60">Send via:</span>
            <select
              value={via}
              onChange={(e) => setVia(e.target.value as "composio" | "hermes")}
              className="h-9 rounded-lg border border-slate-line bg-surface px-2 text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
            >
              <option value="composio">Composio (direct)</option>
              <option value="hermes">Hermes</option>
            </select>
          </label>
          {via === "composio" && (
            <label className="flex items-center gap-1.5">
              <span className="text-ink/60">Account:</span>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as "gmail" | "outlook")}
                className="h-9 rounded-lg border border-slate-line bg-surface px-2 text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
              >
                <option value="gmail">Gmail</option>
                <option value="outlook">Outlook</option>
              </select>
            </label>
          )}
        </div>
        <Input
          placeholder="Recipient email (e.g. you@example.com)"
          value={to}
          onChange={(e) => setTo(e.target.value)}
        />
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-slate-line bg-surface px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
        />
        <Button variant="recall" onClick={send} disabled={busy || !to.trim()}>
          <Send className="h-4 w-4" />
          {busy ? "Sending via Hermes…" : "Generate & send"}
        </Button>
        {result && (
          <div
            className={`rounded-lg border px-3 py-2 text-xs ${
              ok
                ? "border-synapse/40 bg-recall-soft text-ink"
                : "border-recall/40 text-ink"
            }`}
          >
            <pre className="whitespace-pre-wrap break-words font-mono leading-relaxed">
              {result}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ReportPreview({ report }: { report: ProjectReport }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-2xl font-medium text-ink">
          {report.scope_label}
        </h2>
        <p className="font-mono text-xs text-ink/45">
          generated {new Date(report.generated_at).toLocaleString()} · via{" "}
          {report.provider}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        <Stat label="Meetings" value={report.stats.meetings} />
        <Stat label="People" value={report.stats.people} />
        <Stat label="Tasks" value={report.stats.tasks} />
        <Stat label="Edges" value={report.stats.graph_edges} />
        <Stat label="Done" value={report.stats.done_action_items} />
        <Stat label="Open" value={report.stats.open_action_items} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Executive summary</CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-relaxed text-ink/80">
          {report.executive_summary}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InsightCard
          title="Merits"
          icon={<ThumbsUp className="h-4 w-4 text-[#2E7D52]" />}
          items={report.merits}
          accent="#2E7D52"
        />
        <InsightCard
          title="Demerits"
          icon={<ThumbsDown className="h-4 w-4 text-[#B3471F]" />}
          items={report.demerits}
          accent="#B3471F"
        />
      </div>
    </div>
  );
}

function InsightCard({
  title,
  icon,
  items,
  accent,
}: {
  title: string;
  icon: React.ReactNode;
  items: { text: string; evidence: string | null; source: string | null }[];
  accent: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon} {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((it, i) => (
          <div key={i} className="border-l-2 pl-3" style={{ borderColor: accent }}>
            <p className="text-sm text-ink">{it.text}</p>
            {it.evidence && (
              <p className="mt-0.5 text-xs italic text-ink/50">
                {it.source ? `${it.source}: ` : ""}“{it.evidence}”
              </p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-3 text-center">
      <div className="font-display text-2xl font-medium text-ink">{value}</div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-ink/45">
        {label}
      </div>
    </Card>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-ink/45">
      {children}
    </div>
  );
}

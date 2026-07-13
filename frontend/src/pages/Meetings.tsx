import { FormEvent, useEffect, useState } from "react";
import { Plus, UploadCloud } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { MeetingCard } from "@/components/MeetingCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { api, IngestionResult, MeetingSummary } from "@/services/api";

const SAMPLE = `Alice:
API development should finish this week.

Bob:
Authentication module is pending.

Charlie:
I'll complete testing.`;

export function Meetings() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [autoIngestEnabled, setAutoIngestEnabled] = useState(false);

  function refresh() {
    api.listMeetings().then(setMeetings).catch(() => void 0);
  }

  useEffect(() => {
    refresh();
    api.getAutoIngestSettings()
      .then((res) => setAutoIngestEnabled(res.enabled))
      .catch(() => void 0);
  }, []);

  useEffect(() => {
    if (!autoIngestEnabled) return;
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [autoIngestEnabled]);

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Meetings" />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-ink/55">
            Upload a transcript to fold it into the organizational memory.
          </p>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2.5 select-none">
              <button
                type="button"
                onClick={async () => {
                  const nextVal = !autoIngestEnabled;
                  setAutoIngestEnabled(nextVal);
                  try {
                    await api.setAutoIngestSettings({ enabled: nextVal });
                  } catch (err) {
                    console.error("Failed to update auto-ingest settings:", err);
                  }
                }}
                className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-recall ${
                  autoIngestEnabled ? "bg-recall" : "bg-slate-line"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-paper shadow ring-0 transition duration-200 ease-in-out ${
                    autoIngestEnabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
              <span className="text-sm font-medium text-ink">
                Auto-Ingest Downloads
              </span>
            </div>

            <Button onClick={() => setOpen((v) => !v)} variant={open ? "ghost" : "primary"}>
              <Plus className="h-4 w-4" />
              {open ? "Close" : "New meeting"}
            </Button>
          </div>
        </div>

        {open && <UploadForm onDone={() => { refresh(); setOpen(false); }} />}

        {meetings.length === 0 ? (
          <p className="mt-6 text-sm text-ink/55">Nothing ingested yet.</p>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {meetings.map((m) => (
              <MeetingCard key={m.meeting_id} meeting={m} onDeleted={refresh} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function UploadForm({ onDone }: { onDone: () => void }) {
  const [meetingId, setMeetingId] = useState("");
  const [title, setTitle] = useState("");
  const [projectId, setProjectId] = useState("");
  const [transcript, setTranscript] = useState(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestionResult | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.uploadMeeting({
        meeting_id: meetingId.trim(),
        title: title.trim() || "Untitled Meeting",
        transcript,
        project_id: projectId.trim() ? Number(projectId) : null,
      });
      setResult(res);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="animate-rise">
      <CardHeader>
        <CardTitle>New meeting</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Input
              placeholder="Meeting ID (e.g. M001)"
              value={meetingId}
              onChange={(e) => setMeetingId(e.target.value)}
              required
            />
            <Input
              placeholder="Title (e.g. Sprint Meeting)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Input
              type="number"
              placeholder="Project ID (e.g. 1)"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            />
          </div>
          <Textarea
            rows={8}
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            className="font-mono text-xs"
          />
          {error && (
            <div className="rounded-lg border border-recall/40 bg-recall-soft px-3 py-2 text-sm text-ink">
              {error}
            </div>
          )}
          {result && (
            <div className="rounded-lg bg-paper px-3 py-2 font-mono text-xs text-ink/70">
              ingested {result.chunks} chunks · {result.entities} entities ·{" "}
              {result.edges} edges · {result.action_items} actions
            </div>
          )}
          <Button type="submit" variant="recall" disabled={busy || !meetingId.trim()}>
            <UploadCloud className="h-4 w-4" />
            {busy ? "Ingesting…" : "Ingest into memory"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

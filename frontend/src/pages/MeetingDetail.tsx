import * as React from "react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { GraphTriple } from "@/components/GraphTriple";
import { api, MeetingDetail as Detail } from "@/services/api";

const TYPE_COLOR: Record<string, string> = {
  person: "bg-ink text-paper",
  task: "bg-recall text-ink",
  date: "bg-synapse text-paper",
};

export function MeetingDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  function load() {
    api.getMeeting(id).then(setMeeting).catch((e) => setError(e.message));
  }
  useEffect(load, [id]);

  async function remove() {
    if (!confirm(`Delete meeting ${id}? This removes it from memory permanently.`))
      return;
    setBusy(true);
    try {
      await api.deleteMeeting(id);
      navigate("/meetings");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <Navbar title={meeting?.title ?? "Meeting"} />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mb-5 flex items-center justify-between">
          <Link
            to="/meetings"
            className="inline-flex items-center gap-1.5 text-sm text-ink/60 hover:text-ink"
          >
            <ArrowLeft className="h-4 w-4" /> All meetings
          </Link>
          {meeting && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}>
                <Pencil className="h-3.5 w-3.5" />
                {editing ? "Close edit" : "Edit"}
              </Button>
              <Button variant="outline" size="sm" onClick={remove} disabled={busy}>
                <Trash2 className="h-3.5 w-3.5 text-[#B3471F]" />
                Delete
              </Button>
            </div>
          )}
        </div>

        {error && <p className="mb-4 text-sm text-[#B3471F]">{error}</p>}

        {editing && meeting && (
          <EditPanel
            meeting={meeting}
            onSaved={() => {
              setEditing(false);
              load();
            }}
          />
        )}

        {meeting && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Knowledge graph</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {meeting.edges.length === 0 ? (
                  <span className="text-sm text-ink/50">No relationships found.</span>
                ) : (
                  meeting.edges.map((e, i) => <GraphTriple key={i} edge={e} />)
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Entities</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {meeting.entities.map((e, i) => (
                  <span
                    key={i}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                      TYPE_COLOR[e.type] ?? "bg-paper text-ink"
                    }`}
                  >
                    {e.name}
                  </span>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Action items</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {meeting.action_items.length === 0 ? (
                  <span className="text-sm text-ink/50">No action items.</span>
                ) : (
                  meeting.action_items.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between rounded-lg bg-paper px-3 py-2 text-sm"
                    >
                      <span>
                        <b className="text-ink">{a.owner ?? "Unassigned"}</b>{" "}
                        <span className="text-ink/60">— {a.task}</span>
                      </span>
                      {a.due && (
                        <span className="font-mono text-[11px] text-synapse">
                          {a.due}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Transcript</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {meeting.chunks.map((c) => (
                  <div key={c.chunk_index} className="text-sm">
                    {c.speaker && (
                      <span className="font-medium text-ink">{c.speaker}: </span>
                    )}
                    <span className="text-ink/70">{c.content}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <EmailMeetingPanel meetingId={meeting.meeting_id} />
          </div>
        )}
      </div>
    </div>
  );
}

function EmailMeetingPanel({ meetingId }: { meetingId: string }) {
  const [to, setTo] = useState("");
  const [provider, setProvider] = useState<"gmail" | "outlook">("gmail");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);

  async function send() {
    if (!to.trim() || busy) return;
    setBusy(true);
    setMsg(null);
    setOk(null);
    try {
      await api.sendMeetingEmail(meetingId, { to: to.trim(), provider });
      setOk(true);
      setMsg(`Sent meeting details to ${to} via Composio (${provider}).`);
    } catch (e) {
      setOk(false);
      setMsg(e instanceof Error ? e.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Email meeting details (via Composio)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-ink/55">
          Sends this meeting's highlights, risks and action items straight from
          your connected Composio account — no Hermes, no PDF.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Recipient email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="max-w-xs"
          />
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as "gmail" | "outlook")}
            className="h-10 rounded-lg border border-slate-line bg-surface px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
          >
            <option value="gmail">Gmail</option>
            <option value="outlook">Outlook</option>
          </select>
          <Button variant="recall" onClick={send} disabled={busy || !to.trim()}>
            {busy ? "Sending…" : "Send details"}
          </Button>
        </div>
        {msg && (
          <p className={`text-xs ${ok ? "text-ink/70" : "text-recall"}`}>{msg}</p>
        )}
      </CardContent>
    </Card>
  );
}

function EditPanel({
  meeting,
  onSaved,
}: {
  meeting: Detail;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(meeting.title);
  const [append, setAppend] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const body: { title?: string; append_transcript?: string } = {};
      if (title !== meeting.title) body.title = title;
      if (append.trim()) body.append_transcript = append.trim();
      if (Object.keys(body).length === 0) {
        setMsg("Nothing to change.");
        setBusy(false);
        return;
      }
      const r = await api.editMeeting(meeting.meeting_id, body);
      setMsg(
        `Saved · ${r.chunks} chunks · ${r.entities} entities · ${r.edges} edges`
      );
      setAppend("");
      onSaved();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-4 animate-rise">
      <CardHeader>
        <CardTitle>Edit meeting</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label>Title</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <Label>Add to transcript</Label>
          <Textarea
            rows={5}
            value={append}
            onChange={(e) => setAppend(e.target.value)}
            placeholder={"Dana:\nI'll own the deployment."}
            className="font-mono text-xs"
          />
          <p className="mt-1 text-xs text-ink/45">
            New lines are appended and the meeting's memory (graph, entities,
            vectors) is rebuilt automatically.
          </p>
        </div>
        {msg && <p className="text-xs text-ink/60">{msg}</p>}
        <Button variant="recall" onClick={save} disabled={busy}>
          <Plus className="h-4 w-4" />
          {busy ? "Saving…" : "Save changes"}
        </Button>
      </CardContent>
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

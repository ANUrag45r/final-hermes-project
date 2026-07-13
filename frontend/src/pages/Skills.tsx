import * as React from "react";
import { useEffect, useState } from "react";
import {
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  Download,
  Play,
  RefreshCw,
  FileText,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, MeetingSummary, MeetingDetail } from "@/services/api";

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-ink/45">
      {children}
    </div>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  const parseInline = (text: string) => {
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    
    // Bold: **text** or __text__
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    escaped = escaped.replace(/__(.*?)__/g, "<strong>$1</strong>");
    
    // Italics: *text* or _text_
    escaped = escaped.replace(/\*(.*?)\*/g, "<em>$1</em>");
    escaped = escaped.replace(/_(.*?)_/g, "<em>$1</em>");

    // Inline code: `code`
    escaped = escaped.replace(/`(.*?)`/g, '<code class="px-1.5 py-0.5 rounded bg-ink/5 font-mono text-xs text-synapse font-medium">$1</code>');
    
    return <span dangerouslySetInnerHTML={{ __html: escaped }} />;
  };

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  
  let inList = false;
  let listItems: React.ReactNode[] = [];
  
  const flushList = (key: number) => {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key}`} className="my-3 ml-6 list-disc space-y-1 text-sm text-ink/80">
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList(idx);
      return;
    }

    if (trimmed.startsWith("# ")) {
      flushList(idx);
      elements.push(
        <h1 key={idx} className="font-display text-2xl font-semibold text-ink mt-6 mb-3 border-b pb-1 border-slate-line">
          {parseInline(trimmed.slice(2))}
        </h1>
      );
    } else if (trimmed.startsWith("## ")) {
      flushList(idx);
      elements.push(
        <h2 key={idx} className="font-display text-xl font-medium text-ink mt-5 mb-2.5">
          {parseInline(trimmed.slice(3))}
        </h2>
      );
    } else if (trimmed.startsWith("### ")) {
      flushList(idx);
      elements.push(
        <h3 key={idx} className="font-display text-lg font-medium text-synapse mt-4 mb-2">
          {parseInline(trimmed.slice(4))}
        </h3>
      );
    } else if (trimmed.startsWith("#### ")) {
      flushList(idx);
      elements.push(
        <h4 key={idx} className="font-display text-md font-medium text-ink/70 mt-3 mb-1.5">
          {parseInline(trimmed.slice(5))}
        </h4>
      );
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      inList = true;
      listItems.push(
        <li key={idx} className="pl-1">
          {parseInline(trimmed.slice(2))}
        </li>
      );
    } else if (trimmed.startsWith("---") || trimmed.startsWith("___")) {
      flushList(idx);
      elements.push(
        <hr key={idx} className="my-5 border-t border-slate-line" />
      );
    } else {
      flushList(idx);
      elements.push(
        <p key={idx} className="text-sm leading-relaxed text-ink/85 my-2.5">
          {parseInline(trimmed)}
        </p>
      );
    }
  });

  flushList(lines.length);

  return <div className="prose max-w-none">{elements}</div>;
}

export function Skills() {
  const [skill, setSkill] = useState<"spec" | "retro">("spec");
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [meetingId, setMeetingId] = useState<string>("");
  const [meetingDetail, setMeetingDetail] = useState<MeetingDetail | null>(null);
  
  const [showTranscript, setShowTranscript] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ markdown: string; pdf_url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listMeetings().then((m) => {
      setMeetings(m);
      if (m.length > 0) {
        setMeetingId(m[0].meeting_id);
      }
    }).catch(() => void 0);
  }, []);

  useEffect(() => {
    if (!meetingId) {
      setMeetingDetail(null);
      return;
    }
    api.getMeeting(meetingId)
      .then(setMeetingDetail)
      .catch((err) => console.error("Failed to load meeting details:", err));
  }, [meetingId]);

  async function handleRunSkill() {
    if (!meetingId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.runSkill({
        skill_name: skill,
        meeting_id: meetingId,
      });
      setResult({
        markdown: res.markdown,
        pdf_url: api.skillReportPdfUrl(skill, meetingId),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Skill execution failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col bg-paper">
      <Navbar title="GStack Skills" />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Controls Column */}
          <div className="space-y-6 lg:col-span-4">
            <Card className="border-slate-line bg-surface">
              <CardHeader className="pb-4">
                <CardTitle className="flex items-center gap-2 text-ink font-semibold">
                  <Sparkles className="h-5 w-5 text-synapse animate-pulse" />
                  Skill & Target
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Skill selector */}
                <div>
                  <Label>Select GStack Skill</Label>
                  <div className="flex rounded-lg border border-slate-line p-1 bg-paper/50">
                    <button
                      onClick={() => { setSkill("spec"); setResult(null); setError(null); }}
                      className={`flex-1 rounded-md py-2 text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                        skill === "spec"
                          ? "bg-ink text-paper shadow-sm"
                          : "text-ink/60 hover:bg-ink/5"
                      }`}
                    >
                      /spec (Specification)
                    </button>
                    <button
                      onClick={() => { setSkill("retro"); setResult(null); setError(null); }}
                      className={`flex-1 rounded-md py-2 text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                        skill === "retro"
                          ? "bg-ink text-paper shadow-sm"
                          : "text-ink/60 hover:bg-ink/5"
                      }`}
                    >
                      /retro (Retrospective)
                    </button>
                  </div>
                </div>

                {/* Meeting selector */}
                <div>
                  <Label>Select Target Meeting</Label>
                  {meetings.length === 0 ? (
                    <div className="text-sm text-ink/40 py-2">No meetings available. Ingest one first.</div>
                  ) : (
                    <select
                      value={meetingId}
                      onChange={(e) => { setMeetingId(e.target.value); setResult(null); setError(null); }}
                      className="w-full h-10 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall transition-all"
                    >
                      {meetings.map((m) => (
                        <option key={m.meeting_id} value={m.meeting_id}>
                          {m.meeting_id} — {m.title}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <Button
                  onClick={handleRunSkill}
                  disabled={loading || !meetingId}
                  className="w-full h-11 text-xs uppercase tracking-wider font-bold"
                  variant="primary"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Executing...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Execute Skill
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Meeting Detail Card */}
            {meetingDetail && (
              <Card className="border-slate-line bg-surface">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-ink font-semibold">
                    Target Information
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="text-xs space-y-1.5">
                    <div className="flex justify-between">
                      <span className="text-ink/40">Title:</span>
                      <span className="font-medium text-ink text-right max-w-[200px] truncate">{meetingDetail.title}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink/40">Meeting ID:</span>
                      <span className="font-mono text-ink">{meetingDetail.meeting_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink/40">Ingested Date:</span>
                      <span className="text-ink">{new Date(meetingDetail.date).toLocaleDateString()}</span>
                    </div>
                    {meetingDetail.duration && (
                      <div className="flex justify-between">
                        <span className="text-ink/40">Duration:</span>
                        <span className="text-ink">{meetingDetail.duration} minutes</span>
                      </div>
                    )}
                  </div>

                  <hr className="border-slate-line" />

                  {/* Transcript Preview */}
                  <div>
                    <button
                      onClick={() => setShowTranscript(!showTranscript)}
                      className="flex w-full items-center justify-between py-1 text-xs font-semibold text-synapse hover:text-synapse/80"
                    >
                      <span>{showTranscript ? "Hide" : "Show"} Raw Transcript</span>
                      {showTranscript ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </button>
                    {showTranscript && (
                      <div className="mt-2 max-h-60 overflow-y-auto rounded bg-ink/5 p-3 font-mono text-[11px] leading-relaxed text-ink/75 scrollbar-thin">
                        <pre className="whitespace-pre-wrap">{meetingDetail.raw_transcript}</pre>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Results/Workspace Column */}
          <div className="lg:col-span-8">
            <Card className="h-full border-slate-line bg-surface min-h-[500px] flex flex-col">
              <CardHeader className="border-b border-slate-line pb-4 flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-ink font-semibold">
                  <FileText className="h-5 w-5 text-ink/50" />
                  Workspace Output
                </CardTitle>
                {result && (
                  <div className="flex gap-2">
                    <a
                      href={result.pdf_url}
                      className="inline-flex h-9 items-center justify-center rounded-lg bg-ink text-paper px-4 text-xs font-bold uppercase tracking-wider transition-colors hover:bg-ink/90"
                    >
                      <Download className="mr-2 h-3.5 w-3.5" />
                      Download PDF
                    </a>
                    <button
                      onClick={handleRunSkill}
                      className="inline-flex h-9 items-center justify-center rounded-lg border border-slate-line bg-surface text-ink px-4 text-xs font-bold uppercase tracking-wider transition-colors hover:bg-ink/5"
                    >
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      Re-run
                    </button>
                  </div>
                )}
              </CardHeader>
              <CardContent className="flex-1 p-6 overflow-y-auto">
                {loading && (
                  <div className="flex h-full flex-col items-center justify-center py-20 space-y-4">
                    <Loader2 className="h-10 w-10 text-synapse animate-spin" />
                    <div className="text-center space-y-1.5">
                      <p className="text-sm font-medium text-ink">Executing GStack {skill.toUpperCase()} Skill</p>
                      <p className="text-xs text-ink/40">Reasoning via Hermes model — this may take up to a minute</p>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="rounded-lg border border-red-200 bg-red-50/50 p-4 text-sm text-red-800 flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
                    <div className="space-y-1">
                      <p className="font-semibold">Execution Failed</p>
                      <p className="text-red-700/90 leading-relaxed font-mono text-xs">{error}</p>
                    </div>
                  </div>
                )}

                {result && (
                  <div className="space-y-6 animate-rise">
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-md w-fit">
                      <CheckCircle2 className="h-4 w-4" />
                      COMPLETED SUCCESSFULLY
                    </div>
                    <div className="bg-paper p-6 rounded-xl border border-slate-line shadow-sm">
                      <MarkdownRenderer content={result.markdown} />
                    </div>
                  </div>
                )}

                {!loading && !result && !error && (
                  <div className="flex h-full flex-col items-center justify-center py-20 text-center text-ink/40">
                    <Sparkles className="h-12 w-12 stroke-[1.25] text-ink/20 mb-3" />
                    <p className="text-sm font-medium">Workspace is ready</p>
                    <p className="text-xs max-w-sm mt-1 text-ink/30">
                      Select a GStack skill and a target meeting on the left sidebar to generate reports.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

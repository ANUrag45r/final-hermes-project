import * as React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, BrainCircuit, CalendarDays, Check, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { api, MeetingSummary } from "@/services/api";

export function MeetingCard({
  meeting,
  onDeleted,
}: {
  meeting: MeetingSummary;
  onDeleted?: () => void;
}) {
  const [saving, setSaving] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [saveError, setSaveError] = React.useState<string | null>(null);

  const date = new Date(meeting.date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  async function remove(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete meeting ${meeting.meeting_id}?`)) return;
    await api.deleteMeeting(meeting.meeting_id);
    onDeleted?.();
  }

  async function saveToGbrain(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (saving) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const res = await api.agentSaveMeeting(meeting.meeting_id);
      if (res.ok) setSaved(true);
      else setSaveError("Hermes reported an error");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Link to={`/meetings/${meeting.meeting_id}`} className="group block">
      <Card className="animate-rise p-5 transition-colors group-hover:border-ink/30">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-synapse">
                {meeting.meeting_id}
              </span>
              {meeting.project_id != null && (
                <span className="rounded-full bg-ink/5 px-2 py-0.5 font-mono text-[10px] text-ink/60">
                  project {meeting.project_id}
                </span>
              )}
            </div>
            <h3 className="mt-1 font-display text-lg font-medium text-ink">
              {meeting.title}
            </h3>
          </div>
          <div className="flex items-center gap-1">
            {onDeleted && (
              <button
                onClick={remove}
                aria-label="Delete meeting"
                title="Delete meeting"
                className="rounded-md p-1.5 text-ink/30 opacity-0 transition-all hover:bg-[#B3471F]/10 hover:text-[#B3471F] group-hover:opacity-100"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            <ArrowUpRight className="h-4 w-4 text-ink/30 transition-colors group-hover:text-recall" />
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs text-ink/55">
            <CalendarDays className="h-3.5 w-3.5" />
            {date}
            {meeting.duration ? <span>· {meeting.duration} min</span> : null}
          </div>
          <button
            onClick={saveToGbrain}
            disabled={saving}
            title="Tell Hermes to save this meeting to its gbrain memory"
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
              saved
                ? "border-synapse/40 bg-recall-soft text-ink"
                : "border-slate-line text-ink/70 hover:border-recall hover:text-recall"
            } disabled:opacity-60`}
          >
            {saved ? (
              <>
                <Check className="h-3.5 w-3.5" /> Saved to gbrain
              </>
            ) : (
              <>
                <BrainCircuit className="h-3.5 w-3.5" />
                {saving ? "Saving…" : "Save to gbrain"}
              </>
            )}
          </button>
        </div>
        {saveError && (
          <p className="mt-2 text-xs text-[#B3471F]">{saveError}</p>
        )}
      </Card>
    </Link>
  );
}

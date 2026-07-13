import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { SummaryCard } from "@/components/SummaryCard";
import { MeetingCard } from "@/components/MeetingCard";
import { api, DashboardStats, MeetingSummary } from "@/services/api";

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);

  useEffect(() => {
    api.stats().then(setStats).catch(() => void 0);
    api.listMeetings().then(setMeetings).catch(() => void 0);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Dashboard" />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <SummaryCard label="Meetings" value={stats?.meetings ?? "—"} hint="ingested" />
          <SummaryCard label="Memory chunks" value={stats?.chunks ?? "—"} hint="indexed turns" />
          <SummaryCard label="Graph edges" value={stats?.graph_edges ?? "—"} hint="relationships" />
          <SummaryCard
            label="Open actions"
            value={stats?.open_action_items ?? "—"}
            hint="awaiting follow-up"
          />
        </div>

        <h2 className="mb-3 mt-9 font-display text-xl font-medium text-ink">
          Recent meetings
        </h2>
        {meetings.length === 0 ? (
          <p className="text-sm text-ink/55">
            No meetings yet. Add one from the Meetings tab to build memory.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {meetings.map((m) => (
              <MeetingCard key={m.meeting_id} meeting={m} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

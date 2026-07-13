import { useEffect, useState } from "react";
import { FolderGit2 } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { ChatWindow } from "@/components/ChatWindow";
import { api, ProjectSummary } from "@/services/api";

export function Chat() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => void 0);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Ask the Brain" />
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-8 py-6">
        <div className="mb-4 flex items-center gap-2">
          <FolderGit2 className="h-4 w-4 text-synapse" />
          <span className="font-mono text-[11px] uppercase tracking-wider text-ink/45">
            scope
          </span>
          <select
            value={projectId ?? ""}
            onChange={(e) =>
              setProjectId(e.target.value ? Number(e.target.value) : null)
            }
            className="h-9 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
          >
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                Project {p.project_id} ({p.meetings} meeting
                {p.meetings === 1 ? "" : "s"})
              </option>
            ))}
          </select>
          {projectId !== null && (
            <span className="text-xs text-ink/55">
              Answers will use only Project {projectId}'s transcripts.
            </span>
          )}
        </div>
        <ChatWindow projectId={projectId} />
      </div>
    </div>
  );
}

import { FormEvent, useRef, useState } from "react";
import { Mail, Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GraphTriple } from "@/components/GraphTriple";
import { api, ChatResponse } from "@/services/api";

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

export function ChatWindow({
  meetingId,
  projectId,
}: {
  meetingId?: string;
  projectId?: number | null;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function ask(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    setQuery("");
    setBusy(true);
    const index = turns.length;
    setTurns((t) => [...t, { question: q }]);
    try {
      const response = await api.chat({
        query: q,
        meeting_id: meetingId,
        project_id: projectId ?? undefined,
      });
      setTurns((t) =>
        t.map((turn, i) => (i === index ? { ...turn, response } : turn))
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setTurns((t) =>
        t.map((turn, i) => (i === index ? { ...turn, error: message } : turn))
      );
    } finally {
      setBusy(false);
      requestAnimationFrame(() =>
        endRef.current?.scrollIntoView({ behavior: "smooth" })
      );
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-6 overflow-y-auto pb-4">
        {turns.length === 0 && <EmptyState />}
        {turns.map((turn, i) => (
          <div key={i} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-sm text-paper">
                {turn.question}
              </div>
            </div>

            {turn.response && <AnswerBlock response={turn.response} />}
            {turn.error && (
              <div className="rounded-lg border border-recall/40 bg-recall-soft px-4 py-3 text-sm text-ink">
                {turn.error}
              </div>
            )}
            {!turn.response && !turn.error && (
              <div className="font-mono text-xs text-ink/40">recalling…</div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={ask} className="flex items-center gap-2 border-t border-slate-line pt-4">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What task was assigned to Bob?"
          disabled={busy}
        />
        <Button type="submit" variant="recall" disabled={busy || !query.trim()}>
          <Send className="h-4 w-4" />
          Ask
        </Button>
      </form>
    </div>
  );
}

function AnswerBlock({ response }: { response: ChatResponse }) {
  const { answer, context, provider, emails } = response;
  const isMail = response.action.startsWith("mail");
  return (
    <div className="max-w-[88%] space-y-3">
      <div className="rounded-2xl rounded-bl-sm border border-slate-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink shadow-card">
        <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-synapse">
          {isMail ? <Mail className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}{" "}
          {isMail ? "outlook" : "answer"} · via {provider}
        </div>
        <p className="whitespace-pre-line">{answer}</p>
      </div>

      {emails && emails.length > 0 && (
        <div className="space-y-2">
          {emails.map((e) => (
            <div
              key={e.id}
              className="rounded-xl border border-slate-line bg-surface p-3 text-sm shadow-card"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{e.subject}</span>
                <span className="font-mono text-[10px] text-ink/40">
                  {e.received ? new Date(e.received).toLocaleString() : ""}
                </span>
              </div>
              <div className="text-xs text-synapse">{e.sender}</div>
              {e.preview && (
                <div className="mt-1 text-xs text-ink/60">{e.preview}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {!isMail &&
        (context.graph_facts.length > 0 || context.vector_hits.length > 0) && (
          <div className="rounded-xl bg-paper p-3 ring-1 ring-slate-line">
            <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink/40">
              evidence
            </div>
            {context.graph_facts.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {context.graph_facts.map((f, i) => (
                  <GraphTriple key={i} edge={f} />
                ))}
              </div>
            )}
            {context.vector_hits.map((h, i) => (
              <div key={i} className="text-xs text-ink/65">
                <span className="text-ink/40">{(h.score * 100).toFixed(0)}%</span>{" "}
                {h.speaker ? <b>{h.speaker}: </b> : null}
                {h.content}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="font-display text-xl text-ink">Ask the organizational memory</div>
      <p className="mt-2 max-w-sm text-sm text-ink/55">
        Answers are grounded in ingested meetings — retrieved from the knowledge
        graph and semantic memory, then reasoned over by Hermes.
      </p>
    </div>
  );
}

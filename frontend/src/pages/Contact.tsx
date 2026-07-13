import { useEffect, useState } from "react";
import {
  CalendarDays,
  Inbox,
  Mail,
  RefreshCw,
  Send,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  Clock,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";

type Status = Awaited<ReturnType<typeof api.commsStatus>>;
type Tab = "email" | "calendar";

export function Contact() {
  const [status, setStatus] = useState<Status | null>(null);
  const [tab, setTab] = useState<Tab>("email");
  const [provider, setProvider] = useState("gmail");

  const loadStatus = () => api.commsStatus().then(setStatus).catch(() => void 0);
  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Navbar title="Contact" />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <ConnectionBar status={status} onRefresh={loadStatus} />

        {status && !status.enabled && (
          <Card className="mb-6 border-recall/40">
            <CardContent className="pt-5 text-sm text-ink/80">
              Composio isn't configured yet. Add{" "}
              <code className="rounded bg-ink/5 px-1">COMPOSIO_API_KEY</code> to{" "}
              <code className="rounded bg-ink/5 px-1">backend/.env</code> and
              restart the backend. Then connect Gmail, Outlook and Teams in the
              Composio dashboard.
            </CardContent>
          </Card>
        )}

        <div className="mb-5 flex items-center gap-4">
          <div className="flex gap-1 rounded-lg border border-slate-line p-1">
            {(["email", "calendar"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                  tab === t ? "bg-ink text-paper" : "text-ink/60 hover:bg-ink/5"
                }`}
              >
                {t === "email" ? (
                  <Mail className="h-4 w-4" />
                ) : (
                  <CalendarDays className="h-4 w-4" />
                )}
                {t}
              </button>
            ))}
          </div>

          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="h-9 rounded-lg border border-slate-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
          >
            <option value="gmail">{tab === "email" ? "Gmail" : "Google Calendar"}</option>
            <option value="outlook">Outlook</option>
          </select>
        </div>

        {tab === "email" ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Inboxer provider={provider} />
            <Composer provider={provider} />
          </div>
        ) : (
          <CalendarView provider={provider} />
        )}
      </div>
    </div>
  );
}

function ConnectionBar({
  status,
  onRefresh,
}: {
  status: Status | null;
  onRefresh: () => void;
}) {
  const connected = status?.connections ?? [];
  const apps = ["gmail", "googlecalendar", "outlook", "microsoft_teams"];
  const label: Record<string, string> = {
    gmail: "Gmail",
    googlecalendar: "Google Calendar",
    outlook: "Outlook",
    microsoft_teams: "Teams",
  };
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      {apps.map((a) => {
        const on = connected.some((c) => c.app.includes(a.split("_")[0]));
        return (
          <span
            key={a}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
              on
                ? "border-recall/40 bg-recall-soft text-ink"
                : "border-slate-line text-ink/45"
            }`}
          >
            {on ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            {label[a]}
          </span>
        );
      })}
      <Button variant="ghost" size="sm" onClick={onRefresh}>
        <RefreshCw className="h-3.5 w-3.5" />
        Refresh
      </Button>
      {status?.error && (
        <span className="text-xs text-recall">{status.error}</span>
      )}
    </div>
  );
}

function useAsyncResult() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<void>) => {
    setLoading(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };
  return { loading, error, run };
}

function Inboxer({ provider }: { provider: string }) {
  const [data, setData] = useState<unknown>(null);
  const { loading, error, run } = useAsyncResult();
  const fetchMail = () =>
    run(async () => {
      const r = await api.commsEmails(provider, 10);
      setData(r.data ?? r.raw);
    });
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Inbox className="h-4 w-4 text-synapse" /> Inbox
        </CardTitle>
        <Button size="sm" onClick={fetchMail} disabled={loading}>
          {loading ? "Loading…" : "Fetch"}
        </Button>
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-recall">{error}</p>}
        {!error && !data && (
          <p className="text-sm text-ink/45">
            Click Fetch to load recent messages.
          </p>
        )}
        {data != null && <ResultView data={data} />}
      </CardContent>
    </Card>
  );
}

function Composer({ provider }: { provider: string }) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sent, setSent] = useState(false);
  const { loading, error, run } = useAsyncResult();
  const send = () =>
    run(async () => {
      await api.commsSend({ provider, to, subject, body });
      setSent(true);
      setTo("");
      setSubject("");
      setBody("");
    });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="h-4 w-4 text-synapse" /> Compose
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input placeholder="To" value={to} onChange={(e) => setTo(e.target.value)} />
        <Input
          placeholder="Subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
        />
        <textarea
          placeholder="Message"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          className="w-full rounded-lg border border-slate-line bg-surface px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
        />
        {error && <p className="text-sm text-recall">{error}</p>}
        {sent && !error && (
          <p className="text-sm text-synapse">Sent via {provider}.</p>
        )}
        <Button
          variant="recall"
          onClick={send}
          disabled={loading || !to.trim()}
        >
          <Send className="h-4 w-4" />
          {loading ? "Sending…" : "Send"}
        </Button>
      </CardContent>
    </Card>
  );
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function getEventDate(event: Record<string, unknown>): Date | null {
  const startField = event.start || event.startTime || event.date;
  if (!startField) return null;
  if (typeof startField === "string") {
    const d = new Date(startField);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof startField === "object") {
    const obj = startField as Record<string, unknown>;
    const dt = obj.dateTime || obj.date;
    if (typeof dt === "string") {
      const d = new Date(dt);
      return isNaN(d.getTime()) ? null : d;
    }
  }
  return null;
}

function CalendarView({ provider }: { provider: string }) {
  const [data, setData] = useState<unknown>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());
  const { loading, error, run } = useAsyncResult();

  const fetchEvents = () =>
    run(async () => {
      const r = await api.commsEvents(provider, 50);
      const fetchedData = r.data ?? r.raw;
      setData(fetchedData);
      
      const items = extractItems(fetchedData);
      if (items && items.length > 0) {
        const firstEventDate = getEventDate(items[0]);
        if (firstEventDate) {
          setCurrentDate(firstEventDate);
          setSelectedDate(firstEventDate);
        }
      }
    });

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth();

  const firstDayOfWeek = new Date(currentYear, currentMonth, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

  const cells: { date: Date; isCurrentMonth: boolean; isToday: boolean }[] = [];

  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const day = daysInPrevMonth - i;
    const date = new Date(currentYear, currentMonth - 1, day);
    cells.push({ date, isCurrentMonth: false, isToday: false });
  }

  const today = new Date();
  for (let i = 1; i <= daysInMonth; i++) {
    const date = new Date(currentYear, currentMonth, i);
    const isToday =
      today.getDate() === i &&
      today.getMonth() === currentMonth &&
      today.getFullYear() === currentYear;
    cells.push({ date, isCurrentMonth: true, isToday });
  }

  const totalCellsSoFar = cells.length;
  const remaining = (7 - (totalCellsSoFar % 7)) % 7;
  for (let i = 1; i <= remaining; i++) {
    const date = new Date(currentYear, currentMonth + 1, i);
    cells.push({ date, isCurrentMonth: false, isToday: false });
  }

  while (cells.length < 42) {
    const lastCell = cells[cells.length - 1];
    const date = new Date(
      lastCell.date.getFullYear(),
      lastCell.date.getMonth(),
      lastCell.date.getDate() + 1
    );
    cells.push({ date, isCurrentMonth: false, isToday: false });
  }

  const items = extractItems(data);

  const isSameDay = (d1: Date, d2: Date) =>
    d1.getDate() === d2.getDate() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getFullYear() === d2.getFullYear();

  const handlePrevMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth + 1, 1));
  };

  const handleToday = () => {
    const now = new Date();
    setCurrentDate(now);
    setSelectedDate(now);
  };

  const selectedDayEvents = items
    ? items.filter((item) => {
        const eDate = getEventDate(item);
        return eDate && selectedDate ? isSameDay(eDate, selectedDate) : false;
      })
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-5 w-5 text-synapse" />
          <h2 className="text-xl font-semibold text-ink font-display">Calendar</h2>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleToday}>
            Today
          </Button>
          <Button size="sm" onClick={fetchEvents} disabled={loading}>
            {loading ? "Loading…" : "Fetch Events"}
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-recall/40 bg-recall-soft">
          <CardContent className="py-3 text-sm text-recall">{error}</CardContent>
        </Card>
      )}

      {!data && !loading && !error && (
        <Card>
          <CardContent className="py-12 text-center">
            <CalendarDays className="mx-auto h-12 w-12 text-ink/20 mb-3" />
            <p className="text-sm text-ink/50">Click Fetch Events to synchronize and display your calendar.</p>
          </CardContent>
        </Card>
      )}

      {!!data && !items && (
        <Card>
          <CardContent className="p-4">
            <ResultView data={data} />
          </CardContent>
        </Card>
      )}

      {!!data && !!items && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          <Card className="xl:col-span-3 overflow-hidden border-slate-line bg-surface">
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-line bg-surface/50 py-4">
              <CardTitle className="text-lg font-medium text-ink font-display">
                {MONTH_NAMES[currentMonth]} {currentYear}
              </CardTitle>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="ghost" className="h-8 w-8" onClick={handlePrevMonth}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" className="h-8 w-8" onClick={handleNextMonth}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="grid grid-cols-7 border-b border-slate-line text-center bg-surface/30">
                {WEEKDAYS.map((day) => (
                  <div key={day} className="py-2 text-xs font-semibold text-ink/45 uppercase tracking-wider">
                    {day}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7 bg-slate-line gap-[1px]">
                {cells.map((cell, idx) => {
                  const dayEvents = items.filter((item) => {
                    const eDate = getEventDate(item);
                    return eDate ? isSameDay(eDate, cell.date) : false;
                  });

                  const isSelected = selectedDate ? isSameDay(cell.date, selectedDate) : false;

                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedDate(cell.date)}
                      className={`min-h-[100px] bg-surface p-2 flex flex-col justify-between cursor-pointer transition-all hover:bg-ink/5 select-none ${
                        cell.isCurrentMonth ? "" : "opacity-40 bg-surface/60"
                      } ${isSelected ? "ring-2 ring-recall ring-inset" : ""}`}
                    >
                      <div className="flex justify-between items-center">
                        <span
                          className={`text-xs font-semibold rounded-full flex items-center justify-center h-6 w-6 ${
                            cell.isToday
                              ? "bg-recall text-paper font-bold"
                              : "text-ink/80"
                          }`}
                        >
                          {cell.date.getDate()}
                        </span>
                        {dayEvents.length > 0 && (
                          <span className="h-2 w-2 rounded-full bg-synapse" />
                        )}
                      </div>
                      <div className="mt-1 flex-1 flex flex-col justify-end gap-1 overflow-hidden">
                        {dayEvents.slice(0, 2).map((ev, evIdx) => {
                          const title = pick(ev, ["subject", "summary", "title"]) || "(no subject)";
                          return (
                            <div
                              key={evIdx}
                              title={title}
                              className="text-[10px] leading-tight px-1.5 py-0.5 rounded bg-recall-soft text-ink/90 border border-recall/10 truncate font-medium"
                            >
                              {title}
                            </div>
                          );
                        })}
                        {dayEvents.length > 2 && (
                          <div className="text-[9px] text-ink/45 pl-1 font-medium">
                            + {dayEvents.length - 2} more
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <div className="xl:col-span-1">
            <Card className="h-full border-slate-line flex flex-col bg-surface min-h-[400px]">
              <CardHeader className="border-b border-slate-line bg-surface/50 py-4">
                <CardTitle className="text-sm font-semibold text-ink font-display flex flex-col gap-1">
                  <span className="text-xs text-ink/45 uppercase tracking-wider">Schedule for</span>
                  <span className="text-base text-ink">
                    {selectedDate
                      ? selectedDate.toLocaleDateString("en-US", {
                          weekday: "long",
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })
                      : "No Date Selected"}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-4">
                {selectedDayEvents.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-12">
                    <CalendarDays className="h-8 w-8 text-ink/20 mb-2" />
                    <p className="text-sm text-ink/45 font-medium">No events scheduled.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selectedDayEvents.map((ev, i) => {
                      const title = pick(ev, ["subject", "summary", "title"]) || "(no subject)";
                      const dateObj = getEventDate(ev);
                      const timeStr = dateObj
                        ? dateObj.toLocaleTimeString("en-US", {
                            hour: "numeric",
                            minute: "2-digit",
                          })
                        : "";
                      
                      const organizer = pick(ev, ["from", "sender", "organizer"]);
                      
                      return (
                        <div
                          key={i}
                          className="p-3 rounded-lg border border-slate-line bg-surface/50 hover:bg-surface transition-colors space-y-1.5"
                        >
                          <h4 className="font-semibold text-sm text-ink leading-snug">
                            {title}
                          </h4>
                          {timeStr && (
                            <div className="flex items-center gap-1.5 text-xs text-synapse font-medium">
                              <Clock className="h-3.5 w-3.5" />
                              {timeStr}
                            </div>
                          )}
                          {organizer && (
                            <div className="text-[11px] text-ink/55 truncate">
                              <span className="font-medium">Organizer:</span> {organizer}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function ResultView({ data }: { data: unknown }) {
  const items = extractItems(data);

  if (!items) {
    return (
      <pre className="max-h-80 overflow-auto rounded-lg bg-ink/5 p-3 text-xs text-ink/80">
        {JSON.stringify(data, null, 2)}
      </pre>
    );
  }

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-ink/45 font-medium">
        No messages found.
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
      {items.map((item, idx) => {
        const payload = item.payload as Record<string, any> | undefined;
        const headers = payload?.headers as { name: string; value: string }[] | undefined;
        
        const subject = getHeaderValue(headers, "Subject") || (item.subject as string) || "(No Subject)";
        const from = getHeaderValue(headers, "From") || (item.from as string) || (item.sender as string) || "Unknown Sender";
        
        const fromMatch = from.match(/^(.*?)\s*<(.*?)>$/);
        const senderName = fromMatch ? fromMatch[1] : from;
        const senderEmail = fromMatch ? fromMatch[2] : "";

        const timestampStr = (item.messageTimestamp as string) || (item.date as string) || "";
        
        let dateDisplay = "";
        if (timestampStr) {
          try {
            const dateObj = new Date(timestampStr);
            dateDisplay = dateObj.toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit"
            });
          } catch (e) {
            dateDisplay = timestampStr;
          }
        }

        return (
          <div
            key={idx}
            className="p-3.5 rounded-xl border border-slate-line bg-surface/50 hover:bg-surface transition-all flex flex-col gap-1 shadow-sm"
          >
            <div className="flex justify-between items-start gap-3">
              <div className="space-y-1">
                <span className="font-semibold text-sm text-ink block leading-snug">
                  {subject}
                </span>
                <span className="text-xs text-ink/65 block font-medium">
                  {senderName} {senderEmail && <span className="text-ink/45 font-normal">&lt;{senderEmail}&gt;</span>}
                </span>
              </div>
              {dateDisplay && (
                <span className="text-[10px] text-ink/45 font-mono shrink-0 whitespace-nowrap">
                  {dateDisplay}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function getHeaderValue(headers: { name: string; value: string }[] | undefined, name: string): string {
  if (!headers) return "";
  const found = headers.find((h) => h.name.toLowerCase() === name.toLowerCase());
  return found ? found.value : "";
}

function extractItems(data: unknown): Record<string, unknown>[] | null {
  if (Array.isArray(data)) return data as Record<string, unknown>[];
  if (data && typeof data === "object") {
    for (const key of ["messages", "items", "events", "emails", "value", "data"]) {
      const v = (data as Record<string, unknown>)[key];
      if (Array.isArray(v)) return v as Record<string, unknown>[];
    }
  }
  return null;
}

function pick(obj: Record<string, unknown>, keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
    if (v && typeof v === "object") {
      const inner = pick(v as Record<string, unknown>, ["name", "email", "dateTime", "address"]);
      if (inner) return inner;
    }
  }
  return "";
}

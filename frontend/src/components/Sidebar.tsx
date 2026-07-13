import { NavLink } from "react-router-dom";
import {
  Activity,
  AtSign,
  FileText,
  LayoutGrid,
  MessagesSquare,
  Network,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutGrid, end: true },
  { to: "/meetings", label: "Meetings", icon: Network, end: false },
  { to: "/agent", label: "Hermes Agent", icon: Activity, end: false },
  { to: "/reports", label: "Reports", icon: FileText, end: false },
  { to: "/skills", label: "Skills", icon: Sparkles, end: false },
  { to: "/contact", label: "Contact", icon: AtSign, end: false },
  { to: "/chat", label: "Ask the Brain", icon: MessagesSquare, end: false },
];

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-line bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <SynapseMark />
        <div className="leading-tight">
          <div className="font-display text-[15px] font-semibold text-ink">
            Governance
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-synapse">
            Brain
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 px-3">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-ink text-paper"
                  : "text-ink/70 hover:bg-ink/5 hover:text-ink"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-5 py-4 font-mono text-[10px] leading-relaxed text-ink/40">
        memory · graph · recall
      </div>
    </aside>
  );
}

/** Tiny three-node synapse glyph; nodes pulse to suggest active memory. */
function SynapseMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
      <line x1="6" y1="9" x2="20" y2="6" stroke="#3A7CA5" strokeWidth="1.2" />
      <line x1="6" y1="9" x2="14" y2="22" stroke="#3A7CA5" strokeWidth="1.2" />
      <line x1="20" y1="6" x2="14" y2="22" stroke="#3A7CA5" strokeWidth="1.2" />
      <circle cx="6" cy="9" r="3" fill="#0F1E2E" />
      <circle cx="20" cy="6" r="3" fill="#E8A23D" className="animate-node" />
      <circle cx="14" cy="22" r="3" fill="#0F1E2E" />
    </svg>
  );
}

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { api } from "@/services/api";
import { useTheme } from "@/lib/theme";

export function Navbar({ title }: { title: string }) {
  const [provider, setProvider] = useState<string>("");
  const [vectors, setVectors] = useState<string>("");
  const { theme, toggle } = useTheme();

  useEffect(() => {
    api
      .stats()
      .then((s) => {
        setProvider(s.hermes_provider);
        setVectors(s.vector_backend);
      })
      .catch(() => void 0);
  }, []);

  return (
    <header className="flex items-center justify-between border-b border-slate-line bg-paper/80 px-8 py-4 backdrop-blur">
      <h1 className="font-display text-2xl font-medium text-ink">{title}</h1>
      <div className="flex items-center gap-2 font-mono text-[11px] text-ink/60">
        {provider && <Pill label="hermes" value={provider} accent />}
        {vectors && <Pill label="vectors" value={vectors} />}
        <button
          onClick={toggle}
          aria-label="Toggle theme"
          title={theme === "dark" ? "Switch to light" : "Switch to dark"}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-line bg-surface text-ink transition-colors hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-recall"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
      </div>
    </header>
  );
}

function Pill({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-slate-line bg-surface px-2.5 py-1">
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          accent ? "bg-recall" : "bg-synapse"
        }`}
      />
      <span className="text-ink/40">{label}</span>
      <span className="text-ink">{value}</span>
    </span>
  );
}

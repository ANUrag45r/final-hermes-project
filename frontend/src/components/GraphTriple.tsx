import { GraphEdge, GraphFact } from "@/services/api";

/** Renders a knowledge-graph relationship as `source —relation→ target`. */
export function GraphTriple({ edge }: { edge: GraphEdge | GraphFact }) {
  return (
    <span className="triple rounded-md bg-paper px-2 py-1 ring-1 ring-slate-line">
      <span className="text-ink">{edge.source}</span>
      <span className="rel">{edge.relation}</span>
      <span className="text-ink">{edge.target}</span>
    </span>
  );
}

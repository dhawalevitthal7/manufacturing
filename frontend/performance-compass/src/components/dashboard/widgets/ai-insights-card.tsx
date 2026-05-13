import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export function AIInsightsCard() {
  const insights = [
    {
      id: "ai-1",
      title: "Build your organizational hierarchy",
      body: "Create plants, departments, and teams to unlock hierarchy-driven visibility across all modules.",
      confidence: 0.95,
      impact: "High",
    },
    {
      id: "ai-2",
      title: "Set up cascading objectives",
      body: "Organization → Plant → Department → Team objectives enable strategic alignment tracking.",
      confidence: 0.88,
      impact: "High",
    },
  ];

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card p-5">
      <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-16 -left-10 h-40 w-40 rounded-full bg-accent/15 blur-3xl" />
      <div className="relative mb-4 flex items-center gap-2">
        <div className="grid h-7 w-7 place-items-center rounded-md gradient-primary glow-primary">
          <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">AI Insights</h3>
          <p className="text-xs text-muted-foreground">Synthesized from execution signals</p>
        </div>
      </div>
      <ul className="relative space-y-3">
        {insights.map((it, i) => (
          <motion.li
            key={it.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08 }}
            className="rounded-lg border border-border/70 bg-background/50 p-3"
          >
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">{it.title}</div>
              <span className="rounded-md bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                {it.impact}
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{it.body}</p>
            <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
              <span>Confidence</span>
              <div className="h-1 w-16 overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-primary" style={{ width: `${it.confidence * 100}%` }} />
              </div>
              <span className="font-mono">{Math.round(it.confidence * 100)}%</span>
            </div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

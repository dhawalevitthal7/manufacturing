import { Clock, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface QueueItem {
  id: string;
  title: string;
  submittedBy: string;
  scope: string;
  submittedAt: string;
  priority: "low" | "med" | "medium" | "high";
}

const priorityStyles: Record<string, string> = {
  high: "bg-destructive/15 text-destructive",
  med: "bg-warning/15 text-warning",
  medium: "bg-warning/15 text-warning",
  low: "bg-muted text-muted-foreground",
};

interface Props {
  title: string;
  subtitle: string;
  items: QueueItem[];
  emptyText?: string;
}

export function QueueWidget({ title, subtitle, items, emptyText }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
          {items.length}
        </span>
      </div>
      {items.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-muted-foreground">{emptyText ?? "Nothing here."}</div>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((it) => (
            <li
              key={it.id}
              className="group flex cursor-pointer items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/40"
            >
              <span className={cn("rounded-md px-1.5 py-0.5 text-[10px] font-medium uppercase", priorityStyles[it.priority] || priorityStyles.med)}>
                {it.priority === "medium" ? "med" : it.priority}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{it.title}</div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>{it.submittedBy}</span>
                  <span>·</span>
                  <span>{it.scope}</span>
                  {it.submittedAt && (
                    <>
                      <span>·</span>
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        {it.submittedAt}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

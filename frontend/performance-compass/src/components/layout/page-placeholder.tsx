import { Construction } from "lucide-react";

export function PagePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="grid-bg flex min-h-[420px] items-center justify-center rounded-xl border border-dashed border-border bg-card/40">
        <div className="max-w-sm text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-border bg-card">
            <Construction className="h-5 w-5 text-muted-foreground" />
          </div>
          <h3 className="mt-4 text-base font-semibold">Phase 2 of 6</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            This module is part of the upcoming OKR, Reviews and Org rollouts. The dashboard shell, design system,
            permissions and widget framework are live — say the word and we'll build it next.
          </p>
        </div>
      </div>
    </div>
  );
}

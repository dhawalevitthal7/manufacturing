import type { Cycle } from "@/lib/api";

export type CycleQuarter = "Q1" | "Q2" | "Q3" | "Q4";

export interface CycleQuarterYear {
  quarter: CycleQuarter;
  year: number;
}

export const PERIOD_YEAR_MIN = 2020;
export const PERIOD_YEAR_MAX = 2030;
export const ALL_QUARTERS: CycleQuarter[] = ["Q1", "Q2", "Q3", "Q4"];

/** Years 2020–2030 for the global period filter (newest first). */
export function getSelectableYears(): number[] {
  const years: number[] = [];
  for (let y = PERIOD_YEAR_MAX; y >= PERIOD_YEAR_MIN; y -= 1) {
    years.push(y);
  }
  return years;
}

export function currentCalendarQuarter(): CycleQuarter {
  const month = new Date().getMonth() + 1;
  if (month <= 3) return "Q1";
  if (month <= 6) return "Q2";
  if (month <= 9) return "Q3";
  return "Q4";
}

const QUARTER_BY_MONTH: Record<number, CycleQuarterYear["quarter"]> = {
  1: "Q1",
  2: "Q1",
  3: "Q1",
  4: "Q2",
  5: "Q2",
  6: "Q2",
  7: "Q3",
  8: "Q3",
  9: "Q3",
  10: "Q4",
  11: "Q4",
  12: "Q4",
};

const QUARTER_NAME_RE = /\b(Q[1-4])[-\s_/]*(20\d{2})\b/i;

export function parseCycleQuarterYear(cycle?: Pick<Cycle, "name" | "start_date"> | null): CycleQuarterYear | null {
  if (!cycle) return null;

  const fromName = cycle.name?.match(QUARTER_NAME_RE);
  if (fromName) {
    return {
      quarter: fromName[1].toUpperCase() as CycleQuarterYear["quarter"],
      year: Number(fromName[2]),
    };
  }

  const start = cycle.start_date ? new Date(cycle.start_date) : null;
  if (start && !Number.isNaN(start.getTime())) {
    const month = start.getUTCMonth() + 1;
    return {
      quarter: QUARTER_BY_MONTH[month] ?? "Q1",
      year: start.getUTCFullYear(),
    };
  }

  return null;
}

import { create } from "zustand";
import type { CycleQuarter } from "@/lib/cycle-utils";
import { currentCalendarQuarter } from "@/lib/cycle-utils";

interface UIState {
  theme: "dark" | "light";
  sidebarCollapsed: boolean;
  selectedCycleId: string | null;
  selectedYear: number;
  selectedQuarter: CycleQuarter;
  toggleTheme: () => void;
  setTheme: (t: "dark" | "light") => void;
  toggleSidebar: () => void;
  setSelectedCycleId: (id: string | null) => void;
  setSelectedPeriod: (year: number, quarter: CycleQuarter, cycleId?: string | null) => void;
}

const defaultYear = new Date().getFullYear();

export const useUIStore = create<UIState>((set) => ({
  theme: "dark",
  sidebarCollapsed: false,
  selectedCycleId: null,
  selectedYear: defaultYear,
  selectedQuarter: currentCalendarQuarter(),
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      if (typeof document !== "undefined") {
        document.documentElement.classList.toggle("dark", next === "dark");
      }
      return { theme: next };
    }),
  setTheme: (t) => {
    if (typeof document !== "undefined") {
      document.documentElement.classList.toggle("dark", t === "dark");
    }
    set({ theme: t });
  },
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSelectedCycleId: (id) => set({ selectedCycleId: id }),
  setSelectedPeriod: (year, quarter, cycleId) =>
    set({
      selectedYear: year,
      selectedQuarter: quarter,
      selectedCycleId: cycleId ?? null,
    }),
}));

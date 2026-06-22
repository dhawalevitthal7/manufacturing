import { useUIStore } from "@/lib/stores/ui-store";

/** Global year/quarter filter from the top bar — drives OKR and progress queries. */
export function usePeriodFilter() {
  const selectedYear = useUIStore((s) => s.selectedYear);
  const selectedQuarter = useUIStore((s) => s.selectedQuarter);
  const selectedCycleId = useUIStore((s) => s.selectedCycleId);

  return {
    year: selectedYear,
    quarter: selectedQuarter,
    cycleId: selectedCycleId,
    periodKey: `${selectedYear}-${selectedQuarter}`,
  };
}

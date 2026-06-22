import * as React from "react";

import { useQuery } from "@tanstack/react-query";

import { useRouterState } from "@tanstack/react-router";

import { Bell, Moon, Search, Sun, LogOut, Calendar } from "lucide-react";

import { api } from "@/lib/api";

import { useAuthStore } from "@/lib/stores/auth-store";

import { useUIStore } from "@/lib/stores/ui-store";

import {

  ALL_QUARTERS,

  getSelectableYears,

  parseCycleQuarterYear,

  type CycleQuarter,

} from "@/lib/cycle-utils";

import {

  DropdownMenu,

  DropdownMenuContent,

  DropdownMenuItem,

  DropdownMenuSeparator,

  DropdownMenuTrigger,

} from "@/components/ui/dropdown-menu";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import {

  Select,

  SelectContent,

  SelectItem,

  SelectTrigger,

  SelectValue,

} from "@/components/ui/select";



const titles: Record<string, string> = {

  "/": "Operations Command Center",

  "/alignment": "Strategic Alignment",

  "/okrs": "Objectives & Key Results",

  "/progress": "Progress Tracking",

  "/reviews": "Performance Reviews",

  "/approvals": "Approval Queue",

  "/blockers": "Blockers",

  "/employees": "Employees",

  "/teams": "Teams",

  "/hierarchy": "Organizational Hierarchy",

  "/settings": "Settings",

  "/audit-logs": "Audit Logs",

};



export function Topbar() {

  const path = useRouterState({ select: (r) => r.location.pathname });

  const user = useAuthStore((s) => s.user);

  const logout = useAuthStore((s) => s.logout);

  const {

    theme,

    toggleTheme,

    selectedYear,

    selectedQuarter,

    setSelectedPeriod,

  } = useUIStore();

  const title = titles[path] ?? "Workspace";



  const { data: cycles } = useQuery({

    queryKey: ["cycles"],

    queryFn: () => api.getCycles(),

  });



  const cyclesWithQuarterYear = React.useMemo(() => {

    return (cycles ?? [])

      .map((cycle) => ({ cycle, quarterYear: parseCycleQuarterYear(cycle) }))

      .filter(

        (

          entry,

        ): entry is {

          cycle: (typeof cycles)[number];

          quarterYear: NonNullable<ReturnType<typeof parseCycleQuarterYear>>;

        } => Boolean(entry.quarterYear),

      );

  }, [cycles]);



  const activeCycle = cycles?.find((c) => c.status === "ACTIVE" || c.status === "FROZEN");



  const resolveCycleForQuarter = React.useCallback(

    (year: number, quarter: CycleQuarter) => {

      const candidates = cyclesWithQuarterYear

        .filter(({ quarterYear }) => quarterYear.year === year && quarterYear.quarter === quarter)

        .map(({ cycle }) => cycle);

      if (!candidates.length) return null;



      const priority = new Map([

        ["ACTIVE", 0],

        ["FROZEN", 1],

        ["PLANNED", 2],

        ["CLOSED", 3],

      ]);



      return [...candidates].sort((a, b) => {

        const pA = priority.get(a.status) ?? 99;

        const pB = priority.get(b.status) ?? 99;

        if (pA !== pB) return pA - pB;

        return b.start_date.localeCompare(a.start_date);

      })[0];

    },

    [cyclesWithQuarterYear],

  );



  const periodInitialized = React.useRef(false);

  // Default period from active OKR cycle on first load
  React.useEffect(() => {
    if (periodInitialized.current || !activeCycle) return;
    const qy = parseCycleQuarterYear(activeCycle);
    if (qy) {
      setSelectedPeriod(qy.year, qy.quarter, activeCycle.id);
      periodInitialized.current = true;
    }
  }, [activeCycle, setSelectedPeriod]);



  const applyPeriod = React.useCallback(

    (year: number, quarter: CycleQuarter) => {

      const resolvedCycle = resolveCycleForQuarter(year, quarter);

      setSelectedPeriod(year, quarter, resolvedCycle?.id ?? null);

    },

    [resolveCycleForQuarter, setSelectedPeriod],

  );



  const handleYearChange = (yearValue: string) => {

    applyPeriod(Number(yearValue), selectedQuarter);

  };



  const handleQuarterChange = (quarterValue: string) => {

    applyPeriod(selectedYear, quarterValue as CycleQuarter);

  };



  const userInitials = user?.name

    ?.split(" ")

    .map((n) => n[0])

    .join("")

    .toUpperCase() || "?";



  const availableYears = getSelectableYears();



  return (

    <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/70 bg-background/80 px-6 backdrop-blur-md">

      <div className="min-w-0 flex-1">

        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Workspace</div>

        <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>

      </div>



      <div className="hidden items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1.5 text-sm text-muted-foreground lg:flex">

        <Search className="h-3.5 w-3.5" />

        <span>Search OKRs, employees, plants…</span>

        <kbd className="ml-6 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-mono">⌘K</kbd>

      </div>



      <div className="ml-auto flex items-center gap-2">

        <Select value={String(selectedYear)} onValueChange={handleYearChange}>

          <SelectTrigger className="w-[100px] h-9 border-border bg-card text-xs">

            <Calendar className="mr-2 h-3.5 w-3.5 text-muted-foreground" />

            <SelectValue placeholder="Year" />

          </SelectTrigger>

          <SelectContent align="end">

            {availableYears.map((year) => (

              <SelectItem key={year} value={String(year)}>

                {year}

              </SelectItem>

            ))}

          </SelectContent>

        </Select>



        <Select value={selectedQuarter} onValueChange={handleQuarterChange}>

          <SelectTrigger className="w-[92px] h-9 border-border bg-card text-xs">

            <SelectValue placeholder="Quarter" />

          </SelectTrigger>

          <SelectContent align="end">

            {ALL_QUARTERS.map((quarter) => (

              <SelectItem key={quarter} value={quarter}>

                {quarter}

              </SelectItem>

            ))}

          </SelectContent>

        </Select>

      </div>



      <button

        onClick={toggleTheme}

        className="grid h-9 w-9 place-items-center rounded-md border border-border text-muted-foreground hover:bg-muted hover:text-foreground"

        aria-label="Toggle theme"

      >

        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}

      </button>



      <button className="relative grid h-9 w-9 place-items-center rounded-md border border-border text-muted-foreground hover:bg-muted hover:text-foreground">

        <Bell className="h-4 w-4" />

        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-destructive" />

      </button>



      {user && (

        <DropdownMenu>

          <DropdownMenuTrigger asChild>

            <button className="flex items-center gap-2 rounded-md border border-border p-1 hover:bg-muted">

              <Avatar className="h-8 w-8">

                <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold">

                  {userInitials}

                </AvatarFallback>

              </Avatar>

            </button>

          </DropdownMenuTrigger>

          <DropdownMenuContent align="end">

            <div className="px-2 py-1.5">

              <p className="text-sm font-medium">{user.name}</p>

              <p className="text-xs text-muted-foreground">{user.email}</p>

              <p className="text-xs text-muted-foreground">{user.system_role}</p>

            </div>

            <DropdownMenuSeparator />

            <DropdownMenuItem onClick={() => logout()} className="cursor-pointer">

              <LogOut className="mr-2 h-4 w-4" />

              <span>Sign Out</span>

            </DropdownMenuItem>

          </DropdownMenuContent>

        </DropdownMenu>

      )}

    </header>

  );

}



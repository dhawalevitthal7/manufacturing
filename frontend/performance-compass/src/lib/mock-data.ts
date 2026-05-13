// Mock data for the manufacturing OKR dashboard.
// NOTE: This file is retained for reference only. Production widgets use live API data.
import type { SystemRole } from "@/lib/api";
type Role = "executive" | "plant_head" | "manager" | "operator";

export interface StatCard {
  id: string;
  label: string;
  value: string;
  delta: number;
  trend: "up" | "down" | "flat";
  hint?: string;
}

export const statsByRole: Record<Role, StatCard[]> = {
  executive: [
    { id: "s1", label: "Org OKR Health", value: "78%", delta: 4.2, trend: "up", hint: "vs last quarter" },
    { id: "s2", label: "Strategic Alignment", value: "92%", delta: 1.1, trend: "up", hint: "goals cascaded" },
    { id: "s3", label: "Plants On-Track", value: "6 / 8", delta: -1, trend: "down", hint: "Surat & Vizag at risk" },
    { id: "s4", label: "Review Cycle Coverage", value: "84%", delta: 6.8, trend: "up", hint: "Q2 mid-cycle" },
  ],
  plant_head: [
    { id: "s1", label: "Plant OKR Health", value: "81%", delta: 3.4, trend: "up" },
    { id: "s2", label: "Shift Adherence", value: "94%", delta: 0.6, trend: "up" },
    { id: "s3", label: "Pending Validations", value: "23", delta: -8, trend: "down", hint: "below target" },
    { id: "s4", label: "Open Blockers", value: "7", delta: 2, trend: "up", hint: "needs triage" },
  ],
  manager: [
    { id: "s1", label: "Team OKR Progress", value: "67%", delta: 5.2, trend: "up" },
    { id: "s2", label: "Submissions Today", value: "18", delta: 4, trend: "up" },
    { id: "s3", label: "Awaiting My Review", value: "9", delta: -2, trend: "down" },
    { id: "s4", label: "Escalations", value: "2", delta: 1, trend: "up", hint: "1 critical" },
  ],
  operator: [
    { id: "s1", label: "My OKR Progress", value: "72%", delta: 8, trend: "up" },
    { id: "s2", label: "This Week's Output", value: "1,248", delta: 4.1, trend: "up", hint: "units" },
    { id: "s3", label: "Pending Reviews", value: "1", delta: 0, trend: "flat" },
    { id: "s4", label: "My Blockers", value: "0", delta: -1, trend: "down", hint: "all cleared" },
  ],
};

export interface OKRItem {
  id: string;
  objective: string;
  owner: string;
  scope: string;
  progress: number;
  krs: { title: string; progress: number }[];
  status: "on_track" | "at_risk" | "off_track" | "completed";
}

export const sampleOKRs: OKRItem[] = [
  {
    id: "okr-1",
    objective: "Reduce unplanned downtime across Pune facility",
    owner: "Rohan Iyer",
    scope: "Plant · Pune",
    progress: 72,
    status: "on_track",
    krs: [
      { title: "Lower MTTR to under 38 min", progress: 81 },
      { title: "Predictive maintenance on 14 assets", progress: 64 },
      { title: "Operator alerting SLA <90s", progress: 70 },
    ],
  },
  {
    id: "okr-2",
    objective: "Lift first-pass yield on Line A by 6 pts",
    owner: "Priya Nair",
    scope: "Department · Production",
    progress: 54,
    status: "at_risk",
    krs: [
      { title: "Vision-system rollout to 4 stations", progress: 50 },
      { title: "Reduce torque variance to <2%", progress: 62 },
      { title: "Operator certification 100%", progress: 48 },
    ],
  },
  {
    id: "okr-3",
    objective: "Cut energy intensity per unit by 9%",
    owner: "Anika Mehra",
    scope: "Organization",
    progress: 38,
    status: "off_track",
    krs: [
      { title: "Compressor optimization wave 2", progress: 41 },
      { title: "HVAC scheduling automation", progress: 35 },
    ],
  },
  {
    id: "okr-4",
    objective: "Close out Q1 safety observations",
    owner: "Plant EHS",
    scope: "Plant · Vizag",
    progress: 100,
    status: "completed",
    krs: [{ title: "Resolve all amber findings", progress: 100 }],
  },
];

export const executionTrend = [
  { week: "W1", planned: 65, actual: 58 },
  { week: "W2", planned: 68, actual: 64 },
  { week: "W3", planned: 70, actual: 71 },
  { week: "W4", planned: 72, actual: 69 },
  { week: "W5", planned: 74, actual: 76 },
  { week: "W6", planned: 76, actual: 78 },
  { week: "W7", planned: 78, actual: 81 },
  { week: "W8", planned: 80, actual: 79 },
];

export const departmentComparison = [
  { dept: "Production", onTrack: 62, atRisk: 24, offTrack: 14 },
  { dept: "Quality", onTrack: 78, atRisk: 16, offTrack: 6 },
  { dept: "Maintenance", onTrack: 54, atRisk: 30, offTrack: 16 },
  { dept: "Supply Chain", onTrack: 71, atRisk: 18, offTrack: 11 },
  { dept: "EHS", onTrack: 88, atRisk: 9, offTrack: 3 },
];

export interface QueueItem {
  id: string;
  title: string;
  submittedBy: string;
  scope: string;
  submittedAt: string;
  priority: "low" | "med" | "high";
}

export const reviewQueue: QueueItem[] = [
  { id: "rv-1", title: "Q2 self-review · Operator certification", submittedBy: "Vikram Shah", scope: "Line A", submittedAt: "2h ago", priority: "high" },
  { id: "rv-2", title: "Mid-cycle calibration · Maintenance", submittedBy: "Karan Bhatt", scope: "Pune Plant", submittedAt: "5h ago", priority: "med" },
  { id: "rv-3", title: "Skip-level — Quality leads", submittedBy: "Sana Qureshi", scope: "Org", submittedAt: "1d ago", priority: "med" },
  { id: "rv-4", title: "Yield improvement KR review", submittedBy: "Priya Nair", scope: "Line A", submittedAt: "1d ago", priority: "low" },
];

export const approvalQueue: QueueItem[] = [
  { id: "ap-1", title: "Progress: 78% · Predictive maintenance KR", submittedBy: "Vikram Shah", scope: "Pune", submittedAt: "12m ago", priority: "high" },
  { id: "ap-2", title: "Blocker: Vision station calibration drift", submittedBy: "Aarti Verma", scope: "Line A", submittedAt: "1h ago", priority: "high" },
  { id: "ap-3", title: "Progress: 64% · MTTR initiative", submittedBy: "Karan Bhatt", scope: "Pune", submittedAt: "3h ago", priority: "med" },
  { id: "ap-4", title: "Capex request · Torque sensors", submittedBy: "Priya Nair", scope: "Production", submittedAt: "6h ago", priority: "med" },
  { id: "ap-5", title: "Escalation: Operator certification gap", submittedBy: "Shift B Lead", scope: "Line A", submittedAt: "1d ago", priority: "low" },
];

export const aiInsights = [
  {
    id: "ai-1",
    title: "Maintenance is the leading drag on plant OKRs",
    body: "Cross-plant signals show 30% of at-risk KRs originate from maintenance bottlenecks. Re-prioritizing the predictive maintenance rollout could lift plant health by ~6 pts.",
    confidence: 0.84,
    impact: "High",
  },
  {
    id: "ai-2",
    title: "Yield variance correlates with shift handover gaps",
    body: "Line A first-pass yield drops 2.1 pts on shifts with handover times >9 min. Standardizing handovers is a low-effort lever.",
    confidence: 0.71,
    impact: "Medium",
  },
];

export const alignmentNodes = [
  { id: "org", label: "Reduce cost per unit by 12%", level: 0, progress: 64 },
  { id: "p1", label: "Pune: downtime -25%", level: 1, progress: 72, parent: "org" },
  { id: "p2", label: "Vizag: yield +6 pts", level: 1, progress: 54, parent: "org" },
  { id: "p3", label: "Surat: energy -9%", level: 1, progress: 38, parent: "org" },
  { id: "d1", label: "Predictive maintenance", level: 2, progress: 64, parent: "p1" },
  { id: "d2", label: "Operator alerting SLA", level: 2, progress: 70, parent: "p1" },
  { id: "d3", label: "Vision systems rollout", level: 2, progress: 50, parent: "p2" },
  { id: "d4", label: "HVAC automation", level: 2, progress: 35, parent: "p3" },
];

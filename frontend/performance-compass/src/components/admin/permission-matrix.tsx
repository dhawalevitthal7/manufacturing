import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  api,
  type PermissionCategory,
  type PermissionDefinition,
  type PermissionRuleValues,
  type PermissionRuleUpdate,
} from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Shield,
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Sparkles,
  Lock,
  Eye,
  Plus,
  Pencil,
  Trash2,
  ThumbsUp,
  UserPlus,
  Settings2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  view: Eye,
  create: Plus,
  edit: Pencil,
  delete: Trash2,
  approve: ThumbsUp,
  assign: UserPlus,
  manage: Settings2,
};

const ACTION_LABELS: Record<string, string> = {
  view: "View",
  create: "Create",
  edit: "Edit",
  delete: "Delete",
  approve: "Approve",
  assign: "Assign",
  manage: "Manage",
};

const SCOPE_COLORS: Record<string, string> = {
  ORGANIZATION: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
  PLANT: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
  DEPARTMENT: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  TEAM: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  DIRECT_REPORTS: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  SUBTREE: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  SELF: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

const emptyRule = (): PermissionRuleValues => ({
  can_view: false, can_create: false, can_edit: false,
  can_delete: false, can_approve: false, can_assign: false,
  can_manage: false, hierarchy_scope: "SELF",
});

export function PermissionMatrix() {
  const { permissions } = useAuthStore();
  const queryClient = useQueryClient();

  const [selectedRole, setSelectedRole] = useState("EMPLOYEE");
  const [dirty, setDirty] = useState(false);
  const [localRules, setLocalRules] = useState<Record<string, PermissionRuleValues>>({});
  const [collapsedCats, setCollapsedCats] = useState<Set<string>>(new Set());
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Fetch registry (static catalog)
  const { data: registry, isLoading: regLoading } = useQuery({
    queryKey: ["perm-registry"],
    queryFn: () => api.getPermissionRegistry(),
  });

  // Fetch saved rules for selected role
  const { data: savedRules, isLoading: rulesLoading } = useQuery({
    queryKey: ["perm-rules", selectedRole],
    queryFn: () => api.getRoleRules(selectedRole),
    enabled: !!selectedRole,
  });

  // Sync saved rules to local state
  useEffect(() => {
    if (savedRules) {
      setLocalRules(savedRules);
      setDirty(false);
    }
  }, [savedRules]);

  // Mutations
  const saveMutation = useMutation({
    mutationFn: (rules: PermissionRuleUpdate[]) =>
      api.bulkUpdatePermissionRules(selectedRole, rules),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["perm-rules", selectedRole] });
      setSuccessMsg(`Saved ${data.upserted} permission rules for ${selectedRole}`);
      setDirty(false);
      setTimeout(() => setSuccessMsg(""), 4000);
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save");
      setTimeout(() => setErrorMsg(""), 4000);
    },
  });

  const seedMutation = useMutation({
    mutationFn: () => api.seedDefaultPermissionMatrix(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["perm-rules"] });
      setSuccessMsg(`Seeded ${data.seeded} default rules for all roles`);
      setTimeout(() => setSuccessMsg(""), 4000);
    },
  });

  // Permission grouping
  const categories = useMemo(
    () => (registry?.categories || []).sort((a, b) => a.order - b.order),
    [registry]
  );
  const permsByCategory = useMemo(() => {
    const map: Record<string, PermissionDefinition[]> = {};
    for (const p of registry?.permissions || []) {
      if (!map[p.category]) map[p.category] = [];
      map[p.category].push(p);
    }
    return map;
  }, [registry]);

  const toggleAction = useCallback(
    (permKey: string, action: string) => {
      setLocalRules((prev) => {
        const rule = prev[permKey] || emptyRule();
        const key = `can_${action}` as keyof PermissionRuleValues;
        return {
          ...prev,
          [permKey]: { ...rule, [key]: !rule[key] },
        };
      });
      setDirty(true);
    },
    []
  );

  const setScope = useCallback((permKey: string, scope: string) => {
    setLocalRules((prev) => {
      const rule = prev[permKey] || emptyRule();
      return { ...prev, [permKey]: { ...rule, hierarchy_scope: scope } };
    });
    setDirty(true);
  }, []);

  const toggleCategoryCollapse = (catKey: string) => {
    setCollapsedCats((prev) => {
      const next = new Set(prev);
      if (next.has(catKey)) next.delete(catKey);
      else next.add(catKey);
      return next;
    });
  };

  const handleSave = () => {
    const rules: PermissionRuleUpdate[] = [];
    for (const perm of registry?.permissions || []) {
      const rule = localRules[perm.key] || emptyRule();
      rules.push({
        permission_key: perm.key,
        can_view: !!rule.can_view,
        can_create: !!rule.can_create,
        can_edit: !!rule.can_edit,
        can_delete: !!rule.can_delete,
        can_approve: !!rule.can_approve,
        can_assign: !!rule.can_assign,
        can_manage: !!rule.can_manage,
        hierarchy_scope: rule.hierarchy_scope || "SELF",
      });
    }
    saveMutation.mutate(rules);
  };

  const handleGrantAll = (catKey: string) => {
    const perms = permsByCategory[catKey] || [];
    setLocalRules((prev) => {
      const next = { ...prev };
      for (const p of perms) {
        const rule = next[p.key] || emptyRule();
        const updated = { ...rule };
        for (const a of p.actions) {
          (updated as any)[`can_${a}`] = true;
        }
        next[p.key] = updated;
      }
      return next;
    });
    setDirty(true);
  };

  const handleRevokeAll = (catKey: string) => {
    const perms = permsByCategory[catKey] || [];
    setLocalRules((prev) => {
      const next = { ...prev };
      for (const p of perms) {
        next[p.key] = emptyRule();
      }
      return next;
    });
    setDirty(true);
  };

  const isLoading = regLoading || rulesLoading;

  // Count enabled permissions per category
  const catCounts = useMemo(() => {
    const counts: Record<string, { enabled: number; total: number }> = {};
    for (const cat of categories) {
      const perms = permsByCategory[cat.key] || [];
      let enabled = 0;
      for (const p of perms) {
        const rule = localRules[p.key];
        if (rule) {
          const hasAny = p.actions.some((a) => (rule as any)[`can_${a}`]);
          if (hasAny) enabled++;
        }
      }
      counts[cat.key] = { enabled, total: perms.length };
    }
    return counts;
  }, [categories, permsByCategory, localRules]);

  // Access guard — MUST be after all hooks
  if (permissions?.system_role !== "SUPER_ADMIN") {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 p-12 text-center">
        <Lock className="mb-3 h-10 w-10 text-destructive/60" />
        <h3 className="text-lg font-semibold">Access Denied</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Only administrators can access the Permission Matrix.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg gradient-primary glow-primary">
              <Shield className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Permission Matrix</h1>
              <p className="text-sm text-muted-foreground">
                Enterprise RBAC configuration · {registry?.permissions?.length || 0} permissions · {registry?.system_roles?.length || 0} roles
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => seedMutation.mutate()} disabled={seedMutation.isPending}>
            {seedMutation.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-2 h-3.5 w-3.5" />}
            Seed Defaults
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!dirty || saveMutation.isPending}
            className={cn(dirty && "ring-2 ring-primary ring-offset-2 ring-offset-background")}>
            {saveMutation.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-2 h-3.5 w-3.5" />}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Status Messages */}
      <AnimatePresence>
        {successMsg && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />{successMsg}
          </motion.div>
        )}
        {errorMsg && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />{errorMsg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Role Selector */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-[220px]">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Configure Role</label>
            <Select value={selectedRole} onValueChange={(v) => { setSelectedRole(v); setDirty(false); }}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {(registry?.system_roles || []).map((r) => (
                  <SelectItem key={r} value={r}>{r.replace(/_/g, " ")}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Default Scope</label>
            <Badge variant="outline" className={cn("text-xs", SCOPE_COLORS[
              localRules[Object.keys(localRules)[0]]?.hierarchy_scope || "SELF"
            ] || SCOPE_COLORS.SELF)}>
              {selectedRole === "SUPER_ADMIN" ? "ORGANIZATION" :
               selectedRole === "CEO" ? "ORGANIZATION" :
               selectedRole === "PLANT_HEAD" ? "PLANT" :
               selectedRole === "DEPT_HEAD" ? "DEPARTMENT" :
               selectedRole === "MANAGER" ? "TEAM" : "SELF"}
            </Badge>
          </div>
          {dirty && (
            <Badge variant="destructive" className="animate-pulse">Unsaved Changes</Badge>
          )}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Permission Grid */}
      {!isLoading && (
        <div className="space-y-3">
          {categories.map((cat) => {
            const perms = permsByCategory[cat.key] || [];
            if (perms.length === 0) return null;
            const collapsed = collapsedCats.has(cat.key);
            const counts = catCounts[cat.key] || { enabled: 0, total: 0 };

            return (
              <div key={cat.key} className="rounded-xl border border-border bg-card overflow-hidden">
                {/* Category Header */}
                <div
                  className="flex cursor-pointer items-center justify-between border-b border-border px-5 py-3 hover:bg-muted/30 transition-colors"
                  onClick={() => toggleCategoryCollapse(cat.key)}
                >
                  <div className="flex items-center gap-3">
                    {collapsed ? <ChevronRight className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    <h3 className="text-sm font-semibold">{cat.label}</h3>
                    <Badge variant="secondary" className="text-[10px]">
                      {counts.enabled}/{counts.total}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="sm" className="h-7 text-xs text-emerald-400 hover:text-emerald-300"
                      onClick={() => handleGrantAll(cat.key)}>
                      Grant All
                    </Button>
                    <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive hover:text-destructive/80"
                      onClick={() => handleRevokeAll(cat.key)}>
                      Revoke All
                    </Button>
                  </div>
                </div>

                {/* Permission Rows */}
                <AnimatePresence>
                  {!collapsed && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
                      {/* Column Headers */}
                      <div className="grid grid-cols-[1fr_repeat(7,48px)_140px] items-center gap-1 border-b border-border/50 bg-muted/20 px-5 py-2">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Permission</div>
                        {["view", "create", "edit", "delete", "approve", "assign", "manage"].map((a) => {
                          const Icon = ACTION_ICONS[a] || Eye;
                          return (
                            <div key={a} className="flex flex-col items-center gap-0.5" title={ACTION_LABELS[a]}>
                              <Icon className="h-3 w-3 text-muted-foreground" />
                              <span className="text-[8px] font-medium uppercase tracking-wider text-muted-foreground">{a.slice(0, 3)}</span>
                            </div>
                          );
                        })}
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground text-center">Scope</div>
                      </div>

                      {perms.map((perm, idx) => {
                        const rule = localRules[perm.key] || emptyRule();
                        return (
                          <div key={perm.key}
                            className={cn(
                              "grid grid-cols-[1fr_repeat(7,48px)_140px] items-center gap-1 px-5 py-2.5 transition-colors hover:bg-muted/20",
                              idx < perms.length - 1 && "border-b border-border/30"
                            )}>
                            <div className="min-w-0">
                              <div className="truncate text-sm">{perm.label}</div>
                            </div>
                            {["view", "create", "edit", "delete", "approve", "assign", "manage"].map((action) => {
                              const isApplicable = perm.actions.includes(action);
                              const key = `can_${action}` as keyof PermissionRuleValues;
                              const checked = !!rule[key];
                              return (
                                <div key={action} className="flex items-center justify-center">
                                  {isApplicable ? (
                                    <Checkbox
                                      checked={checked}
                                      onCheckedChange={() => toggleAction(perm.key, action)}
                                      className={cn(
                                        "h-4 w-4 transition-all",
                                        checked && "data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                                      )}
                                    />
                                  ) : (
                                    <span className="h-4 w-4 rounded border border-border/20 bg-muted/30" title="N/A" />
                                  )}
                                </div>
                              );
                            })}
                            <div className="flex justify-center">
                              <Select value={rule.hierarchy_scope || "SELF"} onValueChange={(v) => setScope(perm.key, v)}>
                                <SelectTrigger className="h-7 w-full text-[10px] border-border/50">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {(registry?.hierarchy_scopes || []).map((s) => (
                                    <SelectItem key={s.key} value={s.key} className="text-xs">{s.label}</SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      )}

      {/* Sticky Save Bar */}
      {dirty && (
        <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          className="sticky bottom-4 z-10 flex items-center justify-between rounded-xl border border-primary/30 bg-card/95 px-5 py-3 shadow-lg backdrop-blur-md">
          <span className="text-sm font-medium">
            Unsaved changes for <strong>{selectedRole.replace(/_/g, " ")}</strong>
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => { setLocalRules(savedRules || {}); setDirty(false); }}>
              <RotateCcw className="mr-2 h-3.5 w-3.5" />Discard
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-2 h-3.5 w-3.5" />}
              Save All
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  );
}

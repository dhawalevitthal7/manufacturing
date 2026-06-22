import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, CheckCircle2, Lock, Snowflake, Play, Plus, Loader2 } from "lucide-react";
import { api, CycleCreate, Cycle } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

export function CyclesAdmin() {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  
  // Form state
  const [name, setName] = useState("");
  const [cycleType, setCycleType] = useState<any>("QUARTERLY");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [freezeDate, setFreezeDate] = useState("");

  const { data: cycles = [], isLoading: cyclesLoading } = useQuery({
    queryKey: ["cycles"],
    queryFn: () => api.getCycles(),
  });

  const handleCreateCycle = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.createCycle({
        name,
        cycle_type: cycleType,
        start_date: startDate,
        end_date: endDate,
        freeze_date: freezeDate,
      });
      setName(""); setStartDate(""); setEndDate(""); setFreezeDate("");
      queryClient.invalidateQueries({ queryKey: ["cycles"] });
    } catch (err) {
      console.error(err);
      alert("Failed to create cycle.");
    } finally {
      setLoading(false);
    }
  };

  const handleFreeze = async (id: string) => {
    if (!confirm("Freeze this cycle? No more progress updates will be allowed.")) return;
    try {
      await api.freezeCycle(id);
      queryClient.invalidateQueries({ queryKey: ["cycles"] });
    } catch (err) {
      console.error(err);
    }
  };

  const handleClose = async (id: string) => {
    if (!confirm("Close this cycle? This is permanent.")) return;
    try {
      await api.closeCycle(id);
      queryClient.invalidateQueries({ queryKey: ["cycles"] });
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleCreateCycle} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium">Cycle Name</label>
            <Input placeholder="e.g. Q1 2026" value={name} onChange={e => setName(e.target.value)} required className="mt-1 text-xs h-8" />
          </div>
          <div>
            <label className="text-xs font-medium">Type</label>
            <Select value={cycleType} onValueChange={setCycleType}>
              <SelectTrigger className="mt-1 h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ANNUAL">Annual</SelectItem>
                <SelectItem value="HALF_YEARLY">Half Yearly</SelectItem>
                <SelectItem value="QUARTERLY">Quarterly</SelectItem>
                <SelectItem value="MONTHLY">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium">Start Date</label>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} required className="mt-1 text-xs h-8" />
          </div>
          <div>
            <label className="text-xs font-medium">End Date</label>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} required className="mt-1 text-xs h-8" />
          </div>
          <div>
            <label className="text-xs font-medium">Freeze Date</label>
            <Input type="date" value={freezeDate} onChange={e => setFreezeDate(e.target.value)} required className="mt-1 text-xs h-8" />
          </div>
        </div>
        <Button type="submit" disabled={loading} size="sm" className="w-full">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          Create Cycle
        </Button>
      </form>

      <div className="space-y-2 mt-4">
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Existing Cycles</h4>
        {cyclesLoading ? (
          <div className="text-xs text-muted-foreground py-4 text-center">Loading cycles...</div>
        ) : cycles.length === 0 ? (
          <div className="text-xs text-muted-foreground py-4 text-center border rounded-md border-dashed">No cycles found</div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
            {cycles.map((c) => (
              <div key={c.id} className="flex items-center justify-between p-2 rounded-md border border-border bg-card">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{c.name}</span>
                    <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">{c.status}</Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">
                    {c.start_date} to {c.end_date} (Freeze: {c.freeze_date})
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {c.status === "ACTIVE" && (
                    <Button size="sm" variant="outline" className="h-6 text-[10px] px-2 text-blue-500" onClick={() => handleFreeze(c.id)}>
                      <Snowflake className="h-3 w-3 mr-1" /> Freeze
                    </Button>
                  )}
                  {(c.status === "ACTIVE" || c.status === "FROZEN") && (
                    <Button size="sm" variant="outline" className="h-6 text-[10px] px-2 text-rose-500" onClick={() => handleClose(c.id)}>
                      <Lock className="h-3 w-3 mr-1" /> Close
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

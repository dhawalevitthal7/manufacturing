import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertCircle,
  UserPlus,
  Loader2,
  CheckCircle2,
  Trash2,
  Crown,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface TeamMember {
  id: string;
  name: string;
  email: string;
  employee_id?: string;
  team_member_id: string;
  is_team_lead: boolean;
  role_in_team: string;
  joined_at?: string;
}

interface Props {
  teamId: string;
  members: TeamMember[];
  /** When set, "Add member" loads employees assigned to this plant (recommended). */
  plantId?: string | null;
  onMembersChange?: () => void;
}

export function TeamMemberManager({ teamId, members, plantId, onMembersChange }: Props) {
  const queryClient = useQueryClient();
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [isTeamLead, setIsTeamLead] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [employees, setEmployees] = useState<any[]>([]);

  const handleOpenAddDialog = async () => {
    try {
      const response = plantId
        ? await api.getEmployees({ plant_id: plantId, is_active: true })
        : await api.getEmployees({ team_id: teamId });
      setEmployees(response);
    } catch (e) {
      setError("Failed to load employees");
    }
    setAddDialogOpen(true);
  };

  const handleAddMember = async () => {
    if (!selectedEmployee) {
      setError("Please select an employee");
      return;
    }

    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      await api.addTeamMember(teamId, {
        user_id: selectedEmployee,
        is_team_lead: isTeamLead,
      });
      setSuccess("Member added successfully!");
      setSelectedEmployee("");
      setIsTeamLead(false);
      setAddDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["team", teamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      onMembersChange?.();
    } catch (e: any) {
      setError(e.message || "Failed to add member");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    if (!confirm("Remove this member from the team?")) return;

    try {
      await api.removeTeamMember(teamId, memberId);
      setSuccess("Member removed successfully!");
      queryClient.invalidateQueries({ queryKey: ["team", teamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      onMembersChange?.();
    } catch (e: any) {
      setError(e.message || "Failed to remove member");
    }
  };

  const handleToggleTeamLead = async (
    memberId: string,
    userId: string,
    currentStatus: boolean
  ) => {
    try {
      await api.updateTeamLeadStatus(teamId, userId, !currentStatus);
      setSuccess(
        `Team lead status updated!`
      );
      queryClient.invalidateQueries({ queryKey: ["team", teamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      onMembersChange?.();
    } catch (e: any) {
      setError(e.message || "Failed to update team lead status");
    }
  };

  const availableEmployees = employees.filter(
    (emp) => !members.find((m) => m.id === emp.id)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Team Members ({members.length})</h3>
        <Button
          size="sm"
          onClick={handleOpenAddDialog}
          className="h-7 text-xs"
        >
          <UserPlus className="h-3 w-3 mr-1" />
          Add Member
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="text-xs">
          <AlertCircle className="h-3 w-3" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 text-xs">
          <CheckCircle2 className="h-3 w-3" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {members.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground text-xs">
            No members added yet. Add your first team member!
          </div>
        ) : (
          members.map((member) => (
            <div
              key={member.id}
              className="flex items-center justify-between p-2 rounded border border-border/50 hover:bg-accent/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <div className="font-medium text-xs truncate">
                    {member.name}
                  </div>
                  {member.is_team_lead && (
                    <Crown className="h-3 w-3 text-amber-500 flex-shrink-0" />
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {member.email}
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                  onClick={() =>
                    handleToggleTeamLead(
                      member.team_member_id,
                      member.id,
                      member.is_team_lead
                    )
                  }
                  title={
                    member.is_team_lead
                      ? "Remove as team lead"
                      : "Make team lead"
                  }
                >
                  <Crown className={`h-3 w-3 ${member.is_team_lead ? "text-amber-500 fill-amber-500" : "text-muted-foreground"}`} />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                  onClick={() => handleRemoveMember(member.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-base">Add Team Member</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label className="text-xs font-medium">Select Employee</Label>
              <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Choose an employee..." />
                </SelectTrigger>
                <SelectContent>
                  {availableEmployees.map((emp) => (
                    <SelectItem key={emp.id} value={emp.id}>
                      {emp.name} ({emp.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="isLead"
                checked={isTeamLead}
                onCheckedChange={(checked) => setIsTeamLead(checked as boolean)}
              />
              <Label htmlFor="isLead" className="text-xs cursor-pointer">
                Make this person a team lead
              </Label>
            </div>

            {error && (
              <Alert variant="destructive" className="text-xs">
                <AlertCircle className="h-3 w-3" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleAddMember}
              disabled={!selectedEmployee || isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <UserPlus className="h-3 w-3 mr-1" />
              )}
              Add Member
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

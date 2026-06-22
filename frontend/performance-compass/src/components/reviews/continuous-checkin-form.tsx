import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  TrendingUp,
  AlertTriangle,
  MessageCircle,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, type ContinuousCheckinSubmit, type EmployeeMood } from "@/lib/api";

interface ContinuousCheckinFormProps {
  employeeId: string;
  onSuccess?: () => void;
}

const moodOptions: Array<{ value: EmployeeMood; label: string; color: string }> = [
  { value: "VERY_POSITIVE", label: "Very Positive", color: "bg-green-100 text-green-800" },
  { value: "POSITIVE", label: "Positive", color: "bg-emerald-100 text-emerald-800" },
  { value: "NEUTRAL", label: "Neutral", color: "bg-slate-100 text-slate-800" },
  { value: "CONCERNING", label: "Concerning", color: "bg-yellow-100 text-yellow-800" },
  { value: "CRITICAL", label: "Critical", color: "bg-red-100 text-red-800" },
];

export function ContinuousCheckinForm({ employeeId, onSuccess }: ContinuousCheckinFormProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Partial<ContinuousCheckinSubmit>>({
    confidence_score: 75,
    engagement_score: 7,
    employee_mood: "POSITIVE",
    achievements: "",
    blockers: "",
  });
  const [keyWins, setKeyWins] = useState<string[]>([]);
  const [newKeyWin, setNewKeyWin] = useState("");

  const { data: employeeProfile } = useQuery({
    queryKey: ["employee-profile", employeeId],
    queryFn: () => api.getEmployee(employeeId),
    enabled: !!employeeId,
  });

  const reportingLinks = employeeProfile?.reporting_to as
    | Array<{ type?: string; manager_name?: string }>
    | undefined;
  const managerName =
    reportingLinks?.find((r) => r.type === "DIRECT")?.manager_name ||
    reportingLinks?.[0]?.manager_name;

  const submitMutation = useMutation({
    mutationFn: () =>
      api.submitCheckin(employeeId, {
        ...formData,
        key_wins: keyWins,
        checkin_week: Math.ceil(
          (new Date().getDate() - new Date().getDay() + 1) / 7
        ),
      } as ContinuousCheckinSubmit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkins"] });
      queryClient.invalidateQueries({ queryKey: ["employee-checkins"] });
      setFormData({
        confidence_score: 75,
        engagement_score: 7,
        employee_mood: "POSITIVE",
        achievements: "",
        blockers: "",
      });
      setKeyWins([]);
      onSuccess?.();
    },
  });

  const handleAddKeyWin = () => {
    if (newKeyWin.trim()) {
      setKeyWins([...keyWins, newKeyWin]);
      setNewKeyWin("");
    }
  };

  const handleRemoveKeyWin = (index: number) => {
    setKeyWins(keyWins.filter((_, i) => i !== index));
  };

  const selectedMood = moodOptions.find((m) => m.value === formData.employee_mood);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Weekly Check-In</CardTitle>
          <CardDescription>
            Share your progress, challenges, and mood for this week
            {managerName ? ` · Manager: ${managerName}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Mood Selection */}
          <div className="space-y-3">
            <label className="text-sm font-semibold">How are you feeling this week?</label>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {moodOptions.map((mood) => (
                <button
                  key={mood.value}
                  onClick={() => setFormData({ ...formData, employee_mood: mood.value })}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    formData.employee_mood === mood.value
                      ? `border-current bg-current/10 ${mood.color}`
                      : "border-border hover:border-current"
                  }`}
                >
                  <div className="text-xs font-medium">{mood.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Confidence & Engagement */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Confidence Score ({formData.confidence_score}%)
              </label>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={formData.confidence_score || 75}
                onChange={(e) =>
                  setFormData({ ...formData, confidence_score: parseInt(e.target.value) })
                }
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">How confident are you about your progress?</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <MessageCircle className="h-4 w-4" />
                Engagement Score ({formData.engagement_score}/10)
              </label>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={formData.engagement_score || 7}
                onChange={(e) =>
                  setFormData({ ...formData, engagement_score: parseInt(e.target.value) })
                }
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">How engaged are you with your work?</p>
            </div>
          </div>

          {/* Achievements */}
          <div className="space-y-2">
            <label className="text-sm font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Achievements this week
            </label>
            <Textarea
              placeholder="What did you accomplish? What are you proud of?"
              value={formData.achievements || ""}
              onChange={(e) => setFormData({ ...formData, achievements: e.target.value })}
              className="min-h-24"
            />
          </div>

          {/* Key Wins */}
          <div className="space-y-2">
            <label className="text-sm font-semibold">Key Wins</label>
            <div className="flex gap-2">
              <Input
                placeholder="Add a key achievement..."
                value={newKeyWin}
                onChange={(e) => setNewKeyWin(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleAddKeyWin()}
              />
              <Button type="button" variant="outline" onClick={handleAddKeyWin}>
                Add
              </Button>
            </div>
            {keyWins.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {keyWins.map((win, index) => (
                  <Badge
                    key={index}
                    variant="secondary"
                    className="cursor-pointer"
                    onClick={() => handleRemoveKeyWin(index)}
                  >
                    {win} ✕
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Blockers */}
          <div className="space-y-2">
            <label className="text-sm font-semibold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Blockers & challenges
            </label>
            <Textarea
              placeholder="What obstacles did you face? What's slowing you down?"
              value={formData.blockers || ""}
              onChange={(e) => setFormData({ ...formData, blockers: e.target.value })}
              className="min-h-24"
            />
          </div>

          {/* Support Needed */}
          <div className="space-y-2">
            <label className="text-sm font-semibold flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-blue-600" />
              Support or resources needed
            </label>
            <Textarea
              placeholder="What help do you need? What would unblock you?"
              value={formData.support_needed || ""}
              onChange={(e) => setFormData({ ...formData, support_needed: e.target.value })}
              className="min-h-20"
            />
          </div>

          {/* Submit Button */}
          <div className="flex justify-between items-center pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              Week {Math.ceil((new Date().getDate() - new Date().getDay() + 1) / 7)}
            </p>
            <Button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending || !formData.achievements || !formData.blockers}
              className="gap-2"
            >
              {submitMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  Submit Check-In
                </>
              )}
            </Button>
          </div>

          {submitMutation.isError && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-red-900">Failed to submit check-in</p>
                <p className="text-sm text-red-700">
                  {submitMutation.error instanceof Error
                    ? submitMutation.error.message
                    : "An error occurred"}
                </p>
              </div>
            </div>
          )}

          {submitMutation.isSuccess && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-green-900">Check-in submitted!</p>
                <p className="text-sm text-green-700">Your manager will review it soon.</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

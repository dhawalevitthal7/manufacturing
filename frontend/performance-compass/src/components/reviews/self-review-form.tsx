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
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Plus,
  X,
  Zap,
  Target,
} from "lucide-react";
import { api, type SelfReviewSubmitEnhanced, type OKRAssessment } from "@/lib/api";

interface SelfReviewFormProps {
  reviewId: string;
  onSuccess?: () => void;
  okrs?: Array<{ id: string; title: string }>;
}

export function SelfReviewForm({ reviewId, onSuccess, okrs = [] }: SelfReviewFormProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Partial<SelfReviewSubmitEnhanced>>({
    achievements: "",
    strengths: "",
    challenges: "",
    evidence: "",
    major_wins: [],
    growth_areas: [],
    okr_self_assessment: [],
  });
  const [newWin, setNewWin] = useState("");
  const [newGrowthArea, setNewGrowthArea] = useState("");

  const submitMutation = useMutation({
    mutationFn: () => api.submitSelfReviewEnhanced(reviewId, formData as SelfReviewSubmitEnhanced),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
      onSuccess?.();
    },
  });

  const handleAddWin = () => {
    if (newWin.trim()) {
      setFormData({
        ...formData,
        major_wins: [...(formData.major_wins || []), newWin],
      });
      setNewWin("");
    }
  };

  const handleRemoveWin = (index: number) => {
    setFormData({
      ...formData,
      major_wins: formData.major_wins?.filter((_, i) => i !== index),
    });
  };

  const handleAddGrowthArea = () => {
    if (newGrowthArea.trim()) {
      setFormData({
        ...formData,
        growth_areas: [...(formData.growth_areas || []), newGrowthArea],
      });
      setNewGrowthArea("");
    }
  };

  const handleRemoveGrowthArea = (index: number) => {
    setFormData({
      ...formData,
      growth_areas: formData.growth_areas?.filter((_, i) => i !== index),
    });
  };

  const handleOKRAssessmentChange = (okrId: string, field: string, value: any) => {
    const assessment = formData.okr_self_assessment?.find((a) => a.okr_id === okrId) || {
      okr_id: okrId,
      title: okrs.find((o) => o.id === okrId)?.title || "",
    };
    const updatedAssessment = { ...assessment, [field]: value };
    setFormData({
      ...formData,
      okr_self_assessment: [
        ...(formData.okr_self_assessment?.filter((a) => a.okr_id !== okrId) || []),
        updatedAssessment,
      ],
    });
  };

  const isValid =
    formData.achievements?.trim() &&
    formData.strengths?.trim() &&
    formData.challenges?.trim();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5" />
          Self-Assessment Review
        </CardTitle>
        <CardDescription>
          Share your perspective on your performance, achievements, and growth areas
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Achievements */}
        <div className="space-y-2">
          <label className="text-sm font-semibold flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            Your Achievements
          </label>
          <Textarea
            placeholder="Describe your key accomplishments, projects completed, and contributions to team/org goals..."
            value={formData.achievements || ""}
            onChange={(e) => setFormData({ ...formData, achievements: e.target.value })}
            className="min-h-24"
          />
        </div>

        {/* Major Wins */}
        <div className="space-y-2">
          <label className="text-sm font-semibold flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-600" />
            Major Wins
          </label>
          <div className="flex gap-2">
            <Input
              placeholder="Add a major win..."
              value={newWin}
              onChange={(e) => setNewWin(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleAddWin()}
            />
            <Button type="button" variant="outline" onClick={handleAddWin}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          {formData.major_wins && formData.major_wins.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.major_wins.map((win, index) => (
                <Badge key={index} variant="secondary" className="gap-1">
                  {win}
                  <button
                    onClick={() => handleRemoveWin(index)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Strengths */}
        <div className="space-y-2">
          <label className="text-sm font-semibold">Your Strengths</label>
          <Textarea
            placeholder="What are your key strengths? What do you do well? What are you known for?"
            value={formData.strengths || ""}
            onChange={(e) => setFormData({ ...formData, strengths: e.target.value })}
            className="min-h-20"
          />
        </div>

        {/* Challenges */}
        <div className="space-y-2">
          <label className="text-sm font-semibold">Challenges & Obstacles</label>
          <Textarea
            placeholder="What challenges did you face? What was difficult? What barriers did you encounter?"
            value={formData.challenges || ""}
            onChange={(e) => setFormData({ ...formData, challenges: e.target.value })}
            className="min-h-20"
          />
        </div>

        {/* Growth Areas */}
        <div className="space-y-2">
          <label className="text-sm font-semibold flex items-center gap-2">
            <Target className="h-4 w-4 text-blue-600" />
            Growth Areas & Development
          </label>
          <div className="flex gap-2">
            <Input
              placeholder="Add a growth area..."
              value={newGrowthArea}
              onChange={(e) => setNewGrowthArea(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleAddGrowthArea()}
            />
            <Button type="button" variant="outline" onClick={handleAddGrowthArea}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          {formData.growth_areas && formData.growth_areas.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.growth_areas.map((area, index) => (
                <Badge key={index} variant="outline" className="gap-1">
                  {area}
                  <button
                    onClick={() => handleRemoveGrowthArea(index)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* OKR Assessments */}
        {okrs.length > 0 && (
          <div className="space-y-3 p-4 bg-slate-50 rounded-lg border">
            <label className="text-sm font-semibold">OKR Self-Assessments</label>
            {okrs.map((okr) => {
              const assessment = formData.okr_self_assessment?.find((a) => a.okr_id === okr.id);
              return (
                <div key={okr.id} className="space-y-2 p-3 bg-white rounded border">
                  <p className="text-sm font-medium">{okr.title}</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Completion %</label>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={assessment?.self_assessed_completion || 0}
                        onChange={(e) =>
                          handleOKRAssessmentChange(okr.id, "self_assessed_completion", parseInt(e.target.value))
                        }
                        className="w-full px-2 py-1 text-sm border rounded"
                      />
                    </div>
                  </div>
                  <Textarea
                    placeholder="How would you rate the quality of your execution on this OKR?"
                    value={assessment?.quality_assessment || ""}
                    onChange={(e) =>
                      handleOKRAssessmentChange(okr.id, "quality_assessment", e.target.value)
                    }
                    className="min-h-16 text-sm"
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Evidence */}
        <div className="space-y-2">
          <label className="text-sm font-semibold">Supporting Evidence</label>
          <Textarea
            placeholder="Provide specific examples, metrics, or evidence that supports your self-assessment..."
            value={formData.evidence || ""}
            onChange={(e) => setFormData({ ...formData, evidence: e.target.value })}
            className="min-h-20"
          />
        </div>

        {/* Submit Button */}
        <div className="flex justify-between items-center pt-4 border-t">
          <p className="text-xs text-muted-foreground">All fields are required before submission</p>
          <Button
            onClick={() => submitMutation.mutate()}
            disabled={submitMutation.isPending || !isValid}
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
                Submit Self-Review
              </>
            )}
          </Button>
        </div>

        {submitMutation.isError && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-900">Failed to submit review</p>
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
              <p className="font-semibold text-green-900">Self-review submitted!</p>
              <p className="text-sm text-green-700">
                Your manager will review your submission soon.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { api, type ManagerReviewSubmitEnhanced } from "@/lib/api";

interface ManagerReviewFormProps {
  reviewId: string;
  employeeName?: string;
  onSuccess?: () => void;
}

export function ManagerReviewForm({ reviewId, employeeName, onSuccess }: ManagerReviewFormProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Partial<ManagerReviewSubmitEnhanced>>({
    okr_outcomes_assessment: "",
    kr_quality_assessment: "",
    manager_feedback: "",
    collaboration_assessment: "",
    ownership_assessment: "",
    accountability_assessment: "",
    execution_assessment: "",
    behavioral_competency_scores: {
      collaboration: 3,
      ownership: 3,
      execution: 3,
      accountability: 3,
    },
  });

  const submitMutation = useMutation({
    mutationFn: () => api.submitManagerReviewEnhanced(reviewId, formData as ManagerReviewSubmitEnhanced),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
      onSuccess?.();
    },
  });

  const setBehavioral = (key: string, value: number) => {
    setFormData({
      ...formData,
      behavioral_competency_scores: {
        ...formData.behavioral_competency_scores,
        [key]: value,
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manager Review</CardTitle>
        <CardDescription>
          Assess OKR outcomes and behaviors for {employeeName || "this employee"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>OKR outcomes</Label>
          <Textarea
            value={formData.okr_outcomes_assessment}
            onChange={(e) => setFormData({ ...formData, okr_outcomes_assessment: e.target.value })}
            rows={3}
          />
        </div>
        <div className="space-y-2">
          <Label>KR quality assessment</Label>
          <Textarea
            value={formData.kr_quality_assessment}
            onChange={(e) => setFormData({ ...formData, kr_quality_assessment: e.target.value })}
            rows={2}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {(["collaboration", "ownership", "execution", "accountability"] as const).map((key) => (
            <div key={key} className="space-y-1">
              <Label className="capitalize">{key} (1-5)</Label>
              <Input
                type="number"
                min={1}
                max={5}
                value={formData.behavioral_competency_scores?.[key] ?? 3}
                onChange={(e) => setBehavioral(key, Number(e.target.value))}
              />
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <Label>Manager feedback</Label>
          <Textarea
            value={formData.manager_feedback}
            onChange={(e) => setFormData({ ...formData, manager_feedback: e.target.value })}
            rows={4}
          />
        </div>
        <Button
          onClick={() => submitMutation.mutate()}
          disabled={submitMutation.isPending || !formData.manager_feedback?.trim()}
        >
          {submitMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            "Submit manager review"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

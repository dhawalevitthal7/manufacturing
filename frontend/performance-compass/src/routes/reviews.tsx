import { createFileRoute } from "@tanstack/react-router";
import { EnhancedReviewsPage } from "@/components/reviews/enhanced-reviews-page";

type ReviewsSearch = {
  view?: string;
};

export const Route = createFileRoute("/reviews")({
  validateSearch: (search: Record<string, unknown>): ReviewsSearch => ({
    view: typeof search.view === "string" ? search.view : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Performance Reviews — Axis Operate" },
      { name: "description", content: "Performance reviews, self-assessments, and check-ins." },
    ],
  }),
  component: ReviewsRoute,
});

function ReviewsRoute() {
  const { view } = Route.useSearch();
  return <EnhancedReviewsPage initialView={view} />;
}

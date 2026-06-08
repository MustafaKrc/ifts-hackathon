import React from "react";
import { useOutletContext } from "react-router-dom";

import SprintReviewPanel from "../components/SprintReviewPanel";

export default function SprintReviewPage() {
  const ctx = useOutletContext();
  return (
    <SprintReviewPanel
      review={ctx.sprintReview}
      onReview={ctx.handleReview}
      canReview={ctx.selectedKeys.length > 0}
      loading={ctx.loading.review}
    />
  );
}

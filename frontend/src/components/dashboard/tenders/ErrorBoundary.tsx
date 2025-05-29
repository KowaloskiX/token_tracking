"use client";

import { useEffect } from "react";
import { useKanban } from "@/context/KanbanContext";

export function ErrorBoundary({ children }: { children: React.ReactNode }) {
  const { error, clearError } = useKanban();

  useEffect(() => {
    if (error && !error.includes("not found")) {
      console.error("Application Error:", error);
      clearError();
    }
  }, [error, clearError]);

  return <>{children}</>;
}
"use client";

import { KanbanProvider } from "@/context/KanbanContext";
import { ErrorBoundary } from "@/components/dashboard/tenders/ErrorBoundary";

export default function TendersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <KanbanProvider>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </KanbanProvider>
  );
}
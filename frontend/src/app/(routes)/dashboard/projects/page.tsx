"use client"
import AssistantGrid from "@/components/dashboard/projects/AssistantGrid"
import * as React from "react"


export default function ProjectsPage() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <main className="flex-1 overflow-y-auto">
        <AssistantGrid />
      </main>
    </div>
  )
}
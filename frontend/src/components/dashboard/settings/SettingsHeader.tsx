// frontend/src/components/dashboard/settings/SettingsHeader.tsx
"use client"

import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

export function SettingsHeader() {
  return (
    <>
      <header className="flex w-full justify-between h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear px-8">
        <div className="flex items-center gap-2 px-4">
          <SidebarTrigger className="-ml-6" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <div className="flex gap-2 items-center">
            <h2 className="text-2xl font-bold tracking-tight">Ustawienia</h2>
          </div>
        </div>
      </header>
      <Separator />
    </>
  )
}
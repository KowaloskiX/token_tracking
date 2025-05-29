import { SidebarNav } from "@/components/dashboard/settings/SidebarNav"
import { Metadata } from "next"
import { SettingsHeader } from "@/components/dashboard/settings/SettingsHeader"

export const metadata: Metadata = {
  title: "Ustawienia",
  description: "Zarządzaj swoimi ustawieniami i preferencjami.",
}

interface SettingsLayoutProps {
  children: React.ReactNode
}

export default function SettingsLayout({ children }: SettingsLayoutProps) {
  return (
    <div className="hidden md:block w-full">
      <SettingsHeader />
      <div className="p-8">
        <div className="flex flex-col space-y-8 lg:flex-row lg:space-x-12 lg:space-y-0">
          <aside className="lg:w-1/5">
            <SidebarNav />
          </aside>
          <div className="flex-1 lg:max-w-2xl">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
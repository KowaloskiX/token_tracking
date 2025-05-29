"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { LucideIcon } from "lucide-react"
import { 
  UserCircle, 
  Building2, 
  Bell,
  // Palette, 
  // Monitor
} from "lucide-react"

const sidebarNavItems = [
  {
    title: "Konto",
    href: "/dashboard/settings",
    icon: UserCircle,
    description: "Manage your account settings and preferences."
  },
  {
    title: "Organizacja",
    href: "/dashboard/settings/organization",
    icon: Building2,
    description: "Manage your organization and team members."
  },
  // {
  //   title: "Appearance",
  //   href: "/dashboard/settings/appearance",
  //   icon: Palette,
  //   description: "Customize the appearance of the application."
  // },
  {
    title: "Powiadomienia",
    href: "/dashboard/settings/notifications",
    icon: Bell,
    description: "Configure your notification preferences."
  },
  // {
  //   title: "Display",
  //   href: "/dashboard/settings/display",
  //   icon: Monitor,
  //   description: "Manage your display settings."
  // },
]

export function SidebarNav() {
  const pathname = usePathname()

  return (
    <nav className="flex space-x-2 lg:flex-col lg:space-x-0 lg:space-y-1">
      {sidebarNavItems.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            buttonVariants({ variant: "ghost" }),
            pathname === item.href
              ? "bg-muted hover:bg-muted"
              : "hover:bg-transparent hover:underline",
            "justify-start w-full"
          )}
        >
          <div className="flex items-center flex-1">
            <item.icon className="mr-2 h-4 w-4" />
            <span>{item.title}</span>
          </div>
        </Link>
      ))}
    </nav>
  )
}
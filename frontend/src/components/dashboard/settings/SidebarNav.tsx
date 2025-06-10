"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from 'next-intl'
import { useState, useEffect } from 'react'
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { 
  UserCircle, 
  Building2, 
  Bell,
  Globe
} from "lucide-react"

const getDefaultSidebarNavItems = () => [
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
  {
    title: "Powiadomienia",
    href: "/dashboard/settings/notifications",
    icon: Bell,
    description: "Configure your notification preferences."
  },
  {
    title: "Język",
    href: "/dashboard/settings/language",
    icon: Globe,
    description: "Choose your preferred language."
  },
];

const getSidebarNavItems = (t: any) => [
  {
    title: t('settings.account'),
    href: "/dashboard/settings",
    icon: UserCircle,
    description: "Manage your account settings and preferences."
  },
  {
    title: t('settings.organization_title'),
    href: "/dashboard/settings/organization",
    icon: Building2,
    description: "Manage your organization and team members."
  },
  {
    title: t('settings.notifications_title'),
    href: "/dashboard/settings/notifications",
    icon: Bell,
    description: "Configure your notification preferences."
  },
  {
    title: t('settings.language_title'),
    href: "/dashboard/settings/language",
    icon: Globe,
    description: "Choose your preferred language."
  },
];

export function SidebarNav() {
  const pathname = usePathname()
  const [mounted, setMounted] = useState(false)
  const t = useTranslations()
  
  useEffect(() => {
    setMounted(true)
  }, [])

  const sidebarNavItems = mounted ? getSidebarNavItems(t) : getDefaultSidebarNavItems()

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
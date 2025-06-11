"use client"
import * as React from "react"
import { usePathname } from "next/navigation"
import {
  Building2,
  ChevronDown,
  GitMerge,
  LibraryBig,
  Lock,
} from "lucide-react"
import Image from "next/image" // Add Image import for the logo

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import { useDashboard } from "@/hooks/useDashboard"
import { AssistantsDropdown } from "./AssistantsDropdown"
import SidebarFooterComponent from "./SidebarFooter"
import { useRouter } from "next/navigation"
import { ConversationsHistory } from "./conversation-history/ConversationHistory"
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible"
import { CollapsibleTrigger } from "@radix-ui/react-collapsible"
import TendersSidebarContent from "../tenders/TendersSidebarContent"
import { useEffect, useState } from "react"
import { useTranslations } from 'next-intl'

// Define route-specific sidebar content components
const ChatSidebarContent = () => (
  <SidebarGroup>
    <SidebarGroupContent>
      <SidebarMenu>
        <ConversationsHistory />
      </SidebarMenu>
    </SidebarGroupContent>
  </SidebarGroup>
)

const ProjectsSidebarContent = () => (
  <SidebarGroup>
    <SidebarGroupContent>
      <SidebarMenu>
        {/* <SidebarMenuButton className="w-full text-sidebar-foreground">
          <span className="flex-1 truncate min-w-0">Recent Projects</span>
        </SidebarMenuButton>
        <SidebarMenuButton className="w-full text-sidebar-foreground">
          <span className="flex-1 truncate min-w-0">Archived Projects</span>
        </SidebarMenuButton> */}
      </SidebarMenu>
    </SidebarGroupContent>
  </SidebarGroup>
)


interface SidebarComponentProps {
  defaultCollapsed?: boolean;
}

export default function SidebarComponent({ defaultCollapsed }: SidebarComponentProps) {
  const t = useTranslations('common');
  const { 
    assistants = [],
    currentAssistant, 
    setCurrentAssistant 
  } = useDashboard();
  const pathname = usePathname()
  const router = useRouter();
  const isChat = pathname?.startsWith('/dashboard/chat')
  const isTenders = pathname?.startsWith('/dashboard/tenders')
  const { setOpen, open } = useSidebar();
  // Track if we've done the initial collapse
  const initialCollapseRef = React.useRef(false);

  React.useEffect(() => {
    if (assistants.length > 0 && !currentAssistant) {
      setCurrentAssistant(assistants[0])
    }
  }, [assistants, currentAssistant, setCurrentAssistant])

  // Add useEffect to handle automatic collapse/expand based on pathname
  React.useEffect(() => {
    const shouldCollapse = pathname?.startsWith('/dashboard/settings')
    
    if (shouldCollapse) {
      if (!initialCollapseRef.current) {
        setOpen(false);
        initialCollapseRef.current = true;
      }
    } else {
      // Reset the ref and expand sidebar when navigating to non-collapsible routes
      initialCollapseRef.current = false;
      setOpen(true);
    }
  }, [pathname, setOpen]);

  // Function to render route-specific content
  const renderRouteContent = () => {
    if (isChat) {
      return <ChatSidebarContent />
    } else {
      return <TendersSidebarContent />
    }
  }
  
  // Function to render header content based on current route and sidebar state
  const renderHeaderContent = () => {
    if (isTenders) {
      return (
        <SidebarMenuButton
          onClick={() => router.push('/dashboard/tenders')}
          className="cursor-pointer py-6 data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
        >
          {/* Different logos for collapsed vs expanded states */}
          <div className="flex items-center">
            {open ? (
              <Image 
                src="/images/asystent_ai_logo_brown_long.png" 
                width={520}
                height={280}
                alt="Asystent AI" 
                className="w-auto h-8" 
              />
            ) : (
              <Image 
                src="/images/asystent_ai_logo_black.png" 
                width={280}
                height={280}
                alt="Asystent AI" 
                className="w-auto h-4" 
              />
            )}
          </div>
        </SidebarMenuButton>
      )
    } else {
      return (
        <SidebarMenuButton
          onClick={() => router.push('/dashboard/tenders/chat')}
          className="cursor-pointer py-6 data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground border-b border-neutral-200"
        >
          <LibraryBig strokeWidth={2.2} className="w-5 h-5 size-5" />
          <span className="truncate font-semibold text-lg ml-2">
            {t('projects')}
          </span>
        </SidebarMenuButton>
      )
    }
  }
  
  return (
    <Sidebar className="shadow" collapsible="icon" defaultCollapsed={defaultCollapsed}>
      <SidebarHeader>
        {renderHeaderContent()}

        {isChat && (
          <SidebarMenu>
            <AssistantsDropdown />
          </SidebarMenu>
        )}
      </SidebarHeader>
      <SidebarContent className="pb-4 scrollbar-hide">
        {renderRouteContent()}
      </SidebarContent>
      <SidebarFooterComponent />
      <SidebarRail />
    </Sidebar>
  )
}
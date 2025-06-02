// ConversationsHistory.tsx
"use client"

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Conversation, PaginatedConversations } from "@/types";
import { getConversationsByAssistant } from '@/utils/conversationActions';
import { useDashboard } from '@/context/DashboardContext';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@radix-ui/react-collapsible";
import { 
  ChevronRight, 
  Forward, 
  Trash2, 
  MessageSquare, 
  MessageSquarePlus,
  MoreHorizontal,
  Loader2,
  Bot,
  PanelsTopLeft
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Portal } from "@radix-ui/react-portal";
import { useConversation } from "@/hooks/useConversation";
import { 
  SidebarMenuButton, 
  SidebarMenuItem, 
  SidebarMenuSub, 
  SidebarMenuSubItem,
  SidebarGroup,
  SidebarMenu,
  SidebarMenuAction
} from "@/components/ui/sidebar";
import { getConversation } from '@/utils/conversationActions';
import { deleteConversation } from '@/utils/conversationActions';
import { DeletePopup } from '../../popup/DeletePopup';
import { usePathname } from 'next/navigation';

import Link from 'next/link'; // Import Link

function AssistantHeader({ 
  assistant, 
  isExpanded, 
  onToggleExpanded, 
  children 
}: { 
  assistant: any; 
  isExpanded: boolean; 
  onToggleExpanded: () => void; 
  children: React.ReactNode; 
}) {
  if (!assistant) return null;

  return (
    <div className="w-full">
      <div className="rounded-lg bg-sidebar-accent/50 border border-sidebar-border overflow-hidden">
        {/* Assistant Header */}
        <div className="flex items-center gap-3 p-3">
          <div className="flex-shrink-0">
            <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
              <PanelsTopLeft className="w-4 h-4 text-primary" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-sidebar-foreground truncate">
              {assistant.name}
            </div>
          </div>
        </div>

        {/* Conversations Section */}
        <div className="border-t border-sidebar-border/50">
          <Collapsible
            open={isExpanded}
            onOpenChange={onToggleExpanded}
            className="group/collapsible w-full"
          >
            <CollapsibleTrigger asChild className="w-full">
              <div className="w-full">
                <SidebarMenuButton tooltip="Conversations" className="w-full rounded-none hover:bg-sidebar-accent/70">
                  <MessageSquare className="shrink-0 text-sidebar-foreground" />
                  <span className="flex-1 truncate min-w-0">Konwersacje</span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-sidebar-foreground transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                </SidebarMenuButton>
              </div>
            </CollapsibleTrigger>
            <CollapsibleContent className="w-full">
              <div className="bg-sidebar-accent/20">
                {children}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      </div>
    </div>
  );
}

function ConversationItem({ 
  conversation, 
  onDelete,
  isDeleting = false
}: any) {
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    isLoading: boolean;
  }>({ isOpen: false, isLoading: false });

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setDeleteDialog(prev => ({ ...prev, isLoading: true }));
    await onDelete(conversation);
    setDeleteDialog({ isOpen: false, isLoading: false });
  }

  return (
    <div className="group/conversation relative w-full">
      <Link href={`/dashboard/tenders/chat/${conversation._id}`} passHref>
        <SidebarMenuButton asChild className="w-full">
          <div className="relative w-full flex items-center">
            <MessageSquare className="shrink-0" />
            <span className="truncate">{conversation.title}</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuAction 
                  className="invisible absolute right-1 top-1/2 -translate-y-1/2 group-hover/conversation:visible shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4" />
                  <span className="sr-only">More</span>
                </SidebarMenuAction>
              </DropdownMenuTrigger>
              <Portal>
                <DropdownMenuContent
                  className="w-48 rounded-lg"
                  side="right"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuItem onClick={(e) => e.stopPropagation()}>
                    <Forward className="mr-2 text-muted-foreground" />
                    <span>Share Conversation</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteDialog(prev => ({ ...prev, isOpen: true }));
                    }}
                    className="text-destructive focus:text-destructive"
                    disabled={isDeleting || deleteDialog.isLoading}
                  >
                    <Trash2 className="mr-2" />
                    <span>
                      {isDeleting || deleteDialog.isLoading ? 'Deleting...' : 'Delete Conversation'}
                    </span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </Portal>
            </DropdownMenu>
          </div>
        </SidebarMenuButton>
      </Link>
      
      <DeletePopup 
        isOpen={deleteDialog.isOpen}
        onOpenChange={(open) => 
          setDeleteDialog(prev => ({ ...prev, isOpen: open }))
        }
        onConfirm={handleDelete}
        title="Usuń konwersację"
        description="Czy jesteś pewien? Ta akcja jest nieowracalna."
        isLoading={deleteDialog.isLoading}
      />
    </div>
  );
}

export function ConversationsHistory() {
  const { 
    currentAssistant, 
    currentConversation,
    setCurrentConversation,
    setConversationLoading 
  } = useDashboard();

  const [isExpanded, setIsExpanded] = useState(true);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState<Omit<PaginatedConversations, 'data'> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [deletingConversations, setDeletingConversations] = useState<Set<string>>(new Set());

  const pathname = usePathname();
  const params = useParams();
  const { createNewConversation } = useConversation();
  const router = useRouter();
  const isFetching = useRef(false);
  const mounted = useRef(true);

  async function fetchConversations(assistantId: string, page: number) {
    if (isFetching.current || !mounted.current) return;

    try {
      isFetching.current = true;
      setIsLoading(true);
      
      const result = await getConversationsByAssistant(assistantId, page);

      if (mounted.current) {
        setConversations(prev => {
          const newConversations = page === 1 ? [] : [...prev];
          let hasChanges = false;
          
          result.data.forEach((conversation: Conversation) => {
            if (!newConversations.some(conv => conv._id === conversation._id)) {
              newConversations.push(conversation);
              hasChanges = true;
            }
          });
          
          return hasChanges ? newConversations : prev;
        });

        setPagination({
          page: result.page,
          total_pages: result.total_pages,
          total_items: result.total_items,
          has_next: result.has_next,
          has_previous: result.has_previous
        });
      }
    } catch (err) {
      console.error('Error loading conversations:', err);
    } finally {
      if (mounted.current) {
        setIsLoading(false);
      }
      isFetching.current = false;
    }
  }

  async function handleNewConversation() {
    if (!currentAssistant || isCreatingConversation) return;
    
    try {
      setIsCreatingConversation(true);
      setConversationLoading(true);
  
      const conversation = await createNewConversation();
      
      if (mounted.current) {
        setConversations(prev => {
          if (prev.some(conv => conv._id === conversation._id)) {
            return prev;
          }
          return [conversation, ...prev];
        });
        
        router.push(`/dashboard/tenders/chat/${conversation._id}`, {
          scroll: false
        });
        
        setCurrentConversation(conversation);
      }
    } catch (error) {
      console.error('Failed to create conversation:', error);
    } finally {
      if (mounted.current) {
        setIsCreatingConversation(false);
        setConversationLoading(false);
      }
    }
  }

  async function handleDeleteConversation(conversation: Conversation) {
    if (!mounted.current) return;
  
    try {
      setDeletingConversations(prev => new Set(prev).add(conversation._id));
      
      await deleteConversation(conversation._id);
      
      if (mounted.current) {
        if (currentConversation?._id === conversation._id) {
          const currentIndex = conversations.findIndex(conv => conv._id === conversation._id);
          const previousConversation = currentIndex > 0 ? conversations[currentIndex - 1] : conversations[currentIndex + 1];
  
          setConversations(prevConversations => 
            prevConversations.filter(conv => conv._id !== conversation._id)
          );
  
          if (previousConversation) {
            handleSelectConversation(previousConversation);
          } else {
            setCurrentConversation(null);
            router.push('/dashboard/tenders/chat/new', { scroll: false });
            handleNewConversation();
          }
        } else {
          setConversations(prevConversations => 
            prevConversations.filter(conv => conv._id !== conversation._id)
          );
        }
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      throw error; // Re-throw to let the DeletePopup handle the error state
    } finally {
      if (mounted.current) {
        setDeletingConversations(prev => {
          const updated = new Set(prev);
          updated.delete(conversation._id);
          return updated;
        });
      }
    }
  }


  async function handleSelectConversation(conversation: Conversation) {
    try {
      setConversationLoading(true);
      const conversationDetails = await getConversation(conversation._id);
      
      if (mounted.current) {
        setCurrentConversation(conversationDetails);
        router.push(`/dashboard/tenders/chat/${conversation._id}`);
      }
    } catch (err) {
      console.error('Error loading conversation:', err);
    } finally {
      if (mounted.current) {
        setConversationLoading(false);
      }
    }
  }

  function handleLoadMore() {
    if (pagination?.has_next && !isLoading && !isFetching.current && currentAssistant) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      fetchConversations(currentAssistant._id!, nextPage);
    }
  }

  useEffect(() => {
    if (currentAssistant?._id) {
      setConversations([]);
      setCurrentPage(1);
      setPagination(null);
      fetchConversations(currentAssistant._id, 1);
    }
    
    return () => {
      mounted.current = false;
    };
  }, [currentAssistant?._id]);

  useEffect(() => {
    const chatId = params.chatId;
    if (chatId && (!currentConversation || currentConversation._id !== chatId)) {
      const conversation = conversations.find(conv => conv._id === chatId);
      if (conversation && mounted.current && !currentConversation) {
        handleSelectConversation(conversation);
      }
    }
  }, [pathname, currentConversation?._id, conversations]);

  if (!currentAssistant) {
    return null;
  }

  return (
    <div className="w-full flex flex-col">
      <AssistantHeader 
        assistant={currentAssistant}
        isExpanded={isExpanded}
        onToggleExpanded={() => setIsExpanded(!isExpanded)}
      >
        <SidebarMenuSub className="w-full">
          <SidebarMenuSubItem className="w-full">
            <SidebarMenuButton 
              className="w-full text-sidebar-foreground"
              onClick={handleNewConversation}
              disabled={isCreatingConversation}
            >
              {isCreatingConversation ? (
                <Loader2 className="shrink-0 text-sidebar-foreground h-4 w-4 animate-spin" />
              ) : (
                <MessageSquarePlus className="shrink-0 text-sidebar-foreground" />
              )}
              <span className="flex-1 truncate min-w-0">
                {isCreatingConversation ? 'Rozpoczynanie...' : 'Nowa konwersacja'}
              </span>
            </SidebarMenuButton>
          </SidebarMenuSubItem>

          <SidebarGroup className="w-full">
            <SidebarMenu className="w-full space-y-1">
              {conversations.map((conversation) => (
                <SidebarMenuItem key={conversation._id} className="w-full cursor-pointer">
                  <ConversationItem 
                    conversation={conversation}
                    onSelect={handleSelectConversation}
                    onDelete={handleDeleteConversation}
                    isDeleting={deletingConversations.has(conversation._id)}
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>

          {pagination?.has_next && (
            <SidebarMenuSubItem className="w-full">
              <SidebarMenuButton 
                className="w-full text-sidebar-foreground/70"
                onClick={handleLoadMore}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="shrink-0 text-sidebar-foreground h-4 w-4 animate-spin" />
                ) : (
                  <MessageSquare className="shrink-0 text-sidebar-foreground/70" />
                )}
                <span className="flex-1 truncate min-w-0">
                  {isLoading ? 'Loading...' : 'Load More'}
                </span>
              </SidebarMenuButton>
            </SidebarMenuSubItem>
          )}
        </SidebarMenuSub>
      </AssistantHeader>
    </div>
  );
}
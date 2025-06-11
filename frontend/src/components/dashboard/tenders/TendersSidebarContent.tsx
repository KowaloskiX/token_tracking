'use client';

import { Plus, Loader2, AlertCircle, Search, MessageSquare, Settings, ChevronDown, Kanban, KanbanSquare, CircleArrowLeft } from 'lucide-react';
import { useState, useEffect } from 'react';
import { 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarGroupLabel, 
  SidebarMenu, 
  SidebarMenuButton, 
  SidebarMenuItem
} from "@/components/ui/sidebar";
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTender } from '@/context/TenderContext';
import { TenderAnalysisCreateForm } from './forms/TenderAnalysisCreationForm';
import { TenderAnalysisSidebarItem } from './TenderAnalysisSidebarItem';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import { CollapsibleTrigger } from "@radix-ui/react-collapsible";
import { usePathname, useRouter, useParams } from 'next/navigation';
import { ConversationsHistory } from '../sidebar/conversation-history/ConversationHistory';
import { KanbanColumn } from './kanban/KanbanColumn';
import { AnalysisCriteria } from '@/types/tenders';
import { useTendersTranslations, useNavigationTranslations } from "@/hooks/useTranslations";

const ANALYSIS_LIMIT = 10;

export function TendersSidebarContent() {
  const [open, setOpen] = useState(false);
  const [showLimitDialog, setShowLimitDialog] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(true);
  const [isAnalyzeOpen, setIsAnalyzeOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('search');
  
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const chatId = params?.chatId as string;
  
  const t = useTendersTranslations();
  const navT = useNavigationTranslations();
  
  const isChatDetailPage = pathname?.includes('/tenders/chat/') && chatId && chatId !== 'new';
  
  const { 
    analyses, 
    fetchAnalyses, 
    createAnalysis,
    deleteAnalysis,
    isLoading 
  } = useTender();

  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);
  
  // Set active dropdown and tab based on current path
  useEffect(() => {
    if (pathname?.includes('/tenders/chat')) {
      setIsAnalyzeOpen(true);
      setIsSearchOpen(false);
      setActiveTab('analyze');
    } else if (pathname?.includes('/tenders/management')) {
      setIsSearchOpen(false);
      setIsAnalyzeOpen(false);
      setActiveTab('manage');
    } else if (pathname?.includes('/tenders')) {
      setIsSearchOpen(true);
      setIsAnalyzeOpen(false);
      setActiveTab('search');
    }
  }, [pathname]);

  const handleCreateAnalysis = async (values: {
    name: string;
    company_description: string;
    search_phrase: string;
    sources: string[];
    criteria: AnalysisCriteria[];
  }) => {
    try {
      const transformedData = {
        ...values,
        criteria: values.criteria.map(criterion => ({
          name: criterion.name,
          description: criterion.description,
          weight: criterion.weight,
          is_disqualifying: criterion.is_disqualifying,
          exclude_from_score: criterion.exclude_from_score,
          instruction: criterion.instruction,
          subcriteria: criterion.subcriteria,
          keywords: criterion.keywords,
        }))
      };
  
      await createAnalysis(transformedData);
      setOpen(false);
    } catch (error) {
      console.error("Error creating analysis:", error);
    }
  };

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{navT('tenders')}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu className="w-full space-y-1">
          <Collapsible 
            open={isSearchOpen} 
            onOpenChange={(open) => {
              setIsSearchOpen(open);
              if (open) {
                router.push('/dashboard/tenders');
                setActiveTab('search');
              }
            }}
            className="w-full"
          >
            <CollapsibleTrigger asChild>
              <SidebarMenuButton 
                className={`w-full text-sidebar-foreground ${activeTab === 'search' ? 'bg-secondary' : ''}`}
              >
                <Search className="shrink-0 text-sidebar-foreground h-4 w-4 mr-2" />
                <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.search')}</span>
                <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${isSearchOpen ? "rotate-180" : ""}`} />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            
            <CollapsibleContent>
              <div className="pl-6 pr-2 pt-2">
                <ScrollArea className="max-h-[60svh] mb-2">
                  {isLoading ? (
                    <SidebarMenuItem className="w-full">
                      <SidebarMenuButton className="w-full text-sidebar-foreground/70">
                        <Loader2 className="shrink-0 text-sidebar-foreground h-4 w-4 animate-spin" />
                        <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.loadingSearches')}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ) : analyses.length === 0 ? (
                    <SidebarMenuItem className="w-full">
                      <SidebarMenuButton className="w-full text-sidebar-foreground/70">
                        <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.noSearches')}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ) : (
                    analyses.map((analysis) => (
                      <SidebarMenuItem key={analysis._id} className="w-full">
                        <TenderAnalysisSidebarItem
                          analysis={analysis}
                          onDelete={deleteAnalysis}
                          isDeleting={false}
                        />
                      </SidebarMenuItem>
                    ))
                  )}
                </ScrollArea>

                <SidebarMenuItem className="w-full mt-2">
                  <SidebarMenuButton 
                      className="w-full text-sidebar-foreground"
                      onClick={(e) => {
                          e.preventDefault();
                          if (analyses.length >= ANALYSIS_LIMIT) {
                              setShowLimitDialog(true);
                          } else {
                              setOpen(true);
                          }
                      }}
                  >
                      <Plus className="shrink-0 text-sidebar-foreground h-4 w-4" />
                      <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.newSearch')}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {isChatDetailPage ? (
            <Collapsible 
              open={isAnalyzeOpen} 
              onOpenChange={(open) => {
                setIsAnalyzeOpen(open);
                setActiveTab('analyze');
              }}
              className="w-full"
            >
              <CollapsibleTrigger asChild>
                <SidebarMenuButton 
                  className={`w-full text-sidebar-foreground ${activeTab === 'analyze' ? 'bg-secondary' : ''}`}
                >
                  <MessageSquare className="shrink-0 text-sidebar-foreground h-4 w-4 mr-2" />
                  <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.analyze')}</span>
                  <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${isAnalyzeOpen ? "rotate-180" : ""}`} />
                </SidebarMenuButton>
              </CollapsibleTrigger>
              
              <CollapsibleContent>
              <SidebarMenuButton onClick={() => {
                  router.push('/dashboard/tenders/chat');
                  setActiveTab('analyze');
                }}>
                  <CircleArrowLeft/>
                  {t('tenders.sidebar.backToProjects')}
                </SidebarMenuButton>
                <div className="pl-6 pr-2 pt-2">
                  <ConversationsHistory />
                </div>
              </CollapsibleContent>
            </Collapsible>
          ) : (
            // Show as simple menu item that navigates to chat page when not on a specific chat
            <SidebarMenuItem className="w-full">
              <SidebarMenuButton 
                className={`w-full text-sidebar-foreground ${activeTab === 'analyze' ? 'bg-secondary' : ''}`}
                onClick={() => {
                  router.push('/dashboard/tenders/chat');
                  setActiveTab('analyze');
                }}
              >
                <MessageSquare className="shrink-0 text-sidebar-foreground h-4 w-4 mr-2" />
                <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.analyze')}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}

          {/* Zarządzaj as a simple button */}
          <SidebarMenuItem className="w-full">
            <SidebarMenuButton 
              className={`w-full text-sidebar-foreground ${activeTab === 'manage' ? 'bg-secondary' : ''}`}
              onClick={() => {
                router.push('/dashboard/tenders/management');
                setActiveTab('manage');
              }}
            >
              <KanbanSquare className="shrink-0 text-sidebar-foreground h-4 w-4 mr-2" />
              <span className="flex-1 truncate min-w-0">{t('tenders.sidebar.manage')}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroupContent>

      {open && (
        <div 
          className="fixed inset-0 bg-foreground/50 z-50 overflow-y-auto scrollbar-hide py-20"
          onClick={() => setOpen(false)}
        >
          <div 
            className="bg-background dark:bg-foreground rounded-lg w-full max-w-xl mx-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6 pb-0">
              <h2 className="text-lg font-semibold">
                {t('tenders.create.title')}
              </h2>
            </div>
            <TenderAnalysisCreateForm 
              onSubmit={handleCreateAnalysis}
              onCancel={() => setOpen(false)}
              isLoading={isLoading}
            />
          </div>
        </div>
      )}

      {showLimitDialog && (
        <div 
          className="fixed inset-0 bg-black/50 z-50 overflow-y-auto py-16"
          onClick={() => setShowLimitDialog(false)}
        >
          <div 
            className="bg-white dark:bg-gray-950 rounded-lg w-full max-w-md mx-auto p-6"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="h-5 w-5 text-destructive" />
              <h2 className="text-lg font-semibold">
                {t('tenders.sidebar.limitReached')}
              </h2>
            </div>
            <p className="text-muted-foreground mb-6">
              {t('tenders.sidebar.limitMessage', { limit: ANALYSIS_LIMIT })}
            </p>
            <div className="flex justify-end">
              <Button 
                variant="outline" 
                onClick={() => setShowLimitDialog(false)}
              >
                {t('tenders.sidebar.understand')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </SidebarGroup>
  );
}

export default TendersSidebarContent;
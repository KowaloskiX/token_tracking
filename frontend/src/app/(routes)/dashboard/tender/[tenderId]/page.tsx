"use client"
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { 
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { TooltipProvider } from "@/components/ui/tooltip";
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { useMemo } from 'react';
import { TenderAnalysisResult, TenderAnalysisUpdate } from '@/types/tenders';
import { useTender } from '@/context/TenderContext';
import { KanbanProvider } from '@/context/KanbanContext';
import { useToast } from '@/hooks/use-toast';
import TenderDetailsSkeleton from '@/components/dashboard/tenders/TenderDetailsSkeleton';
import { CriteriaAnalysisResult } from '@/types/tenders';
import { AddToKanbanDialog } from '@/components/dashboard/tenders/AddToKanbanDialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { createAssistant } from '@/utils/assistantActions';
import { createConversation } from '@/utils/conversationActions';
import { createFilesWithOpenAIId } from '@/utils/fileActions';
import { Assistant, CreateConversationRequest } from '@/types';
import { useTendersTranslations, useCommonTranslations } from '@/hooks/useTranslations';
import TenderDetailsHeader from '@/components/dashboard/tender/TenderDetailsHeader';
import TenderInfoCard from '@/components/dashboard/tender/TenderInfoCard';
import TenderStatusCard from '@/components/dashboard/tender/TenderStatusCard';
import TenderCriteriaCard from '@/components/dashboard/tender/TenderCriteriaCard';
import TenderActionButtons from '@/components/dashboard/tender/TenderActionButtons';
import TenderDescriptionCard from '@/components/dashboard/tender/TenderDescriptionCard';
import TenderUpdatesCard from '@/components/dashboard/tender/TenderUpdatesCard';
import TenderFilesCard from '@/components/dashboard/tender/TenderFilesCard';
import TenderCommentsCard from '@/components/dashboard/tender/TenderCommentsCard';
import JSZip from 'jszip';

interface UpdateSummary {
  update_id: string;
  overall_summary: string;
  file_summaries: Array<{
    filename: string;
    summary: string;
  }>;
}

function TenderDetailsPageContent() {
  const { tenderId } = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  
  const [tender, setTender] = useState<TenderAnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [localStatus, setLocalStatus] = useState<string>('inactive');
  const [resultUpdates, setResultUpdates] = useState<TenderAnalysisUpdate[]>([]);
  const [isLoadingUpdates, setIsLoadingUpdates] = useState(false);
  const [updateSummaries, setUpdateSummaries] = useState<UpdateSummary[]>([]);
  const [showAddToKanban, setShowAddToKanban] = useState(false);
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupMessage, setPopupMessage] = useState("");
  const [addToKanbanSuccess, setAddToKanbanSuccess] = useState<boolean | null>(null);
  const [addedToBoardId, setAddedToBoardId] = useState<string | null>(null);

  const { updateTenderStatus, fetchTenderResultById } = useTender();

  // Markdown components for rendering
  const markdownComponents: Components = useMemo(() => ({
    p: ({ children }) => <p className="my-1 leading-normal whitespace-pre-line">{children}</p>,
    h1: ({ children }) => <h1 className="text-xl font-bold mt-2 mb-1">{children}</h1>,
    h2: ({ children }) => <h2 className="text-lg font-bold mt-2 mb-1">{children}</h2>,
    h3: ({ children }) => <h3 className="text-md font-bold mt-1.5 mb-0.5">{children}</h3>,
    h4: ({ children }) => <h4 className="text-base font-semibold mt-1 mb-0.5">{children}</h4>,
    strong: ({ children }) => <strong className="font-bold">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-secondary-border pl-2 my-1 italic bg-secondary/50 py-0.5 rounded-r">
        {children}
      </blockquote>
    ),
    ul: ({ children }) => (
      <ul className="list-disc pl-4 my-1">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal pl-4 my-1">
        {children}
      </ol>
    ),
    li: ({ children }) => (
      <li className="mb-2 relative">
        {children}
      </li>
    ),
    a: ({ href, children, ...props }) => (
      <a
        href={href ?? '#'}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 underline hover:text-blue-800"
        {...props}
      >
        {children}
      </a>
    ),
    hr: () => <hr className="border-secondary-border my-2" />,
    code: ({ inline, children, ...props }: any) =>
      inline ? (
        <code className="bg-secondary-hover rounded px-1 py-0.5 font-mono text-sm" {...props}>
          {children}
        </code>
      ) : (
        <pre className="bg-secondary-hover p-2 rounded-lg my-1 overflow-x-auto">
          <code className="font-mono text-sm" {...props}>{children}</code>
        </pre>
      ),
  }), []);

  // Fetch tender data
  useEffect(() => {
    if (!tenderId) return;

    const fetchTender = async () => {
      setLoading(true);
      try {
        const result = await fetchTenderResultById(tenderId as string);
        if (result) {
          setTender(result);
          setLocalStatus(result.status || 'inactive');
          fetchUpdates(result);
          fetchTenderUpdatesSummary(result._id!);
        } else {
          toast({
            title: t('tenders.errors.loadFailedTitle'),
            description: t('tenders.errors.notFound'),
            variant: "destructive"
          });
          router.push('/dashboard/tenders');
        }
      } catch (error) {
        console.error('Error fetching tender:', error);
        toast({
          title: t('tenders.errors.loadFailedTitle'),
          description: t('tenders.errors.loadFailed'),
          variant: "destructive"
        });
        router.push('/dashboard/tenders');
      } finally {
        setLoading(false);
      }
    };

    fetchTender();
  }, [tenderId, fetchTenderResultById, toast, router, t]);

  const fetchUpdates = async (tender: TenderAnalysisResult) => {
    if (!tender || !tender.updates || tender.updates.length === 0) {
      setResultUpdates([]);
      return;
    }

    setIsLoadingUpdates(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        console.error('Authentication token not found');
        return;
      }

      const updatePromises = tender.updates.map(async (updateId) => {
        const updateResponse = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-updates/${updateId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          }
        });
        
        if (!updateResponse.ok) {
          console.error(`Failed to fetch update ${updateId}`);
          return null;
        }
        const data = await updateResponse.json();
        return data;
      });
      
      const updates = await Promise.all(updatePromises);
      const validUpdates = updates
        .filter((update): update is TenderAnalysisUpdate => update !== null)
        .sort((a, b) => new Date(b.update_date).getTime() - new Date(a.update_date).getTime());
      
      setResultUpdates(validUpdates);
    } catch (error) {
      console.error('Error fetching updates:', error);
      setResultUpdates([]);
    } finally {
      setIsLoadingUpdates(false);
    }
  };

  const fetchTenderUpdatesSummary = async (tenderId: string) => {
    if (!tenderId) return [];
    
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        console.error('Authentication token not found');
        return [];
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tenders/${tenderId}/updates`, 
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          }
        }
      );
      
      if (!response.ok) {
        throw new Error(`Error fetching tender updates: ${response.statusText}`);
      }
      
      const summaries = await response.json();
      setUpdateSummaries(summaries);
    } catch (error) {
      console.error('Error fetching tender updates summary:', error);
      setUpdateSummaries([]);
    }
  };

  const handleStatusChange = async (value: string) => {
    if (!tender || !tender._id) return;

    if (!['inactive', 'active', 'archived'].includes(value)) {
      console.error('Invalid status value:', value);
      return;
    }
    
    const newStatus = value as 'inactive' | 'active' | 'archived';
    setLocalStatus(newStatus);
    
    try {
      await updateTenderStatus(tender._id!, newStatus);
      setTender(prev => prev ? { ...prev, status: newStatus } : null);
    } catch (error) {
      console.error('Error updating tender status:', error);
      setLocalStatus(tender.status || 'inactive');
    }
  };

  const handleCriteriaUpdate = (criteriaName: string, newSummary: string) => {
    if (!tender?._id) return;
    setTender(prev => {
      if (!prev) return null;
      return {
        ...prev,
        criteria_analysis: prev.criteria_analysis.map((item) =>
          item.criteria === criteriaName
            ? {
                ...item,
                analysis: {
                  ...item.analysis,
                  summary: newSummary,
                },
              }
            : item
        ),
      };
    });
  };

  const openAsAssistant = async () => {
    if (!tender) return;
    setIsCreating(true);
    try {
      const fileSearchTool = {
        type: "file_search",
        config: {}
      };
      const assistantData: Omit<Assistant, 'id' | 'created_at'> = {
        name: `${tender.tender_metadata?.name || t('tenders.board.unnamedTender')}`,
        description: tender.company_match_explanation || '',
        model: "gpt-4-turbo",
        owner_id: tender.user_id,
        system_prompt: `You are a specialized tender analysis assistant for the tender "${tender.tender_metadata?.name || t('tenders.board.unnamedTender')}" from ${tender.tender_metadata?.organization || 'Unknown Organization'}.
        The tender involves ${tender.company_match_explanation || 'no specific details'}.
        The submission deadline is ${tender.tender_metadata?.submission_deadline || 'not specified'}.
        Please help the user understand the tender requirements and prepare their submission.`,
        tools: [fileSearchTool],
        shared_with: [],
        temperature: 0.6,
        pinecone_config: tender.pinecone_config,
        tender_pinecone_id: tender.tender_pinecone_id,
        assigned_users: []
      };
    
      const assistant = await createAssistant(assistantData);
      const filesToCreate = tender.uploaded_files
        ?.map(file => ({
          filename: file.filename,
          openai_file_id: file.openai_file_id,
          blob_url: file.blob_url,
          type: file.filename.split('.').pop()?.toLowerCase() || 'unknown'
        })) || [];

      if (filesToCreate.length > 0) {
        await createFilesWithOpenAIId({
          files: filesToCreate,
          owner_id: tender.user_id,
          assistant_id: assistant._id
        });
      }

      const conversationData: CreateConversationRequest = {
        user_id: tender.user_id,
        assistant_id: assistant._id,
        initial_message: ``,
        our_rag: tender.pinecone_config ? true : undefined
      };

      const conversation = await createConversation(conversationData);
      window.open(`/dashboard/tenders/chat/${conversation._id}`, '_blank');

    } catch (error) {
      console.error('Error creating assistant or conversation:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const exportCriteriaToXls = (
    criteria: CriteriaAnalysisResult[],
    fileName = 'criteria_analysis'
  ) => {
    const name = tender?.tender_metadata?.name || t('tenders.actions.noTenderSelected');
    const description = tender?.tender_description || '';
    const headers = [t('tenders.criteria.title'), t('tenders.updates.updateSummary'), t('tenders.criteria.met'), t('tenders.criteria.weight')];
    const columnCount = headers.length;
    
    let table = '<table><thead>';
    
    table += '<tr>';
    table += `<th colspan="${columnCount}" style="font-weight: bold">${name}</th>`;
    table += '</tr>';
    
    table += '<tr>';
    table += `<th colspan="${columnCount}">${description}</th>`;
    table += '</tr>';
    
    table += '<tr>';
    headers.forEach(h => table += `<th style="font-weight: bold">${h}</th>`);
    table += '</tr></thead><tbody>';
    
    criteria.forEach(item => {
      table += '<tr>';
      table += `<td>${item.criteria}</td>`;
      table += `<td>${item.analysis.summary.replace(/"/g, '""')}</td>`;
      table += `<td>${item.analysis.criteria_met === true ? commonT('yes') : item.analysis.criteria_met === false ? commonT('no') : ''}</td>`;
      table += `<td>${item.analysis.weight}</td>`;
      table += '</tr>';
    });
    
    table += '</tbody></table>';
    
    const html = 
      '<html xmlns:o="urn:schemas-microsoft-com:office:office" ' +
            'xmlns:x="urn:schemas-microsoft-com:office:excel" ' +
            'xmlns="http://www.w3.org/TR/REC-html40">' +
      '<head>' +
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />' +
        '<!--[if gte mso 9]><xml>' +
          '<x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>' +
            '<x:Name>Sheet1</x:Name>' +
            '<x:WorksheetOptions><x:DisplayGridlines/>' +
            '</x:WorksheetOptions>' +
          '</x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook>' +
        '</xml><![endif]-->' +
      '</head>' +
      `<body>${table}</body></html>`;
    
    const bom = '\uFEFF';
    const blob = new Blob([bom + html], {
      type: 'application/vnd.ms-excel;charset=utf-8'
    });
  
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName}.xls`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: t('tenders.actions.copySuccess'),
      description: t('tenders.actions.copySuccessDescription')
    });
  };

  if (loading) {
    return (
      <div className="w-full h-screen overflow-y-auto bg-background">
        <TenderDetailsSkeleton />
      </div>
    );
  }

  if (!tender) {
    return (
      <div className="w-full h-screen overflow-y-auto bg-background">
        <div className="container mx-auto px-4 py-20">
          <div className="max-w-md mx-auto text-center">
            <h1 className="text-2xl font-bold mb-2">{t('tenders.errors.notFound')}</h1>
            <p className="text-muted-foreground mb-4">{t('tenders.errors.notFoundDescription')}</p>
            <Button onClick={() => router.push('/dashboard/tenders')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t('tenders.actions.backToTenders')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="w-full h-screen overflow-y-auto bg-background">
        <TenderDetailsHeader 
          tender={tender}
          onCopyId={copyToClipboard}
        />

        {/* Main Content */}
        <div className="w-full">
          <div className="container mx-auto px-4 py-6">
            <div className="max-w-4xl mx-auto space-y-6 pb-32"> {/* Increased bottom padding for fixed buttons */}
              <TenderDescriptionCard 
                tender={tender}
                markdownComponents={markdownComponents}
              />

              <TenderInfoCard tender={tender} />

              <TenderStatusCard 
                status={localStatus}
                onStatusChange={handleStatusChange}
              />

              <TenderCriteriaCard
                tender={tender}
                markdownComponents={markdownComponents}
                onCriteriaUpdate={handleCriteriaUpdate}
                onExportCriteria={exportCriteriaToXls}
              />

              <TenderUpdatesCard
                tender={tender}
                resultUpdates={resultUpdates}
                isLoadingUpdates={isLoadingUpdates}
                updateSummaries={updateSummaries}
              />

              <TenderFilesCard tender={tender} />

              <TenderCommentsCard tender={tender} />

              {/* Remove TenderActionButtons from here - it's now fixed at bottom */}
            </div>
          </div>
        </div>

        {/* Fixed Action Buttons - outside the scrollable content */}
        <TenderActionButtons
          tender={tender}
          localStatus={localStatus}
          isCreating={isCreating}
          onOpenAsAssistant={openAsAssistant}
          onAddToKanban={() => setShowAddToKanban(true)}
        />
      </div>

      {/* Dialogs - existing code stays the same */}
      {showAddToKanban && tender && (
        <AddToKanbanDialog 
          open={showAddToKanban}
          onOpenChange={setShowAddToKanban}
          tender={tender}
          onAddSuccess={(boardId: string) => {
            setPopupMessage(t('tenders.kanban.addSuccess'));
            setAddToKanbanSuccess(true);
            setAddedToBoardId(boardId);
            setPopupOpen(true);
          }}
          onAddError={() => {
            setPopupMessage(t('tenders.kanban.addError'));
            setAddToKanbanSuccess(false);
            setPopupOpen(true);
          }}
        />
      )}

      {/* Popup Sukcesu/Błędu */}
      {popupOpen && (
        <Dialog open={popupOpen} onOpenChange={setPopupOpen}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <div className="flex flex-col items-center text-center space-y-4">
                <div className={`rounded-full p-3 ${addToKanbanSuccess ? 'bg-success/15' : 'bg-destructive/15'}`}>
                  {addToKanbanSuccess ? (
                    <CheckCircle2 className="h-8 w-8 text-success" strokeWidth={1.5} />
                  ) : (
                    <AlertCircle className="h-8 w-8 text-destructive" strokeWidth={1.5} />
                  )}
                </div>
                <DialogTitle className="text-lg font-semibold leading-none tracking-tight">
                  {popupMessage}
                </DialogTitle>
              </div>
            </DialogHeader>
            <DialogFooter className="sm:justify-center gap-2">
              {addToKanbanSuccess && addedToBoardId && (
                <Button 
                  onClick={() => {
                    setPopupOpen(false);
                    window.open(`/dashboard/tenders/management/${addedToBoardId}`, "_blank");
                  }}
                  variant="default"
                  className="px-6"
                >
                  {t('tenders.kanban.openBoard')}
                </Button>
              )}
              <Button 
                onClick={() => setPopupOpen(false)}
                variant={addToKanbanSuccess ? "outline" : "default"}
                className="px-6"
              >
                {addToKanbanSuccess ? t('tenders.kanban.stay') : commonT('close')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </TooltipProvider>
  );
}

export default function TenderDetailsPage() {
  return (
    <KanbanProvider>
      <TenderDetailsPageContent />
    </KanbanProvider>
  );
}
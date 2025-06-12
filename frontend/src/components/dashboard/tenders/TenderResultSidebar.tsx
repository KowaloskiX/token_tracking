import React, { useEffect, useRef, useState, useMemo } from 'react';
import { TenderAnalysisResult, TenderAnalysisUpdate } from '@/types/tenders';
import MagicDrawer from '../ExpandableDrawer';
import { Button } from "@/components/ui/button";
import JSZip from 'jszip';
import { 
    FileText, 
    ChevronDown, 
    ListCheck, 
    LibraryBig, 
    Clock, 
    Link as LinkIcon, 
    CheckCircle2,
    Archive,
    AlertCircle,
    XCircle,
    FileDown,
    Building,
    Calendar,
    Percent,
    MapPin,
    Globe,
    Flag,
    MoreHorizontal,
    Download
} from "lucide-react";
import { Card } from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useRouter } from 'next/navigation';
import { Assistant, CreateConversationRequest, FileData } from '@/types';
import { createAssistant } from '@/utils/assistantActions';
import { createConversation } from '@/utils/conversationActions';
import { createFilesWithOpenAIId, enrichFiles } from '@/utils/fileActions';
import Link from 'next/link';
import TenderSourceIcon from './TenderSourceIcon';
import ReactMarkdown, { Components } from 'react-markdown';
import { format } from 'date-fns';
import { 
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useTender } from "@/context/TenderContext";
import { useKanban } from '@/context/KanbanContext';
import { AddToKanbanDialog } from './AddToKanbanDialog';
import { useDashboard } from '@/hooks/useDashboard';
import CommentSection from './CommentSection';
import EditableCriteriaItem from './EditableCriteriaItem';
import { CriteriaAnalysisResult } from '@/types/tenders';
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { DropdownMenuItem } from '@radix-ui/react-dropdown-menu';
import ResultFileItem from './ResultFileItem';
import TenderDetailsSkeleton from './TenderDetailsSkeleton';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

interface TenderResultSidebarProps {
    result: TenderAnalysisResult | null;
    drawerRef?: React.RefObject<{ setVisibility: (value: boolean) => void }>;
    allResults: TenderAnalysisResult[];
    setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
    onFilePreview?: (file: FileData, citationsForFile: string[]) => void;
    tenderBoardStatus?: string | null;
}
interface UpdateSummary {
  update_id: string;
  overall_summary: string;
  file_summaries: Array<{
    filename: string;
    summary: string;
  }>;
}

const TenderResultSidebar: React.FC<TenderResultSidebarProps> = ({ result, drawerRef, allResults, setAllResults, onFilePreview,tenderBoardStatus }) => {
    const [isDownloading, setIsDownloading] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [initialLoad, setInitialLoad] = useState(true);
    const [localStatus, setLocalStatus] = useState<string>('inactive');
    const { updateTenderStatus, setSelectedResult, fetchTenderResultById } = useTender();
    const [resultUpdates, setResultUpdates] = useState<TenderAnalysisUpdate[]>([]);
    const [isLoadingUpdates, setIsLoadingUpdates] = useState(false);
    const [isLoadingFullResult, setIsLoadingFullResult] = useState(false);
    const [showAddToKanban, setShowAddToKanban] = useState(false);
    const [lastFetchedId, setLastFetchedId] = useState<string | null>(null);

    const [popupOpen, setPopupOpen] = useState(false);
    const [popupMessage, setPopupMessage] = useState("");
    const [addToKanbanSuccess, setAddToKanbanSuccess] = useState<boolean | null>(null);
    const [addedToBoardId, setAddedToBoardId] = useState<string | null>(null);
    
    const [updateSummaries, setUpdateSummaries] = useState<UpdateSummary[]>([]);
    const { user } = useDashboard();
    const router = useRouter();

    // Log when component renders with a new result
    useEffect(() => {
        console.log("[TenderSidebar] Component rendered with result:", {
            resultId: result?._id,
            hasFullData: !!result?.criteria_analysis?.length
        });
    }, [result]);

    const updatedResult = result
      ? allResults.find((tender) => tender._id?.toString() === result._id?.toString()) || result
      : null;

    // Log when updatedResult changes
    useEffect(() => {
        console.log("[TenderSidebar] Updated result reference:", {
            resultId: updatedResult?._id,
            hasFullData: !!updatedResult?.criteria_analysis?.length,
            loadingState: isLoadingFullResult
        });
    }, [updatedResult, isLoadingFullResult]);

    // This effect triggers when result changes - critical for first load
    useEffect(() => {
        if (result?._id && result._id !== lastFetchedId) {
            console.log("[TenderSidebar] NEW RESULT DETECTED - forcing fetch:", {
                resultId: result._id,
                hasFullData: !!result?.criteria_analysis?.length
            });
            
            const needsFetch = !result.criteria_analysis || 
                               result.criteria_analysis.length === 0 ||
                               !result.tender_description;
                
            if (needsFetch && !isLoadingFullResult) {
                console.log("[TenderSidebar] IMMEDIATE FETCH for new result:", result._id);
                
                // Set loading state immediately when new tender is selected
                setIsLoadingFullResult(true);
                
                (async () => {
                    try {
                        // Add API request logging
                        console.log(`[TenderSidebar] API REQUEST STARTING: /tender-analysis/${result._id}/details`);
                        
                        // Save fetched ID to prevent duplicate fetches
                        if (result._id) {
                            setLastFetchedId(result._id);
                        }
                        
                        console.time("[TenderSidebar] API fetch duration");
                        const forceResult = await fetchTenderResultById(result._id!);
                        console.timeEnd("[TenderSidebar] API fetch duration");
                        
                        console.log("[TenderSidebar] NEW RESULT fetch completed:", {
                            success: !!forceResult,
                            resultId: result._id,
                            hasData: !!forceResult?.criteria_analysis && Array.isArray(forceResult.criteria_analysis) && forceResult.criteria_analysis.length > 0,
                            criteriaCount: Array.isArray(forceResult?.criteria_analysis) ? forceResult.criteria_analysis.length : 0
                        });
                        
                        if (forceResult) {
                            setAllResults(prev => 
                                prev.map(tender => 
                                    tender._id === forceResult._id ? { ...tender, ...forceResult } : tender
                                )
                            );
                        }
                    } catch (error) {
                        console.error("[TenderSidebar] Failed to fetch new result:", error);
                    } finally {
                        setIsLoadingFullResult(false);
                    }
                })();
            }
        } else if (!result?._id) {
            // Reset loading state when no result is selected
            setIsLoadingFullResult(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [result?._id]);

    // Simplified drawer ref setup that doesn't try to track visibility
    useEffect(() => {
        if (!drawerRef?.current) return;

        const currentRef = drawerRef.current;

        if ((currentRef as any)._isWrapped) return; // already wrapped

        console.log("[TenderSidebar] Wrapping drawer ref setVisibility - FIRST TIME (mount)");

        const originalSetVisibility = currentRef.setVisibility;

        currentRef.setVisibility = (value: boolean) => {
            console.log("[TenderSidebar] Drawer visibility changed to:", value, "for result ID:", updatedResult?._id);
            originalSetVisibility(value);
        };

        (currentRef as any)._isWrapped = true;

        return () => {
            console.log("[TenderSidebar] Unmount cleanup - restoring drawer methods");
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Additional validation to ensure we never get stuck in loading state
    useEffect(() => {
        let resetTimer: NodeJS.Timeout | null = null;
        
        if (isLoadingFullResult) {
            // Safety timeout - if loading state gets stuck for more than 10 seconds, reset it
            resetTimer = setTimeout(() => {
                console.log("[TenderSidebar] TIMEOUT: Loading state was stuck for 10 seconds, resetting");
                setIsLoadingFullResult(false);
            }, 10000);
        }
        
        return () => {
            if (resetTimer) clearTimeout(resetTimer);
        };
    }, [isLoadingFullResult]);

    useEffect(() => {
        if (initialLoad && drawerRef?.current) {
            drawerRef.current.setVisibility(false);
            setInitialLoad(false);
        }
    }, [initialLoad, drawerRef]);

    function exportCriteriaToXls(
        criteria: CriteriaAnalysisResult[],
        fileName = 'criteria_analysis'
      ) {
        const name = updatedResult?.tender_metadata?.name || 'Analysis Report';
        const description = updatedResult?.tender_description || '';
        const headers = ['Kryterium', 'Podsumowanie', 'Spełnione', 'Waga'];
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
          table += `<td>${item.analysis.criteria_met === true ? 'Tak' : item.analysis.criteria_met === false ? 'Nie' : ''}</td>`;
          table += `<td>${item.analysis.weight}</td>`;
          table += '</tr>';
        });
        
        table += '</tbody></table>';
        
        // wrap with UTF-8 declaration
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
        
        // prepend BOM so Excel picks up UTF-8
        const bom = '\uFEFF';
        const blob = new Blob([bom + html], {
          type: 'application/vnd.ms-excel;charset=utf-8'
        });
      
        // download
        const url = URL.createObjectURL(blob);
        const a   = document.createElement('a');
        a.href    = url;
        a.download= `${fileName}.xls`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    const criteriaToExport = allResults.length > 0
        ? allResults[0].criteria_analysis
        : [];
    

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
            
            return await response.json();
        } catch (error) {
            console.error('Error fetching tender updates summary:', error);
            return [];
        }
    };

    useEffect(() => {
        // if there is no ID, bail out
        if (!updatedResult?._id) {
            setUpdateSummaries([]);
            return;
        }

        const tenderId = updatedResult._id;  // here `tenderId` is inferred as `string`

        (async () => {
            const summaries = await fetchTenderUpdatesSummary(tenderId);
            setUpdateSummaries(summaries);
        })();
        }, [updatedResult?._id]);
            
    useEffect(() => {
        if (updatedResult) {
            setLocalStatus(updatedResult.status || 'inactive');
            fetchUpdates(updatedResult);
        } else {
            setResultUpdates([]);
            setLocalStatus('inactive');
            drawerRef?.current?.setVisibility(false);
        }
    }, [updatedResult, drawerRef]);

    const openAsAssistant = async () => {
        if (!updatedResult) return;
        setIsCreating(true);
        try {
            const fileSearchTool = {
                type: "file_search",
                config: {}
            };
            const assistantData: Omit<Assistant, 'id' | 'created_at'> = {
                name: `${updatedResult.tender_metadata?.name || 'Unnamed Tender'}`,
                description: updatedResult.company_match_explanation || '',
                model: "gpt-4-turbo",
                owner_id: updatedResult.user_id,
                system_prompt: `You are a specialized tender analysis assistant for the tender "${updatedResult.tender_metadata?.name || 'Unnamed Tender'}" from ${updatedResult.tender_metadata?.organization || 'Unknown Organization'}.
                The tender involves ${updatedResult.company_match_explanation || 'no specific details'}.
                The submission deadline is ${updatedResult.tender_metadata?.submission_deadline || 'not specified'}.
                Please help the user understand the tender requirements and prepare their submission.`,
                tools: [fileSearchTool],
                shared_with: [],
                temperature: 0.6,
                pinecone_config: updatedResult.pinecone_config,
                tender_pinecone_id: updatedResult.tender_pinecone_id,
                assigned_users: []
            };
        
            const assistant = await createAssistant(assistantData);
            const filesToCreate = updatedResult.uploaded_files
                ?.map(file => ({
                    filename: file.filename,
                    openai_file_id: file.openai_file_id,
                    blob_url: file.blob_url,
                    type: file.filename.split('.').pop()?.toLowerCase() || 'unknown'
                })) || [];
    
            if (filesToCreate.length > 0) {
                await createFilesWithOpenAIId({
                    files: filesToCreate,
                    owner_id: updatedResult.user_id,
                    assistant_id: assistant._id
                });
            }
    
            const conversationData: CreateConversationRequest = {
                user_id: updatedResult.user_id,
                assistant_id: assistant._id,
                initial_message: ``,
                our_rag: updatedResult.pinecone_config ? true : undefined
            };
    
            const conversation = await createConversation(conversationData);
            window.open(`/dashboard/tenders/chat/${conversation._id}`, '_blank');
    
        } catch (error) {
            console.error('Error creating assistant or conversation:', error);
        } finally {
            setIsCreating(false);
        }
    };

    const handleStatusChange = async (value: string) => {
        if (!updatedResult || !updatedResult._id) return;
    
        if (!['inactive', 'active', 'archived'].includes(value)) {
            console.error('Invalid status value:', value);
            return;
        }
        
        const newStatus = value as 'inactive' | 'active' | 'archived';
        setLocalStatus(newStatus);
        
        try {
            await updateTenderStatus(updatedResult._id!, newStatus);
            
            // Update the allResults array with the new status to sync with TendersList
            setAllResults(prevResults => 
                prevResults.map(tender => 
                    tender._id === updatedResult._id
                        ? { ...tender, status: newStatus }
                        : tender
                )
            );
            
            // Update the global selected result if this is the current result
            const updatedTender = { ...updatedResult, status: newStatus };
            setSelectedResult(updatedTender);
        } catch (error) {
            console.error('Error updating tender status:', error);
            setLocalStatus(updatedResult.status || 'inactive');
        }
    };

    const handleCriteriaUpdate = (criteriaName: string, newSummary: string) => {
        if (!updatedResult?._id) return;
        setAllResults((prevAllResults) =>
            prevAllResults.map((tender) => {
                if (tender._id?.toString() === updatedResult._id?.toString()) {
                    return {
                        ...tender,
                        criteria_analysis: tender.criteria_analysis.map((item) =>
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
                }
                return tender;
            })
        );
    };


    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'inactive':
                return <AlertCircle className="h-4 w-4 text-gray-500" />;
            case 'active':
                return <CheckCircle2 className="h-4 w-4 text-green-600/80" />;
            case 'archived':
                return <Archive className="h-4 w-4 text-gray-500" />;
            default:
                return <AlertCircle className="h-5 w-5 text-yellow-500" />;
        }
    };
    
    const getStatusBadge = (status: string, currentTenderBoardStatus: string | null | undefined = tenderBoardStatus) => {
        if (currentTenderBoardStatus) {
            return <Badge variant="outline" className="border-transparent bg-secondary-hover text-primary shadow">{currentTenderBoardStatus}</Badge>;
        }

        switch (status) {
            case 'inactive':
            return <Badge variant="outline" className="border-gray-400 text-gray-600 font-normal">Nieaktywny</Badge>;
            case 'active':
            return <Badge variant="default" className="bg-green-600/80 hover:bg-green-600 font-normal">Aktywny</Badge>;
            case 'archived':
            return <Badge variant="secondary" className="bg-secondary text-primary/70 hover:bg-secondary font-normal">Zarchiwizowany</Badge>;
            default:
            return <Badge variant="outline">Nieznany</Badge>;
        }
        };


    const formatDate = (date: Date): string => {
        try {
            return format(date, "dd.MM.yyyy");
        } catch (e) {
            return "Invalid date";
        }
    };

    const getCriteriaMetColor = (criteria_met?: boolean) => {
        // If undefined (older record), you might decide to fall back on another logic,
        // for example, based on the confidence level or simply show a neutral color.
        if (criteria_met === undefined) {
          return 'bg-gray-500'; // Neutral color for missing info
        }
        return criteria_met ? 'bg-green-600/80' : 'bg-red-400/80';
      };

    const getWeightBadge = (weight: number) => {
        const badgeStyle = 'bg-secondary border-secondary-border border-2 text-primary';
      
        return (
          <Badge 
            variant="outline" 
            className={`${badgeStyle} rounded-md px-2 py-0.5 h-auto font-medium`}
          >
            Waga: {weight}
          </Badge>
        );
    };


    const handlePopupClose = () => {
        setPopupOpen(false);
        if (addedToBoardId) {
            window.open(`/dashboard/tenders/management/${addedToBoardId}`, "_blank");
        }
        setAddedToBoardId(null);
    };

    const handleDownloadAllFiles = async () => {
        if (!updatedResult?.uploaded_files || updatedResult.uploaded_files.length === 0) {
            setPopupMessage('Brak plików do pobrania');
            setPopupOpen(true);
            return;
        }
        setIsDownloading(true);
    
        try {
            const files = updatedResult.uploaded_files;
            const zip = new JSZip();  
            for (const file of files) {
                const downloadUrl = file.blob_url || file.url;
                if (downloadUrl) {
                    const response = await fetch(downloadUrl);
                    const blob = await response.blob();
                    zip.file(file.filename, blob);
                }
            }
    
            const zipBlob = await zip.generateAsync({ type: 'blob' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(zipBlob);
            a.download = `${updatedResult.tender_metadata.name}_files.zip`; 
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (error) {
            console.error('Błąd podczas pobierania plików:', error);
            setPopupMessage('Błąd podczas pobierania plików.');
            setPopupOpen(true);
        } finally {
            setIsDownloading(false);
        }
    };
    
    // Add the components definition for ReactMarkdown similar to ChatMessage.tsx
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

    return (
        <>
            <MagicDrawer 
                ref={drawerRef}
                forceExpanded={false}
                maxWidth={800} 
            >
                <div className="flex flex-col h-full relative w-full overflow-hidden">
                    {/* Show skeleton loader when fetch is in progress or when awaiting full result details */}
                    {isLoadingFullResult || (updatedResult && updatedResult.uploaded_files?.length > 0 && (!updatedResult.criteria_analysis?.length || !updatedResult.tender_description)) ? (
                        <TenderDetailsSkeleton />
                    ) : (
                        <>
                        {updatedResult && (
                            <div className="p-4 sm:p-6 pb-24 overflow-y-auto overflow-x-hidden scrollbar-hide flex-grow space-y-4 sm:space-y-6">
                                <>
                                    <div className='border-b pb-4'>
                                        <div className="flex flex-wrap sm:flex-nowrap justify-between gap-4 sm:gap-8 mb-4">
                                            <div className="flex items-center gap-4">
                                                <div className="border border-neutral-200 p-2 rounded-lg">
                                                    <div className="w-5 h-5 relative">
                                                        <TenderSourceIcon 
                                                            source={updatedResult.source} 
                                                            url={updatedResult.tender_url} 
                                                        />
                                                    </div>
                                                </div>
                                                {updatedResult.tender_url ? (
                                                    <Link 
                                                        href={updatedResult.tender_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-sm sm:text-lg font-semibold hover:underline"
                                                    >
                                                        {updatedResult.tender_metadata?.name || 'Unnamed Tender'}
                                                    </Link>
                                                ) : (
                                                    <span className="text-sm sm:text-lg font-semibold">
                                                        {updatedResult.tender_metadata?.name || 'Unnamed Tender'}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {!updatedResult.uploaded_files?.length && (
                                            <div className="mb-4 p-4 bg-secondary/30 border border-neutral-200 rounded-lg">
                                                <div className="flex items-start gap-3">
                                                    <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
                                                    <div>
                                                        <h4 className="text-sm font-medium text-muted-foreground mb-1">Brak dostępnych plików</h4>
                                                        <p className="text-sm text-muted-foreground">
                                                            Ten przetarg nie posiada plików do pobrania. Sprawdź bezpośrednio źródło przetargu, aby uzyskać dostęp do wymaganych dokumentów.
                                                        </p>
                                                        {updatedResult.tender_url && (
                                                            <Link 
                                                                href={updatedResult.tender_url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="inline-flex items-center gap-1 text-sm text-primary hover:text-primary/80 mt-2 font-medium"
                                                            >
                                                                <LinkIcon className="h-4 w-4" />
                                                                Otwórz źródło przetargu
                                                            </Link>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        
                                        {!updatedResult.uploaded_files?.length && (
                                            <div className="mb-4 p-4 bg-secondary/30 border border-neutral-200 rounded-lg">
                                                <div className="flex items-start gap-3">
                                                    <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
                                                    <div>
                                                        <h4 className="text-sm font-medium text-muted-foreground mb-1">Brak dostępnych plików</h4>
                                                        <p className="text-sm text-muted-foreground">
                                                            Ten przetarg nie posiada plików do pobrania. Sprawdź bezpośrednio źródło przetargu, aby uzyskać dostęp do wymaganych dokumentów.
                                                        </p>
                                                        {updatedResult.tender_url && (
                                                            <Link 
                                                                href={updatedResult.tender_url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="inline-flex items-center gap-1 text-sm text-primary hover:text-primary/80 mt-2 font-medium"
                                                            >
                                                                <LinkIcon className="h-4 w-4" />
                                                                Otwórz źródło przetargu
                                                            </Link>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        
                                        <div className='text-sm tracking-tight text-muted-foreground markdown-content'>
                                            <ReactMarkdown
                                                components={markdownComponents}
                                                remarkPlugins={[remarkGfm, remarkBreaks]}
                                            >
                                                {updatedResult.tender_description? updatedResult.tender_description === "Brak danych." ? "" : updatedResult.tender_description : "Brak opisu. Pliki nie zostały pobrane ze źródła przetargu."}
                                            </ReactMarkdown>
                                        </div>
                                        
                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-6 mt-6">
                                            <div className="flex flex-col gap-1">
                                                <div className="flex items-center gap-2">
                                                    <Building className="h-4 w-4 text-gray-500" />
                                                    <h3 className="text-xs sm:text-sm font-medium text-muted-foreground">Zamawiający</h3>
                                                </div>
                                                <TooltipProvider delayDuration={300}>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <p className="text-xs sm:text-sm truncate">
                                                                {updatedResult.tender_metadata?.organization || 'N/A'}
                                                            </p>
                                                        </TooltipTrigger>
                                                        <TooltipContent side="top" className="max-w-[300px] break-all">
                                                            <p>{updatedResult.tender_metadata?.organization || 'N/A'}</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <div className="flex items-center gap-2">
                                                    <Calendar className="h-4 w-4 text-gray-500" />
                                                    <h3 className="text-xs sm:text-sm font-medium text-muted-foreground">Termin zgłoszenia</h3>
                                                </div>
                                                <p className="text-xs sm:text-sm truncate">
                                                    {updatedResult.tender_metadata?.submission_deadline || 'N/A'}
                                                </p>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <div className="flex items-center gap-2">
                                                    <Percent className="h-4 w-4 text-gray-500" />
                                                    <h3 className="text-xs sm:text-sm font-medium text-muted-foreground">Relewantność</h3>
                                                </div>
                                                <p className="text-xs sm:text-sm truncate">
                                                    {(updatedResult.tender_score * 100).toFixed(1)}%
                                                </p>
                                            </div>
                                        </div>
                                        
                                        {updatedResult.location && (
                                            <div className="mt-4 border-t border-gray-100 pt-4">
                                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 ">
                                                    {updatedResult.location.country && updatedResult.location.country !== "UNKNOWN" && (
                                                        <div className="flex flex-col gap-1">
                                                            <div className="flex items-center gap-2">
                                                                <Globe className="h-4 w-4 text-gray-400" />
                                                                <span className="text-xs sm:text-sm font-medium text-muted-foreground">Kraj</span>
                                                            </div>
                                                            <span className="text-xs sm:text-sm truncate">
                                                                {updatedResult.location.country}
                                                            </span>
                                                        </div>
                                                    )}
                                                    {updatedResult.location.voivodeship && updatedResult.location.voivodeship !== "UNKNOWN" && (
                                                        <div className="flex flex-col gap-1">
                                                            <div className="flex items-center gap-2">
                                                                <Flag className="h-4 w-4 text-gray-400" />
                                                                <span className="text-xs sm:text-sm font-medium text-muted-foreground">Województwo</span>
                                                            </div>
                                                            <span className="text-xs sm:text-sm truncate">
                                                                {updatedResult.location.voivodeship}
                                                            </span>
                                                        </div>
                                                    )}
                                                    {updatedResult.location.city && updatedResult.location.city !== "UNKNOWN" && (
                                                        <div className="flex flex-col gap-1">
                                                            <div className="flex items-center gap-2">
                                                                <MapPin className="h-4 w-4 text-gray-400" />
                                                                <span className="text-xs sm:text-sm font-medium text-muted-foreground">Miejscowość</span>
                                                            </div>
                                                            <span className="text-xs sm:text-sm truncate">
                                                                {updatedResult.location.city}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex items-center gap-2 mb-4 bg-secondary/30 p-3 rounded-lg border border-neutral-200">
                                        <div className="flex items-center gap-2">
                                            {getStatusIcon(localStatus)}
                                            <Label htmlFor="tender-status" className="text-sm font-normal">
                                                Status:
                                            </Label>
                                        </div>
                                        <div className="flex-grow ml-2">
                                            <Select 
                                                value={localStatus} 
                                                onValueChange={handleStatusChange}
                                            >
                                                <SelectTrigger id="tender-status" className="h-8 w-48 bg-white/20 hover:bg-secondary-hover">
                                                    <SelectValue placeholder="Wybierz status" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="inactive">Nieaktywny</SelectItem>
                                                    <SelectItem value="active">Aktywny</SelectItem>
                                                    <SelectItem value="archived">Zarchiwizowany</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div>
                                            {getStatusBadge(localStatus)}
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                    <h3 className="font-semibold">Kryteria</h3>
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                        <Button variant="ghost" size="sm">
                                            <MoreHorizontal className="h-4 w-4" />
                                        </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                        <DropdownMenuItem 
                                        onClick={() => {
                                            const fullName = updatedResult?.tender_metadata?.name || 'Przetarg';
                                            
                                            const words = fullName.split(' ');
                                            const firstFourWords = words.slice(0, 5).join(' ');
                                            
                                            const trimmedName = firstFourWords.length > 100 
                                              ? firstFourWords.substring(0, 100) 
                                              : firstFourWords;
                                            
                                            const fileName = `${trimmedName}_kryteria`;
                                            exportCriteriaToXls(updatedResult?.criteria_analysis, fileName);
                                          }}
                                            disabled={!updatedResult?.criteria_analysis?.length}
                                            className="flex items-center gap-2 cursor-pointer outline-none p-2 text-sm"
                                            >
                                            <FileDown className="h-4 w-4" />
                                            <span>Eksportuj kryteria do Excel</span>
                                        </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                    </div>
                                        <div className="space-y-2">
                                            {isLoadingFullResult && (
                                                <div className="flex items-center justify-center p-4 bg-muted/20 rounded-md my-2 border border-muted">
                                                    <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin mr-2" />
                                                    <span className="text-sm text-muted-foreground">Loading full tender details...</span>
                                                </div>
                                            )}
                                            
                                            {(!updatedResult?.criteria_analysis || updatedResult.criteria_analysis.length === 0) && !isLoadingFullResult && (
                                                <div className="flex flex-col items-center justify-center p-4 bg-muted/20 rounded-md my-2 border border-muted">
                                                    {!updatedResult.uploaded_files?.length ? (
                                                        <p className="text-sm text-muted-foreground text-center">
                                                            Brak analizy kryteriów. Pliki nie zostały pobrane ze źródła przetargu.
                                                        </p>
                                                    ) : (
                                                        <Button
                                                            onClick={async () => {
                                                                if (!updatedResult?._id) return;
                                                                setIsLoadingFullResult(true);
                                                                try {
                                                                    const fullResult = await fetchTenderResultById(updatedResult._id!);
                                                                    
                                                                    if (fullResult) {
                                                                        setAllResults(prev => 
                                                                            prev.map(tender => 
                                                                                tender._id === fullResult._id ? { ...tender, ...fullResult } : tender
                                                                            )
                                                                        );
                                                                    }
                                                                } catch (error) {
                                                                    console.error('Error fetching full tender details:', error);
                                                                } finally {
                                                                    setIsLoadingFullResult(false);
                                                                }
                                                            }}
                                                            variant="outline"
                                                            size="sm"
                                                            disabled={isLoadingFullResult}
                                                        >
                                                            <Download className="w-4 h-4 mr-2" />
                                                            Pobierz pełne dane
                                                        </Button>
                                                    )}
                                                </div>
                                            )}

                                            {updatedResult.criteria_analysis?.map((item, index) => {
                                                // Determine rendering logic based on exclude_from_score
                                                const shouldShowWeight = item.exclude_from_score === false;

                                                // Collect all citations from all criteria
                                                const allCitations = updatedResult.criteria_analysis?.flatMap(criteria => 
                                                    criteria.citations || []
                                                ) || [];

                                                return (
                                                    <Collapsible key={index}>
                                                        <div className="group">
                                                            <CollapsibleTrigger asChild>
                                                                <div 
                                                                    data-state="closed"
                                                                    className="flex overflow-hidden items-center gap-2 py-2 px-4 transition-all duration-200 border border-secondary-border shadow-sm bg-secondary/30 w-full hover:bg-secondary rounded-t-lg rounded-b-lg data-[state=open]:rounded-b-none cursor-pointer"
                                                                >
                                                                    {/* Icon - fixed width */}
                                                                    <Card className="bg-secondary p-2 relative rounded-md flex-shrink-0">
                                                                        {/* Conditional dot rendering */}
                                                                        <div className={`absolute w-2 h-2 rounded-full ${getCriteriaMetColor(item.analysis.criteria_met)} right-0 top-0 transform translate-x-1 -translate-y-1`} />
                                                                        <ListCheck className="w-4 h-4 shrink-0 text-muted-foreground" />
                                                                    </Card>
                                                                    
                                                                    {/* Criteria text - flexible but constrained */}
                                                                    <TooltipProvider delayDuration={300}>
                                                                        <Tooltip>
                                                                            <TooltipTrigger asChild>
                                                                                <div className="flex-1 min-w-0">
                                                                                    <p className="text-sm font-medium truncate text-left">
                                                                                        {item.criteria}
                                                                                    </p>
                                                                                </div>
                                                                            </TooltipTrigger>
                                                                            <TooltipContent side="top" className="max-w-[300px] break-all">
                                                                                <div className="markdown-content">
                                                                                    <ReactMarkdown
                                                                                        remarkPlugins={[remarkGfm, remarkBreaks]}
                                                                                        components={markdownComponents}
                                                                                    >
                                                                                        {item.criteria}
                                                                                    </ReactMarkdown>
                                                                                </div>
                                                                            </TooltipContent>
                                                                        </Tooltip>
                                                                    </TooltipProvider>
                                                                    
                                                                    {/* Weight badge - fixed position when present */}
                                                                    {shouldShowWeight && (
                                                                        <div className="flex-shrink-0 ml-2">
                                                                            {getWeightBadge(item.analysis.weight)}
                                                                        </div>
                                                                    )}
                                                                    
                                                                    {/* Chevron - always fixed position */}
                                                                    <ChevronDown 
                                                                        className="w-4 h-4 flex-shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180 ml-2" 
                                                                    />
                                                                </div>
                                                            </CollapsibleTrigger>
                                                        </div>
                                                        <CollapsibleContent>
                                                            <div className="border border-t-0 border-secondary-border bg-secondary/30 px-4 py-3 rounded-b-xl">
                                                                <div className="flex gap-4">
                                                                    <div className="" />
                                                                    <EditableCriteriaItem
                                                                        resultId={updatedResult._id?.toString() ?? ""}
                                                                        criteriaItem={item}
                                                                        markdownComponents={markdownComponents}
                                                                        uploadedFiles={updatedResult.uploaded_files}
                                                                        onUpdate={(newSummary) => {
                                                                            handleCriteriaUpdate(item.criteria, newSummary);
                                                                        }}
                                                                        onFilePreview={onFilePreview}
                                                                        allCitations={allCitations}
                                                                    />
                                                                </div>
                                                            </div>
                                                        </CollapsibleContent>
                                                    </Collapsible>
                                                );
                                            }) || (
                                                <p className="text-sm text-muted-foreground">Brak kryteriów</p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        <h3 className="font-semibold">Aktualizacje</h3>
                                        {isLoadingUpdates ? (
                                            <div className="text-sm text-muted-foreground p-2 flex items-center">
                                                <span className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin mr-2" />
                                                Ładowanie aktualizacji...
                                            </div>
                                        ) : updatedResult && resultUpdates.length > 0 ? (
                                            <Accordion type="multiple" className="w-full">
                                                {resultUpdates.map((update) => (
                                                    <AccordionItem
                                                        key={`update-${update._id}`}
                                                        value={`update-${update._id}`}
                                                        className="border rounded-md mb-2 border-neutral-200 overflow-hidden"
                                                    >
                                                        <AccordionTrigger className="py-2 px-4 hover:no-underline hover:bg-secondary-hover">
                                                        <div className="flex items-center gap-2 text-sm w-full">
                                                            <Card className="bg-secondary p-2 rounded-md flex-shrink-0">
                                                            <Clock className="w-4 h-4 shrink-0 text-muted-foreground" />
                                                            </Card>
                                                            <div className="flex flex-col text-left">
                                                            <span className="font-medium">
                                                                Aktualizacja: {formatDate(new Date(update.update_date))}
                                                            </span>
                                                            </div>
                                                        </div>
                                                        </AccordionTrigger>
                                                        <AccordionContent className="px-4 py-3 bg-secondary/30">
                                                        <div className="space-y-2 pl-10">
                                                            {update.updated_files && update.updated_files.length > 0 ? (
                                                            update.updated_files.map((file, fileIndex) => (
                                                                <div
                                                                key={`update-${update._id}-file-${fileIndex}`}
                                                                className="flex items-center justify-between p-2 rounded-md bg-background hover:bg-secondary border border-neutral-200"
                                                                >
                                                                <div className="flex items-center gap-2">
                                                                    <FileText size={16} className="text-muted-foreground" />
                                                                    <span className="text-sm truncate max-w-[180px]">
                                                                    {file.filename}
                                                                    </span>
                                                                </div>
                                                                <Badge variant="outline" className="text-xs">
                                                                    {file.filename.split('.').pop()?.toUpperCase() || "DOC"}
                                                                </Badge>
                                                                </div>
                                                            ))
                                                ) : (
                                                    <div className="text-sm text-muted-foreground italic">Brak plików w tej aktualizacji</div>
                                                )}

                                                {update.update_link && (
                                                <Link
                                                    href={update.update_link}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="flex items-center gap-1 text-sm text-primary hover:underline mt-2 py-1"
                                                >
                                                    <LinkIcon size={14} />
                                                    <span>Źródło aktualizacji</span>
                                                </Link>
                                                )}
                                                {(() => {
                                                const summary = updateSummaries.find(s => s.update_id === update._id);
                                                return summary ? (
                                                    <>
                                                    {summary.overall_summary && (
                                                        <div className="mt-4">
                                                        <h4 className="font-medium text-sm">Podsumowanie aktualizacji</h4>
                                                        <ReactMarkdown className="prose-sm whitespace-pre-line">
                                                            {summary.overall_summary}
                                                        </ReactMarkdown>
                                                        </div>
                                                    )}
                                                    {summary.file_summaries.length > 0 && (
                                                    <div className="mt-2 pl-10">
                                                        <h4 className="font-medium text-sm">Podsumowania plików</h4>
                                                        <ul className="list-disc list-inside text-sm space-y-1">
                                                        {summary.file_summaries.map((fs, idx) => (
                                                            <li key={idx}>
                                                            <span className="font-medium">{fs.filename}:</span>{" "}
                                                            {fs.summary}
                                                            </li>
                                                        ))}
                                                        </ul>
                                                    </div>
                                                    )}
                                                    </>
                                                ) : null;
                                                })()}
                                            </div>
                                            </AccordionContent>
                                        </AccordionItem>
                                        ))}
                                            </Accordion>
                                        ) : (
                                            <div className="text-sm text-muted-foreground italic p-2">
                                                Brak aktualizacji dla tego przetargu
                                            </div>
                                        )}
                                    </div>
                                    {updatedResult.uploaded_files && updatedResult.uploaded_files.length > 0 ? (
                                        <>
                                            <div className="space-y-4">
                                                <h3 className="font-semibold">Files</h3>
                                                <div className="flex flex-wrap gap-2">
                                                    {updatedResult.uploaded_files.map((file, index) => (
                                                        <ResultFileItem key={index} file={file} />
                                                    ))}
                                                </div>
                                            </div>
                                            <Button
                                                className="w-full mt-4"
                                                onClick={handleDownloadAllFiles}
                                                disabled={isDownloading || !updatedResult.uploaded_files || updatedResult.uploaded_files.length === 0}
                                            >
                                                {isDownloading ? 'Pobieranie...' : 'Pobierz wszystkie pliki'}
                                            </Button>
                                        </>
                                    ) : (
                                        <div className="space-y-4">
                                            <h3 className="font-semibold">Pliki</h3>
                                            <p className="text-sm text-muted-foreground">Brak dostępnych plików</p>
                                        </div>
                                    )}

                                    {updatedResult?._id ? (
                                        <div className="space-y-4">
                                            <CommentSection 
                                                tenderId={updatedResult._id} 
                                                refreshTrigger={true}
                                            />
                                        </div>
                                    ) : (
                                        <div className="space-y-4">
                                            <h3 className="font-semibold">Komentarze</h3>
                                            <p className="text-sm text-muted-foreground">Nie można załadować komentarzy - brak identyfikatora przetargu</p>
                                        </div>
                                    )}

                                    
                                </>
                            </div>
                        )}
                        {!updatedResult && (
                            <div className="flex items-center justify-center h-[80svh] text-muted-foreground">
                                <div className="text-center space-y-2">
                                    <p className="text-lg font-medium">Nie wybranego przetargu</p>
                                    <p className="text-sm">Wybierz przetarg żeby wyświetlić szczegóły</p>
                                </div>
                            </div>
                        )}
                        </>
                    )}

                    <div className="sticky bottom-0 w-full p-4 sm:p-6 bg-background border-t border-neutral-200 mt-auto z-10">
                        <div className="flex flex-col gap-2">
                            <Button 
                                className="w-full text-white transition-colors"
                                disabled={isLoadingFullResult || !updatedResult || isCreating || localStatus === 'archived' || !updatedResult.uploaded_files?.length}
                                onClick={openAsAssistant}
                            >
                                {isCreating ? (
                                    <>
                                        <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                                        Tworzenie projektu...
                                    </>
                                ) : (
                                    <>
                                        <LibraryBig strokeWidth={2.2} className="w-5 h-5 mr-2" />
                                        Otwórz jako nowy projekt
                                    </>
                                )}
                            </Button>
                            {!isLoadingFullResult && localStatus === 'active' && (
                                <Button
                                    variant="outline"
                                    className="w-full"
                                    onClick={() => setShowAddToKanban(true)}
                                    disabled={!updatedResult}
                                >
                                    <ListCheck className="mr-2 h-4 w-4" />
                                    Dodaj do tablicy Kanban
                                </Button>
                            )}
                        </div>
                    </div>
                </div>
            </MagicDrawer>
            {showAddToKanban && updatedResult && (
                <AddToKanbanDialog 
                    open={showAddToKanban}
                    onOpenChange={setShowAddToKanban}
                    tender={updatedResult}
                    onAddSuccess={(boardId: string) => {
                        setPopupMessage("Przetarg został pomyślnie dodany do tablicy.");
                        setAddToKanbanSuccess(true);
                        setAddedToBoardId(boardId);
                        setPopupOpen(true);
                    }}
                    onAddError={() => {
                        setPopupMessage("Wystąpił błąd podczas dodawania przetargu do tablicy.");
                        setAddToKanbanSuccess(false);
                        setPopupOpen(true);
                    }}
                />
            )}

            {popupOpen && (
                <Dialog open={popupOpen} onOpenChange={setPopupOpen}>
                    <DialogContent className="sm:max-w-[425px]">
                        <DialogHeader>
                            <div className="flex flex-col items-center text-center space-y-4">
                                <div className={`rounded-full p-3 ${addToKanbanSuccess ? 'bg-success/15' : 'bg-destructive/15'}`}>
                                    {addToKanbanSuccess ? (
                                        <CheckCircle2 className="h-8 w-8 text-success" strokeWidth={1.5} />
                                    ) : (
                                        <XCircle className="h-8 w-8 text-destructive" strokeWidth={1.5} />
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
                                    onClick={handlePopupClose}
                                    variant="default"
                                    className="px-6"
                                >
                                    Otwórz tablicę
                                </Button>
                            )}
                            <Button 
                                onClick={() => setPopupOpen(false)}
                                variant={addToKanbanSuccess ? "outline" : "default"}
                                className="px-6"
                            >
                                {addToKanbanSuccess ? "Zostań" : "Zamknij"}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
        </>
    );
};

export default TenderResultSidebar;
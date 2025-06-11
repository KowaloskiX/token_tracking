import React, { useEffect, useRef, useState } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from '@/components/ui/textarea';
import { Pencil, Quote, FileText, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Citation } from '@/types/tenders';
import { Badge } from "@/components/ui/badge";
import { FileData } from '@/types';
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface EditableCriteriaItemProps {
    resultId: string;
    criteriaItem: any; 
    onUpdate?: (newSummary: string) => void;
    markdownComponents?: Components;
    uploadedFiles?: FileData[];
    onFilePreview?: (file: FileData, citationsForFile: string[]) => void;
    allCitations?: Citation[];
}

const EditableCriteriaItem: React.FC<EditableCriteriaItemProps> = ({ 
    resultId, 
    criteriaItem, 
    onUpdate,
    markdownComponents,
    uploadedFiles = [],
    onFilePreview,
    allCitations = []
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [summaryText, setSummaryText] = useState(criteriaItem.analysis.summary);
    const [isSaving, setIsSaving] = useState(false);
    const [expandedCitations, setExpandedCitations] = useState<Set<number>>(new Set());
    const [citationsSectionExpanded, setCitationsSectionExpanded] = useState(false);
    const t = useTendersTranslations();
    const commonT = useCommonTranslations();

    const textAreaRef = useRef<HTMLTextAreaElement | null>(null);

    useEffect(() => {
        setSummaryText(criteriaItem.analysis.summary);
    }, [criteriaItem.analysis.summary]);

    useEffect(() => {
        if (isEditing && textAreaRef.current) {
        textAreaRef.current.style.height = "auto"
        textAreaRef.current.style.height = `${textAreaRef.current.scrollHeight}px`
        }
    }, [summaryText, isEditing])

    const handleSave = async () => {
        setIsSaving(true);
        try {
            const token = localStorage.getItem("token");
            if (!token) {
                throw new Error("Authentication token not found.");
            }
            const response = await fetch(
                `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-results/${resultId}/edit-criteria/${encodeURIComponent(criteriaItem.criteria)}`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({ summary: summaryText })
                }
            );
            
            if (!response.ok) {
                throw new Error("Failed to update criteria");
            }
            
            setIsEditing(false);
            if (onUpdate) {
                onUpdate(summaryText);
            }
        } catch (error) {
            console.error("Error updating criteria:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancel = () => {
        setSummaryText(criteriaItem.analysis.summary);
        setIsEditing(false);
    };

    const toggleCitationExpansion = (index: number) => {
        setExpandedCitations(prev => {
            const newSet = new Set(prev);
            if (newSet.has(index)) {
                newSet.delete(index);
            } else {
                newSet.add(index);
            }
            return newSet;
        });
    };

    const findMatchingFile = (citationSource: string): FileData | undefined => {
        if (!citationSource) return undefined;
        
        // Helper function to normalize filename for comparison
        const normalizeFilename = (filename: string): string => {
            return filename
                .normalize('NFKD')
                .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
                .replace(/[^A-Za-z0-9._-]/g, '_') // Replace special chars with underscore
                .replace(/^_+|_+$/g, '') // Remove leading/trailing underscores
                .toLowerCase();
        };
        
        const normalizedSource = normalizeFilename(citationSource);
        
        return uploadedFiles.find(file => {
            const normalizedFilename = normalizeFilename(file.filename);
            
            // Strategy 1: Exact match on original filename
            if (file.filename === citationSource) return true;
            
            // Strategy 2: Exact match on normalized filenames
            if (normalizedFilename === normalizedSource) return true;
            
            // Strategy 3: Source contains filename (partial match)
            if (file.filename.includes(citationSource)) return true;
            
            // Strategy 4: Filename contains source (reverse partial match)
            if (citationSource.includes(file.filename)) return true;
            
            // Strategy 5: Normalized partial matching
            if (normalizedFilename.includes(normalizedSource) || 
                normalizedSource.includes(normalizedFilename)) return true;
            
            return false;
        });
    };

    const handleFileClick = async (file: FileData) => {
        if (onFilePreview) {
            // Get citations that reference this file from CURRENT criteria only
            const citationsForFile = citations
                .filter(citation => citation.source === file.filename)
                .map(citation => citation.text);
            
            // Determine proper file type from filename extension
            const getFileTypeFromFilename = (filename: string): string => {
                const extension = filename.split('.').pop()?.toLowerCase();
                
                // Map common extensions to supported types
                const extensionMap: Record<string, string> = {
                    'pdf': 'pdf',
                    'doc': 'doc',
                    'docx': 'docx',
                    'odt': 'odt',
                    'txt': 'txt',
                    'rtf': 'txt', // Treat RTF as text
                    'html': 'txt',
                    'htm': 'txt'
                };
                
                return extensionMap[extension || ''] || extension || 'unknown';
            };
            
            // Create a file object with corrected type for preview
            const fileWithCorrectType: FileData = {
                ...file,
                type: getFileTypeFromFilename(file.filename)
            };
            
            onFilePreview(fileWithCorrectType, citationsForFile);
        } else {
            // Fallback to download if preview handler not provided
            const fileDownloadUrl = file.blob_url || file.url;
            if (!fileDownloadUrl) return;
            
            try {
                const response = await fetch(fileDownloadUrl);
                if (!response.ok) throw new Error("File not found");
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = file.filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            } catch (err) {
                alert(t('tenders.files.downloadError'));
            }
        }
    };

    const truncateText = (text: string, maxLength: number = 150): string => {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    };

    const truncateKeyword = (keyword: string, maxLength: number = 15): string => {
        if (keyword.length <= maxLength) return keyword;
        return keyword.substring(0, maxLength) + '...';
    };

    const truncateSource = (source: string, maxLength: number = 35): string => {
        if (source.length <= maxLength) return source;
        return source.substring(0, maxLength) + '...';
    };

    // Default markdown components if none provided - improved formatting to match ChatMessage
    const defaultComponents: Components = {
        p: ({ children }) => <p className="my-1 leading-relaxed whitespace-pre-line">{children}</p>,
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
            <ul className="list-disc pl-4 my-0.5 space-y-0 !leading-tight">
                {children}
            </ul>
        ),
        ol: ({ children }) => (
            <ol className="list-decimal pl-4 my-0.5 space-y-0 !leading-tight">
                {children}
            </ol>
        ),
        li: ({ children }) => (
            <li className="my-0 !leading-tight">
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
    };

    const citations: Citation[] = criteriaItem.citations || [];

    return (
        <div className="flex flex-col w-full">
          {isEditing ? (
            <>
              <Textarea
                    ref={textAreaRef}
                    className="border w-full p-2 rounded focus:outline-none resize-none overflow-hidden"
                    value={summaryText}
                    onChange={(e) => setSummaryText(e.target.value)}
                    rows={1}
                />
              <div className="mt-2 flex gap-2 justify-end">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? t('tenders.criteria.saving') : commonT('save')}
                </Button>
                <Button variant="outline" onClick={handleCancel}>
                  {commonT('cancel')}
                </Button>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap items-end justify-end">
              <div className="w-full flex-grow space-y-3">
                <div className="markdown-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={markdownComponents || defaultComponents}
                  >
                    {summaryText}
                  </ReactMarkdown>
                </div>

                {citations.length > 0 && (
                  <Collapsible open={citationsSectionExpanded} onOpenChange={setCitationsSectionExpanded}>
                    <div className="border-t pt-3">
                      <div className={`bg-secondary/40 border rounded-lg overflow-hidden ${citationsSectionExpanded ? '' : 'hover:bg-secondary/50'} transition-colors`}>
                        <CollapsibleTrigger asChild>
                          <div className="flex items-center gap-3 cursor-pointer p-3 transition-colors group">
                            <Card className="bg-secondary p-2 relative rounded-md shrink-0">
                              <Quote className="h-4 w-4 shrink-0 text-muted-foreground" />
                            </Card>
                            <div className="flex items-center justify-between flex-grow">
                              <span className="text-sm font-medium text-muted-foreground">
                                {t('tenders.criteria.viewCitations')}
                              </span>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">
                                  {citations.length}
                                </Badge>
                                <ChevronDown 
                                  className={`w-4 h-4 shrink-0 text-muted-foreground transition-transform duration-200 ${citationsSectionExpanded ? 'rotate-180' : ''}`}
                                />
                              </div>
                            </div>
                          </div>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <div className="px-3 pb-3 space-y-2 border-t border-secondary-border/50">
                            {citations.map((citation, idx) => {
                              const isExpanded = expandedCitations.has(idx);
                              const matchingFile = findMatchingFile(citation.source || '');
                              const displayText = isExpanded ? citation.text : truncateText(citation.text);
                              const shouldShowExpand = citation.text.length > 150;

                              return (
                                <div key={idx} className="bg-background shadow-sm border rounded-md p-3">
                                  <div className="text-sm text-foreground leading-relaxed mb-2">
                                    &ldquo;{displayText}&rdquo;
                                    {shouldShowExpand && (
                                      <button
                                        onClick={() => toggleCitationExpansion(idx)}
                                        className="ml-2 inline-flex items-center gap-1 text-xs text-primary hover:text-primary-hover transition-colors"
                                      >
                                        {isExpanded ? (
                                          <>
                                            <ChevronUp className="h-3 w-3" />
                                            {t('tenders.criteria.collapse')}
                                          </>
                                        ) : (
                                          <>
                                            <ChevronDown className="h-3 w-3" />
                                            {t('tenders.criteria.expand')}
                                          </>
                                        )}
                                      </button>
                                    )}
                                  </div>
                                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                                    <div className="flex items-center gap-1">
                                      <FileText className="h-3 w-3" />
                                      {matchingFile ? (
                                        <button
                                          onClick={() => handleFileClick(matchingFile)}
                                          className="flex items-center text-left gap-1 text-primary hover:text-primary-hover hover:underline transition-colors"
                                          title={citation.source || t('tenders.criteria.unknownSource')}
                                        >
                                          <span className="truncate whitespace-nowrap">
                                            {truncateSource(citation.source || t('tenders.criteria.unknownSource'))}
                                          </span>
                                          <ExternalLink className="h-3 w-3 flex-shrink-0" />
                                        </button>
                                      ) : (
                                        <span>{citation.source || t('tenders.criteria.unknownSource')}</span>
                                      )}
                                    </div>
                                    {citation.keyword && (
                                      <span 
                                        className="text-xs bg-accent/20 text-accent-foreground px-2 py-0.5 rounded font-medium border border-accent/30 cursor-help truncate max-w-24 inline-block" 
                                        title={citation.keyword}
                                      >
                                        {truncateKeyword(citation.keyword)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </CollapsibleContent>
                      </div>
                    </div>
                  </Collapsible>
                )}
              </div>
              <Button className='bg-transparent border-none p-0 hover:bg-transparent hover:text-primary-hover' variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                <Pencil />
              </Button>
            </div>
          )}
        </div>
    );
};

export default EditableCriteriaItem;
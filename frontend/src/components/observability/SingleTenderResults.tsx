"use client"
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Copy, 
  ExternalLink, 
  Calendar, 
  Building, 
  MapPin, 
  Globe,
  Flag,
  Percent,
  ListCheck,
  ChevronDown,
  Clock,
  FileText,
  Link as LinkIcon,
  Download,
  AlertCircle,
  CheckCircle2,
  Archive
} from 'lucide-react';
import { SingleTenderAnalysisResponse } from '@/types/observability';
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { useMemo, useState } from 'react';
import TenderSourceIcon from '../dashboard/tenders/TenderSourceIcon';
import Link from 'next/link';
import JSZip from 'jszip';

interface SingleTenderResultsProps {
  results: SingleTenderAnalysisResponse | null;
  onCopyText: (text: string) => void;
}

export function SingleTenderResults({ results, onCopyText }: SingleTenderResultsProps) {
  const [isDownloading, setIsDownloading] = useState(false);

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

  const getCriteriaMetColor = (criteria_met?: boolean) => {
    if (criteria_met === undefined) {
      return 'bg-gray-500';
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
        Weight: {weight}
      </Badge>
    );
  };

  const handleDownloadAllFiles = async () => {
    const tender = results?.result;
    if (!tender?.uploaded_files || tender.uploaded_files.length === 0) {
      return;
    }

    setIsDownloading(true);
    try {
      const files = tender.uploaded_files;
      const zip = new JSZip();
      
      for (const file of files) {
        const downloadUrl = file.blob_url || file.url;
        if (downloadUrl) {
          try {
            const response = await fetch(downloadUrl);
            const blob = await response.blob();
            zip.file(file.filename, blob);
          } catch (error) {
            console.error(`Failed to download ${file.filename}:`, error);
          }
        }
      }

      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tender.tender_metadata?.name || 'tender_analysis'}_files.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download error:', error);
    } finally {
      setIsDownloading(false);
    }
  };

  if (!results) {
    return (
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Analysis Results</CardTitle>
          <CardDescription>
            Results will appear here after running an analysis
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-muted-foreground">
            No analysis results. Run a single tender analysis to see results here.
          </div>
        </CardContent>
      </Card>
    );
  }

  const tender = results.result;
  if (!tender) {
    return (
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Analysis Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-red-500">
            Analysis completed but no tender data was returned.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="lg:col-span-2 space-y-6">
      {/* Header Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="border border-neutral-200 p-2 rounded-lg">
                <div className="w-5 h-5 relative">
                  <TenderSourceIcon 
                    source={tender.source || tender.tender_metadata?.source || 'unknown'} 
                    url={tender.tender_url || ''} 
                  />
                </div>
              </div>
              <div>
                <CardTitle className="text-lg">
                  {tender.tender_url ? (
                    <Link 
                      href={tender.tender_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {'Analysis'}
                    </Link>
                  ) : (
                    'Analysis'
                  )}
                </CardTitle>
                <CardDescription>
                  ID: {tender._id || 'N/A'}
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onCopyText(tender._id || 'No ID available')}
              >
                <Copy className="h-4 w-4 mr-1" />
                Copy ID
              </Button>
              {tender.tender_url && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(tender.tender_url, '_blank')}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Open Tender
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Tender Description */}
          <div className="text-sm tracking-tight text-muted-foreground markdown-content">
            <ReactMarkdown
              components={markdownComponents}
              remarkPlugins={[remarkGfm, remarkBreaks]}
            >
              {tender.tender_description || 'No description available'}
            </ReactMarkdown>
          </div>

          {/* Information Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-medium text-muted-foreground">Country</h3>
              </div>
              <span className="text-sm truncate">
                {tender.location?.country && tender.location.country !== "UNKNOWN" 
                  ? tender.location.country 
                  : 'N/A'}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Flag className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-medium text-muted-foreground">Voivodeship</h3>
              </div>
              <span className="text-sm truncate">
                {tender.location?.voivodeship && tender.location.voivodeship !== "UNKNOWN" 
                  ? tender.location.voivodeship 
                  : 'N/A'}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-medium text-muted-foreground">City</h3>
              </div>
              <span className="text-sm truncate">
                {tender.location?.city && tender.location.city !== "UNKNOWN" 
                  ? tender.location.city 
                  : 'N/A'}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Percent className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-medium text-muted-foreground">Relevance Score</h3>
              </div>
              <span className="text-sm truncate">
                {tender.tender_score !== undefined ? (
                  `${(tender.tender_score * 100).toFixed(1)}% - ${tender.tender_score >= 0.7 ? "Highly Relevant" : 
                   tender.tender_score >= 0.5 ? "Moderately Relevant" : "Low Relevance"}`
                ) : (
                  'N/A'
                )}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Criteria Analysis Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListCheck className="h-5 w-5" />
            Criteria Analysis
          </CardTitle>
          <CardDescription>
            Detailed analysis of tender requirements and compliance
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tender.criteria_analysis && tender.criteria_analysis.length > 0 ? (
            <div className="space-y-2">
              {tender.criteria_analysis.map((item, index) => {
                const shouldShowWeight = item.exclude_from_score === false && 
                                       item.analysis?.weight !== undefined;

                return (
                  <Collapsible key={index}>
                    <div className="group">
                      <CollapsibleTrigger asChild>
                        <div 
                          data-state="closed"
                          className="flex overflow-hidden items-center gap-2 py-2 px-4 transition-all duration-200 border border-secondary-border shadow-sm bg-secondary/30 w-full hover:bg-secondary rounded-t-lg rounded-b-lg data-[state=open]:rounded-b-none cursor-pointer"
                        >
                          {/* Icon with status dot */}
                          <Card className="bg-secondary p-2 relative rounded-md flex-shrink-0">
                            <div className={`absolute w-2 h-2 rounded-full ${getCriteriaMetColor(item.analysis?.criteria_met)} right-0 top-0 transform translate-x-1 -translate-y-1`} />
                            <ListCheck className="w-4 h-4 shrink-0 text-muted-foreground" />
                          </Card>
                          
                          {/* Criteria text */}
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
                          
                          {/* Weight badge */}
                          {shouldShowWeight && item.analysis && (
                            <div className="flex-shrink-0 ml-2">
                              {getWeightBadge(item.analysis.weight!)}
                            </div>
                          )}
                          
                          {/* Chevron */}
                          <ChevronDown 
                            className="w-4 h-4 flex-shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180 ml-2" 
                          />
                        </div>
                      </CollapsibleTrigger>
                    </div>
                    <CollapsibleContent>
                      <div className="border border-t-0 border-secondary-border bg-secondary/30 px-4 py-3 rounded-b-xl">
                        <div className="space-y-3">
                          {/* Analysis summary */}
                          {item.analysis?.summary && (
                            <div>
                              <h4 className="text-sm font-medium mb-2">Analysis</h4>
                              <div className="text-sm text-muted-foreground markdown-content">
                                <ReactMarkdown
                                  components={markdownComponents}
                                  remarkPlugins={[remarkGfm, remarkBreaks]}
                                >
                                  {item.analysis.summary}
                                </ReactMarkdown>
                              </div>
                            </div>
                          )}

                          {/* Citations */}
                          {item.citations && item.citations.length > 0 && (
                            <div>
                              <h4 className="text-sm font-medium mb-2">Citations</h4>
                              <div className="space-y-2">
                                {item.citations.map((citation, citationIndex) => (
                                  <div key={citationIndex} className="text-xs bg-muted p-2 rounded border-l-2 border-primary/30">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="font-medium text-primary">
                                        {citation.source}
                                      </span>
                                      {citation.keyword && (
                                        <Badge variant="outline" className="text-xs border-primary/20 text-primary/80">
                                          {citation.keyword}
                                        </Badge>
                                      )}
                                    </div>
                                    <ReactMarkdown
                                      components={markdownComponents}
                                      remarkPlugins={[remarkGfm, remarkBreaks]}
                                    >
                                      {citation.text}
                                    </ReactMarkdown>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Criteria met status */}
                          {item.analysis?.criteria_met !== undefined && (
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">Status:</span>
                              <Badge 
                                variant={item.analysis.criteria_met ? "default" : "destructive"}
                                className="text-xs"
                              >
                                {item.analysis.criteria_met ? "Met" : "Not Met"}
                              </Badge>
                              {item.analysis?.confidence && (
                                <Badge variant="outline" className="text-xs">
                                  {item.analysis.confidence} Confidence
                                </Badge>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No criteria analysis available</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Files Card */}
      {tender.uploaded_files && tender.uploaded_files.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Uploaded Files ({tender.uploaded_files.length})
            </CardTitle>
            <CardDescription>
              Files processed for this tender analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {tender.uploaded_files.map((file, index) => (
                <div 
                  key={index}
                  className="flex items-center justify-between p-3 border border-secondary-border rounded-lg bg-secondary/20 hover:bg-secondary/40 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium truncate max-w-[300px]">
                        {file.filename}
                      </p>
                      {file.bytes && (
                        <p className="text-xs text-muted-foreground">
                          {(file.bytes / 1024).toFixed(1)} KB
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {file.type?.toUpperCase() || file.filename.split('.').pop()?.toUpperCase() || 'FILE'}
                    </Badge>
                    {file.blob_url && (
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => window.open(file.blob_url, '_blank')}
                      >
                        <Download className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            
            {/* Download All Files Button */}
            <Button
              className="w-full mt-4"
              onClick={handleDownloadAllFiles}
              disabled={isDownloading || !tender.uploaded_files || tender.uploaded_files.length === 0}
            >
              {isDownloading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  Download All Files
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
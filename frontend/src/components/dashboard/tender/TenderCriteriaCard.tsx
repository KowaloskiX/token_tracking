"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ListCheck, ChevronDown, MoreHorizontal, FileDown, AlertCircle } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger, DropdownMenuItem } from '@/components/ui/dropdown-menu';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import EditableCriteriaItem from '@/components/dashboard/tenders/EditableCriteriaItem';
import { TenderAnalysisResult, CriteriaAnalysisResult } from '@/types/tenders';
import { FileData } from '@/types'; // NEW: Add this import
import { useTendersTranslations, useCommonTranslations } from '@/hooks/useTranslations';

interface TenderCriteriaCardProps {
  tender: TenderAnalysisResult;
  markdownComponents: Components;
  onCriteriaUpdate: (criteriaName: string, newSummary: string) => void;
  onExportCriteria: (criteria: CriteriaAnalysisResult[], fileName: string) => void;
  onFilePreview?: (file: FileData, citationsForFile: string[]) => void; // NEW: Add this prop
}

export default function TenderCriteriaCard({ 
  tender, 
  markdownComponents, 
  onCriteriaUpdate, 
  onExportCriteria,
  onFilePreview // NEW: Accept this prop
}: TenderCriteriaCardProps) {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();

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
        {t('tenders.criteria.weight')}: {weight}
      </Badge>
    );
  };

  const handleExport = () => {
    const fullName = tender?.tender_metadata?.name || t('tenders.actions.noTenderSelected');
    const words = fullName.split(' ');
    const firstFourWords = words.slice(0, 5).join(' ');
    const trimmedName = firstFourWords.length > 100 
      ? firstFourWords.substring(0, 100) 
      : firstFourWords;
    const fileName = `${trimmedName}_${t('tenders.criteria.title').toLowerCase()}`;
    onExportCriteria(tender?.criteria_analysis || [], fileName);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ListCheck className="h-5 w-5" />
              {t('tenders.criteria.title')}
            </CardTitle>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem 
                onClick={handleExport}
                disabled={!tender?.criteria_analysis?.length}
                className="flex items-center gap-2 cursor-pointer"
              >
                <FileDown className="h-4 w-4" />
                <span>{t('tenders.criteria.exportToExcel')}</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent>
        {tender.criteria_analysis && tender.criteria_analysis.length > 0 ? (
          <div className="space-y-2">
            {tender.criteria_analysis.map((item, index) => {
              const shouldShowWeight = item.exclude_from_score === false && item.analysis?.weight !== undefined;
              const allCitations = tender.criteria_analysis?.flatMap(criteria => 
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
                        <Card className="bg-secondary p-2 relative rounded-md flex-shrink-0">
                          <div className={`absolute w-2 h-2 rounded-full ${getCriteriaMetColor(item.analysis?.criteria_met)} right-0 top-0 transform translate-x-1 -translate-y-1`} />
                          <ListCheck className="w-4 h-4 shrink-0 text-muted-foreground" />
                        </Card>
                        
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
                        
                        {shouldShowWeight && (
                          <div className="flex-shrink-0 ml-2">
                            {getWeightBadge(item.analysis!.weight!)}
                          </div>
                        )}
                        
                        <ChevronDown 
                          className="w-4 h-4 flex-shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180 ml-2" 
                        />
                      </div>
                    </CollapsibleTrigger>
                  </div>
                  <CollapsibleContent>
                    <div className="border border-t-0 border-secondary-border bg-secondary/30 px-4 py-3 rounded-b-xl">
                      <EditableCriteriaItem
                        resultId={tender._id?.toString() ?? ""}
                        criteriaItem={item}
                        markdownComponents={markdownComponents}
                        uploadedFiles={tender.uploaded_files}
                        onUpdate={(newSummary) => {
                          onCriteriaUpdate(item.criteria, newSummary);
                        }}
                        onFilePreview={onFilePreview} // NEW: Pass the file preview handler
                        allCitations={allCitations}
                      />
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('tenders.noAnalysis')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
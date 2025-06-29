"use client"
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Clock, FileText, Link as LinkIcon, AlertCircle } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import ReactMarkdown from 'react-markdown';
import Link from 'next/link';
import { format } from 'date-fns';
import { TenderAnalysisResult, TenderAnalysisUpdate } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface UpdateSummary {
  update_id: string;
  overall_summary: string;
  file_summaries: Array<{
    filename: string;
    summary: string;
  }>;
}

interface TenderUpdatesCardProps {
  tender: TenderAnalysisResult;
  resultUpdates: TenderAnalysisUpdate[];
  isLoadingUpdates: boolean;
  updateSummaries: UpdateSummary[];
}

export default function TenderUpdatesCard({ 
  tender, 
  resultUpdates, 
  isLoadingUpdates, 
  updateSummaries 
}: TenderUpdatesCardProps) {
  const t = useTendersTranslations();

  const formatDate = (date: Date): string => {
    try {
      return format(date, "dd.MM.yyyy");
    } catch (e) {
      return t('common.dates.invalidDate');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          {t('tenders.updates.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoadingUpdates ? (
          <div className="text-sm text-muted-foreground p-2 flex items-center">
            <span className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin mr-2" />
            {t('tenders.updates.loading')}
          </div>
        ) : tender && resultUpdates.length > 0 ? (
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
                        {t('tenders.updates.updateDate')}: {formatDate(new Date(update.update_date))}
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
                      <div className="text-sm text-muted-foreground italic">
                        {t('tenders.updates.noFilesInUpdate')}
                      </div>
                    )}

                    {update.update_link && (
                      <Link
                        href={update.update_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-sm text-primary hover:underline mt-2 py-1"
                      >
                        <LinkIcon size={14} />
                        <span>{t('tenders.updates.updateSource')}</span>
                      </Link>
                    )}
                    
                    {(() => {
                      const summary = updateSummaries.find(s => s.update_id === update._id);
                      return summary ? (
                        <>
                          {summary.overall_summary && (
                            <div className="mt-4">
                              <h4 className="font-medium text-sm">{t('tenders.updates.updateSummary')}</h4>
                              <ReactMarkdown className="prose-sm whitespace-pre-line">
                                {summary.overall_summary}
                              </ReactMarkdown>
                            </div>
                          )}
                          {summary.file_summaries.length > 0 && (
                            <div className="mt-2 pl-10">
                              <h4 className="font-medium text-sm">{t('tenders.updates.fileSummaries')}</h4>
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
          <div className="text-center py-8 text-muted-foreground">
            <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('tenders.updates.noUpdates')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
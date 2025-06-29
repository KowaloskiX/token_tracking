"use client"
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';
import { FileText } from 'lucide-react';

interface TenderDescriptionCardProps {
  tender: TenderAnalysisResult;
  markdownComponents: Components;
}

export default function TenderDescriptionCard({ tender, markdownComponents }: TenderDescriptionCardProps) {
  const t = useTendersTranslations();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          {t('description.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-sm tracking-tight text-muted-foreground markdown-content">
          <ReactMarkdown
            components={markdownComponents}
            remarkPlugins={[remarkGfm, remarkBreaks]}
          >
            {tender.tender_description ? 
              tender.tender_description === "Brak danych." ? "" : tender.tender_description 
              : t('tenders.description.noDescription')
            }
          </ReactMarkdown>
        </div>
      </CardContent>
    </Card>
  );
}
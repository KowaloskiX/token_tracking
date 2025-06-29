"use client"
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MessageSquare } from 'lucide-react';
import CommentSection from '@/components/dashboard/tenders/CommentSection';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderCommentsCardProps {
  tender: TenderAnalysisResult;
}

export default function TenderCommentsCard({ tender }: TenderCommentsCardProps) {
  const t = useTendersTranslations();
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          {t('tenders.comments.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tender._id ? (
          <CommentSection 
            tenderId={tender._id} 
            refreshTrigger={true}
          />
        ) : (
          <p className="text-sm text-muted-foreground">{t('tenders.noCommentsError')}</p>
        )}
      </CardContent>
    </Card>
  );
}
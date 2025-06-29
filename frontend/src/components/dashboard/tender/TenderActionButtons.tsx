"use client"
import { Button } from '@/components/ui/button';
import { LibraryBig, ListCheck } from 'lucide-react';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderActionButtonsProps {
  tender: TenderAnalysisResult;
  localStatus: string;
  isCreating: boolean;
  onOpenAsAssistant: () => void;
  onAddToKanban: () => void;
}

export default function TenderActionButtons({ 
  tender, 
  localStatus, 
  isCreating, 
  onOpenAsAssistant, 
  onAddToKanban 
}: TenderActionButtonsProps) {
  const t = useTendersTranslations();

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 md:left-64">
      <div className="container mx-auto px-4 py-2">
        <div className="max-w-4xl mx-auto flex gap-3">
          <Button 
            className="flex-1 text-white transition-colors"
            disabled={!tender || isCreating || localStatus === 'archived' || !tender.uploaded_files?.length}
            onClick={onOpenAsAssistant}
          >
            {isCreating ? (
              <>
                <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                {t('tenders.actions.creating')}
              </>
            ) : (
              <>
                <LibraryBig strokeWidth={2.2} className="w-5 h-5 mr-2" />
                {t('tenders.actions.openAsProject')}
              </>
            )}
          </Button>
          
          <Button
            variant="outline"
            className={`flex-1 transition-colors ${
              localStatus !== 'active' 
                ? 'opacity-50 cursor-not-allowed text-muted-foreground border-muted' 
                : 'hover:bg-secondary'
            }`}
            onClick={onAddToKanban}
            disabled={!tender || localStatus !== 'active'}
          >
            <ListCheck className="mr-2 h-4 w-4" />
            {t('tenders.actions.addToKanban')}
          </Button>
        </div>
      </div>
    </div>
  );
}
"use client"
import TenderSourceIcon from '@/components/dashboard/tenders/TenderSourceIcon';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderDetailsHeaderProps {
  tender: TenderAnalysisResult;
  onCopyId: (id: string) => void;
}

export default function TenderDetailsHeader({ tender, onCopyId }: TenderDetailsHeaderProps) {
  const t = useTendersTranslations();

  const handleTitleClick = () => {
    if (tender.tender_url) {
      window.open(tender.tender_url, '_blank');
    }
  };

  return (
    <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
      <div className="container mx-auto px-4 py-2">
        <div className="max-w-4xl mx-auto flex items-center gap-4 min-h-8">
          <div className="border border-neutral-200 p-2 rounded-lg flex-shrink-0">
            <div className="w-5 h-5 relative">
              <TenderSourceIcon 
                source={tender.source} 
                url={tender.tender_url} 
              />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h1 
              className={`text-xl font-semibold leading-snug ${tender.tender_url ? 'cursor-pointer hover:underline' : ''}`}
              onClick={handleTitleClick}
            >
              {tender.tender_metadata?.name || t('tenders.board.unnamedTender')}
            </h1>
          </div>
        </div>
      </div>
    </div>
  );
}
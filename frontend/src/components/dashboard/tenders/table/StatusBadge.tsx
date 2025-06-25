import React from 'react';
import { Badge } from "@/components/ui/badge";
import { TenderAnalysisResult } from "@/types/tenders";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface StatusBadgeProps {
  result: TenderAnalysisResult;
  boardNames: string[];
  boardsLoading: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ 
  result, 
  boardNames, 
  boardsLoading 
}) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();

  const truncateText = (text: string, maxLength: number) => {
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
  };

  if (boardsLoading) {
    return (
      <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">
        {commonT('loading')}
      </Badge>
    );
  }

  if (boardNames.length > 0) {
    const displayText = boardNames.length === 1
      ? truncateText(boardNames[0], 15)
      : `${truncateText(boardNames[0], 10)}+${boardNames.length - 1}`;

    return (
      <Badge
        variant="outline"
        className="border-transparent bg-secondary-hover text-primary shadow"
        title={boardNames.length > 1 ? `${t('tenders.board.management')}: ${boardNames.join(', ')}` : boardNames[0]}
      >
        {displayText}
      </Badge>
    );
  }

  const status = result.status || 'inactive';
  switch (status) {
    case 'inactive':
      return <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">{t('tenders.status.inactive')}</Badge>;
    case 'active':
      return <Badge variant="default" className="bg-green-600/80 hover:bg-green-600/80 font-normal">{t('tenders.status.active')}</Badge>;
    case 'archived':
      return <Badge variant="secondary" className="bg-secondary text-primary/70 hover:bg-secondary font-normal">{t('tenders.status.archived')}</Badge>;
    default:
      return <Badge variant="outline">{t('tenders.status.unknown')}</Badge>;
  }
};
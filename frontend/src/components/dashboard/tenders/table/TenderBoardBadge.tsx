import React from 'react';
import { Badge } from '@/components/ui/badge';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations, useCommonTranslations } from '@/hooks/useTranslations';
import { truncateText } from '@/utils/tenderDateUtils';

interface TenderBoardBadgeProps {
  result: TenderAnalysisResult;
  getTenderBoards: (tenderId: string) => string[];
  boardsLoading: boolean;
}

export const TenderBoardBadge: React.FC<TenderBoardBadgeProps> = ({
  result,
  getTenderBoards,
  boardsLoading
}) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();



  if (boardsLoading) {
    return (
      <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">
        {commonT('loading')}
      </Badge>
    );
  }

  const boardNames = getTenderBoards(result._id!);
  
  if (boardNames.length > 0) {
    const displayText = boardNames.length === 1
      ? truncateText(boardNames[0], 15)
      : `${truncateText(boardNames[0], 10)}+${boardNames.length - 1}`;

    return (
      <Badge
        variant="outline"
        className="border-transparent bg-secondary-hover text-center text-primary shadow"
        title={boardNames.length > 1 ? `${t('tenders.board.management')}: ${boardNames.join(', ')}` : boardNames[0]}
      >
        {displayText}
      </Badge>
    );
  }

  // If not in any board, show status as fallback
  const status = result.status || 'inactive';
  switch (status) {
    case 'inactive':
      return (
        <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">
          {t('tenders.status.inactive')}
        </Badge>
      );
    case 'active':
      return (
        <Badge variant="default" className="bg-green-600/80 hover:bg-green-600/80 font-normal">
          {t('tenders.status.active')}
        </Badge>
      );
    case 'archived':
      return (
        <Badge variant="secondary" className="bg-secondary text-primary/70 hover:bg-secondary font-normal">
          {t('tenders.status.archived')}
        </Badge>
      );

       case 'filtered':
        return <Badge variant="default" className="bg-yellow-600/80 hover:bg-yellow-600/80 font-normal">{t('tenders.status.filtered')}</Badge>;
      case 'external':
        return <Badge variant="default" className="bg-primary hover:bg-primary/80 font-normal">{t('tenders.status.external')}</Badge>;
    default:
      return (
        <Badge variant="outline">
          {t('tenders.status.unknown')}
        </Badge>
      );
  }
};
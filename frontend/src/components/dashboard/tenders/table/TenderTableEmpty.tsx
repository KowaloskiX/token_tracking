import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableEmptyProps {
  tableWidth: number;
  allResultsLength: number;
  selectedAnalysis: any;
  columnCount: number; // Added missing prop
}

export const TenderTableEmpty: React.FC<TenderTableEmptyProps> = ({
  tableWidth,
  allResultsLength,
  selectedAnalysis,
  columnCount // Added missing prop
}) => {
  const t = useTendersTranslations();

  const getMessage = () => {
    if (allResultsLength > 0) {
      return t('tenders.list.noTenders');
    } else if (selectedAnalysis) {
      return t('tenders.list.noResults');
    } else {
      return t('tenders.list.selectAnalysis');
    }
  };

  return (
    <TableRow>
      <TableCell 
        colSpan={columnCount} 
        className="text-center text-muted-foreground py-20"
      >
        {getMessage()}
      </TableCell>
    </TableRow>
  );
};
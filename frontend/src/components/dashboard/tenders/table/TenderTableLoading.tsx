import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Loader2 } from 'lucide-react';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableLoadingProps {
  tableWidth: number;
  totalFetched: number;
  totalTendersCount: number | null;
}

export const TenderTableLoading: React.FC<TenderTableLoadingProps> = ({
  tableWidth,
  totalFetched,
  totalTendersCount
}) => {
  const t = useTendersTranslations();

  return (
    <TableRow>
      <TableCell colSpan={tableWidth >= 700 ? 9 : 6} className="h-[500px]">
        <div className="flex flex-col w-full h-full items-center justify-center space-y-2">
          <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
          <p className="text-sm text-muted-foreground">
            {t('tenders.list.loading', {
              fetched: totalFetched,
              total: totalTendersCount !== null ? ` / ${totalTendersCount}` : ''
            })}
          </p>
          {totalTendersCount !== null && totalTendersCount > 0 && (
            <div className="w-1/4 h-1 bg-muted rounded-full overflow-hidden">
              <div
                className="h-1 bg-primary transition-all duration-300"
                style={{ width: `${(totalFetched / totalTendersCount) * 100}%` }}
              />
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
};
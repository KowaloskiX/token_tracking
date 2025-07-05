import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Loader2 } from 'lucide-react';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableLoadingProps {
  tableWidth: number;
  totalFetched: number;
  totalTendersCount: number | null;
  columnCount: number;
}

export const TenderTableLoading: React.FC<TenderTableLoadingProps> = ({
  tableWidth,
  totalFetched,
  totalTendersCount,
  columnCount
}) => {
  const t = useTendersTranslations();

  return (
    <TableRow>
      <TableCell colSpan={columnCount} className="h-[500px] p-0 relative">
        {/* Viewport-centered loading container */}
        <div className="fixed inset-0 flex items-center justify-center pointer-events-none z-10">
          <div className="bg-card border border-border rounded-lg shadow-lg p-8 max-w-md pointer-events-auto">
            <div className="flex flex-col items-center justify-center space-y-4">
              <div className="relative">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              </div>
              
              <div className="text-center space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t('tenders.list.loading', {
                    fetched: totalFetched,
                    total: totalTendersCount !== null ? ` / ${totalTendersCount}` : ''
                  })}
                </p>
              </div>

              {totalTendersCount !== null && totalTendersCount > 0 && (
                <div className="w-full space-y-2">
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-2 bg-primary transition-all duration-300 rounded-full"
                      style={{ width: `${(totalFetched / totalTendersCount) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground text-center">
                    {Math.round((totalFetched / totalTendersCount) * 100)}%
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Semi-transparent overlay to dim the table behind */}
        <div className="absolute inset-0 bg-background/50 backdrop-blur-[1px]" />
      </TableCell>
    </TableRow>
  );
};
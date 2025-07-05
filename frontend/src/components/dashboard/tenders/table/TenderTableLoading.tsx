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

const SkeletonCell: React.FC<{ width?: string; height?: string }> = ({ 
  width = "w-full", 
  height = "h-4" 
}) => (
  <div className={`${width} ${height} bg-muted rounded animate-pulse`} />
);

const SkeletonRow: React.FC<{ columnCount: number }> = ({ columnCount }) => (
  <TableRow className="hover:bg-transparent">
    {/* Source column */}
    <TableCell className="w-10">
      <div className="w-6 h-6 bg-muted rounded animate-pulse" />
    </TableCell>
    
    {/* Name column */}
    <TableCell className="w-40">
      <div className="space-y-2">
        <SkeletonCell width="w-3/4" />
        <SkeletonCell width="w-1/2" height="h-3" />
      </div>
    </TableCell>
    
    {/* Organization column */}
    <TableCell className="w-36">
      <SkeletonCell width="w-5/6" />
    </TableCell>
    
    {/* Publication date */}
    <TableCell className="w-20">
      <SkeletonCell width="w-16" height="h-3" />
    </TableCell>
    
    {/* Progress bar */}
    <TableCell className="w-20">
      <div className="w-full h-2 bg-muted rounded-full animate-pulse" />
    </TableCell>
    
    {/* Submission deadline */}
    <TableCell className="w-30">
      <div className="flex items-center gap-1">
        <SkeletonCell width="w-16" height="h-3" />
        <SkeletonCell width="w-8" height="h-3" />
      </div>
    </TableCell>
    
    {/* Board status */}
    <TableCell className="w-24">
      <div className="w-16 h-6 bg-muted rounded-full animate-pulse" />
    </TableCell>
    
    {/* Score */}
    <TableCell className="w-20">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 bg-muted rounded-full animate-pulse" />
        <SkeletonCell width="w-10" height="h-3" />
      </div>
    </TableCell>
    
    {/* Fill remaining columns with generic skeletons */}
    {Array.from({ length: Math.max(0, columnCount - 9) }, (_, index) => (
      <TableCell key={`skeleton-${index}`} className="w-32">
        <SkeletonCell />
      </TableCell>
    ))}
    
    {/* Actions column */}
    <TableCell className="w-10">
      <div className="w-4 h-4 bg-muted rounded animate-pulse" />
    </TableCell>
  </TableRow>
);

export const TenderTableLoading: React.FC<TenderTableLoadingProps> = ({
  tableWidth,
  totalFetched,
  totalTendersCount,
  columnCount
}) => {
  const t = useTendersTranslations();
  
  // Calculate progress percentage
  const progressPercentage = totalTendersCount && totalTendersCount > 0 
    ? Math.round((totalFetched / totalTendersCount) * 100) 
    : 0;

  return (
    <>
      {/* First few skeleton rows */}
      {Array.from({ length: 3 }, (_, index) => (
        <SkeletonRow key={`skeleton-row-top-${index}`} columnCount={columnCount} />
      ))}
      
      {/* Loading progress row in the middle */}
      <TableRow className="bg-muted/30">
        <TableCell colSpan={columnCount} className="py-8">
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="flex items-center space-x-3">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">
                  {t('tenders.list.loading', {
                    fetched: totalFetched,
                    total: totalTendersCount !== null ? ` / ${totalTendersCount}` : ''
                  })}
                </p>
              </div>
            </div>
            
            {/* Progress bar */}
            {totalTendersCount !== null && totalTendersCount > 0 && (
              <div className="w-full max-w-md space-y-2">
                <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-2 bg-primary transition-all duration-300 rounded-full"
                    style={{ width: `${progressPercentage}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground text-center">
                  {progressPercentage}%
                </p>
              </div>
            )}
          </div>
        </TableCell>
      </TableRow>
      
      {/* More skeleton rows after the loading indicator */}
      {Array.from({ length: 4 }, (_, index) => (
        <SkeletonRow key={`skeleton-row-bottom-${index}`} columnCount={columnCount} />
      ))}
    </>
  );
};
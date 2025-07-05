import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { FileText, Search, FolderOpen } from 'lucide-react';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableEmptyProps {
  tableWidth: number;
  allResultsLength: number;
  selectedAnalysis: any;
  columnCount: number;
}

export const TenderTableEmpty: React.FC<TenderTableEmptyProps> = ({
  tableWidth,
  allResultsLength,
  selectedAnalysis,
  columnCount
}) => {
  const t = useTendersTranslations();

  const getEmptyState = () => {
    if (allResultsLength > 0) {
      return {
        icon: Search,
        title: "No matching tenders",
        message: t('tenders.list.noTenders'),
        description: "Try adjusting your filters or search criteria"
      };
    } else if (selectedAnalysis) {
      return {
        icon: FileText,
        title: "No results found",
        message: t('tenders.list.noResults'),
        description: "This analysis hasn't found any tenders yet"
      };
    } else {
      return {
        icon: FolderOpen,
        title: "Select an analysis",
        message: t('tenders.list.selectAnalysis'),
        description: "Choose a tender analysis to view results"
      };
    }
  };

  const emptyState = getEmptyState();
  const Icon = emptyState.icon;

  return (
    <TableRow>
      <TableCell colSpan={columnCount} className="p-0">
        {/* Centered empty state container with better styling */}
        <div className="relative w-full h-80 flex items-center justify-start pl-8">
          <div className="bg-card border border-border rounded-lg shadow-lg p-8 max-w-md">
            <div className="flex flex-col items-center justify-center space-y-4 text-center">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <Icon className="h-8 w-8 text-muted-foreground" />
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-foreground">
                  {emptyState.title}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {emptyState.message}
                </p>
                {emptyState.description && (
                  <p className="text-xs text-muted-foreground/80">
                    {emptyState.description}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </TableCell>
    </TableRow>
  );
};
// Updated TenderTable.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Table, TableBody } from '@/components/ui/table';
import { Loader2 } from 'lucide-react';
import { TenderAnalysisResult } from '@/types/tenders';
import { ResizableTableHeader } from './ResizableTableHeader';
import { DynamicTableRow } from './DynamicTableRow';
import { TenderTableLoading } from './TenderTableLoading';
import { TenderTableEmpty } from './TenderTableEmpty';
import { TenderTablePagination } from './TenderTablePagination';
import { TableLayout } from './TableLayout';
import { useTableColumns } from '@/hooks/table/useTableColumns';
import { ColumnConfig } from '@/types/tableColumns';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableProps {
  currentResults: TenderAnalysisResult[];
  selectedResult: TenderAnalysisResult | null;
  selectedAnalysis: any;
  isLoading: boolean;
  totalFetched: number;
  totalTendersCount: number | null;
  allResultsLength: number;
  currentPage: number;
  totalPages: number;
  availableCriteria: Array<{
    id: string;
    name: string;
    description?: string;
  }>;
  isUpdatedAfterOpened: (result: TenderAnalysisResult) => boolean;
  calculateDaysRemaining: (deadlineStr: string) => number;
  getTenderBoards: (tenderId: string) => string[];
  boardsLoading: boolean;
  onRowClick: (result: TenderAnalysisResult, event?: React.MouseEvent) => void;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => void;
  onUnopened: (result: TenderAnalysisResult) => void;
  onDelete: (event: React.MouseEvent, resultId: string) => void;
  onAddToKanban: (result: TenderAnalysisResult) => void;
  onPageChange: (page: number) => void;
  onSortChange?: (columnId: string, direction: 'asc' | 'desc' | null) => void;
  isDrawerVisible?: boolean;
  onDrawerVisibilityChange?: (visible: boolean) => void;
}

export const TenderTable: React.FC<TenderTableProps> = ({
  currentResults,
  selectedResult,
  selectedAnalysis,
  isLoading,
  totalFetched,
  totalTendersCount,
  allResultsLength,
  currentPage,
  totalPages,
  availableCriteria,
  isUpdatedAfterOpened,
  calculateDaysRemaining,
  getTenderBoards,
  boardsLoading,
  onRowClick,
  onStatusChange,
  onUnopened,
  onDelete,
  onAddToKanban,
  onPageChange,
  onSortChange,
  isDrawerVisible,
  onDrawerVisibilityChange,
}) => {
  const t = useTendersTranslations();
  const [tableWidth, setTableWidth] = useState(0);
  const tableContainerRef = useRef<HTMLDivElement>(null);

  // Use the table columns hook with selectedResult for sidebar-aware column sizing
  const {
    columnState,
    visibleColumns,
    totalTableWidth,
    updateColumnWidth,
    toggleColumnVisibility,
    updateCriteriaDisplayMode,
    reorderColumns,
    addCriteriaColumn,
    removeCriteriaColumn,
    setSortConfig,
    resetToDefaults,
    openTableLayout,
    closeTableLayout,
    managerState,
    saveColumnsToBackend,
  } = useTableColumns({
    selectedAnalysisId: selectedAnalysis?._id,
    availableCriteria,
    tableWidth,
    selectedResult,
  });

  // Monitor table container width
  useEffect(() => {
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setTableWidth(entry.contentRect.width);
      }
    });
    if (tableContainerRef.current) {
      resizeObserver.observe(tableContainerRef.current);
    }
    return () => resizeObserver.disconnect();
  }, []);

  const handleSort = (columnId: string, direction: 'asc' | 'desc' | null) => {
    setSortConfig(columnId, direction);
    onSortChange?.(columnId, direction);
  };

  const handleColumnResize = (columnId: string, newWidth: number) => {
    updateColumnWidth(columnId, newWidth);
  };

  const handleSaveConfiguration = async (columns: ColumnConfig[]): Promise<void> => {
    await saveColumnsToBackend(columns);
  };

  // Determine if horizontal scrolling is needed
  const needsHorizontalScroll = totalTableWidth > tableWidth && tableWidth > 0;

  // Calculate progress percentage for loader
  const progressPercentage = totalTendersCount && totalTendersCount > 0 
    ? Math.round((totalFetched / totalTendersCount) * 100) 
    : 0;

  return (
    <div className="w-full max-w-full relative">
      {/* Absolutely positioned loader in center of screen */}
      {isLoading && (
        <div className="fixed inset-0 flex items-center justify-center z-50 pointer-events-none">
          <div className="flex flex-col items-center justify-center space-y-4 bg-background/95 border border-border rounded-lg p-6 shadow-lg">
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
              <div className="w-64 space-y-2">
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
        </div>
      )}

      <div
        className="rounded-md border shadow-sm overflow-visible relative"
        ref={tableContainerRef}
      >
        {/* Always scrollable table container - handles both sidebar states consistently */}
        <div className={`
          ${needsHorizontalScroll ? 'overflow-x-auto scrollbar-thin' : 'overflow-x-visible'}
          ${selectedResult ? 'transition-all duration-200 ease-in-out' : ''}
        `}>
          <Table 
            className="min-w-max table-fixed" 
            style={{ 
              minWidth: needsHorizontalScroll ? `${totalTableWidth}px` : '100%',
              width: needsHorizontalScroll ? `${totalTableWidth}px` : '100%'
            }}
          >
            <ResizableTableHeader
              columns={visibleColumns}
              sortConfig={columnState.sortConfig}
              onSort={handleSort}
              onColumnResize={handleColumnResize}
              onOpenTableLayout={openTableLayout}
              isResizeDisabled={!!selectedResult}
            />
            <TableBody>
              {isLoading ? (
                <TenderTableLoading
                  tableWidth={tableWidth}
                  totalFetched={totalFetched}
                  totalTendersCount={totalTendersCount}
                  columnCount={visibleColumns.length + 1}
                />
              ) : currentResults.length === 0 ? (
                <TenderTableEmpty
                  tableWidth={tableWidth}
                  allResultsLength={allResultsLength}
                  selectedAnalysis={selectedAnalysis}
                  columnCount={visibleColumns.length + 1}
                />
              ) : (
                currentResults.map((result: TenderAnalysisResult) => (
                  <DynamicTableRow
                    key={result._id}
                    result={result}
                    selectedResult={selectedResult}
                    columns={visibleColumns}
                    isUpdatedAfterOpened={isUpdatedAfterOpened}
                    calculateDaysRemaining={calculateDaysRemaining}
                    getTenderBoards={getTenderBoards}
                    boardsLoading={boardsLoading}
                    onRowClick={onRowClick}
                    onStatusChange={onStatusChange}
                    onUnopened={onUnopened}
                    onDelete={onDelete}
                    onAddToKanban={onAddToKanban}
                  />
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Horizontal scroll indicator - show when scroll is needed and has content */}
        {needsHorizontalScroll && currentResults.length > 0 && !isLoading && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary/20 to-transparent pointer-events-none" />
        )}
      </div>

      {/* Pagination */}
      <TenderTablePagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={onPageChange}
      />

      {/* Column Manager */}
      <TableLayout
        isOpen={managerState.isOpen}
        onClose={closeTableLayout}
        columns={columnState.columns}
        availableCriteria={availableCriteria}
        onToggleVisibility={toggleColumnVisibility}
        onReorderColumns={reorderColumns}
        onAddCriteriaColumn={addCriteriaColumn}
        onRemoveCriteriaColumn={removeCriteriaColumn}
        onResetToDefaults={resetToDefaults}
        onUpdateColumnWidth={updateColumnWidth}
        onUpdateCriteriaDisplayMode={updateCriteriaDisplayMode}
        onSaveConfiguration={handleSaveConfiguration}
      />
    </div>
  );
};
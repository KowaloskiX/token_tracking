// Updated TenderTable.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Table, TableBody } from '@/components/ui/table';
import { TenderAnalysisResult } from '@/types/tenders';
import { ResizableTableHeader } from './ResizableTableHeader';
import { DynamicTableRow } from './DynamicTableRow';
import { TenderTableLoading } from './TenderTableLoading';
import { TenderTableEmpty } from './TenderTableEmpty';
import { TenderTablePagination } from './TenderTablePagination';
import { TableLayout } from './TableLayout';
import { useTableColumns } from '@/hooks/table/useTableColumns';
import { ColumnConfig } from '@/types/tableColumns';

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
  // NEW: Add callback to inform parent about scroll needs
  onScrollInfoChange?: (needsScroll: boolean, totalWidth: number) => void;
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
  onScrollInfoChange, // NEW: Accept scroll info callback
}) => {
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

  // NEW: Notify parent about scroll needs when sidebar is closed
  useEffect(() => {
    // Only report scroll needs when:
    // 1. Sidebar is closed (!selectedResult)
    // 2. Table has actual content (not loading and has results)
    // 3. Table width is measured (tableWidth > 0)
    if (onScrollInfoChange && !selectedResult && !isLoading && currentResults.length > 0 && tableWidth > 0) {
      const needsScroll = totalTableWidth > tableWidth;
      onScrollInfoChange(needsScroll, totalTableWidth);
    } else if (onScrollInfoChange && (!selectedResult && (isLoading || currentResults.length === 0))) {
      // Reset scroll when loading or no content
      onScrollInfoChange(false, 0);
    }
  }, [onScrollInfoChange, selectedResult, totalTableWidth, tableWidth, isLoading, currentResults.length]);

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
  const needsHorizontalScroll = totalTableWidth > tableWidth;

  return (
    <div className="w-full max-w-full">
      <div
        className={`rounded-md border shadow-sm overflow-visible relative ${
          selectedResult ? 'transition-all duration-200 ease-in-out' : ''
        }`}
        ref={tableContainerRef}
      >
        {/* Scrollable table container - only scroll here when sidebar is OPEN AND has content */}
        <div className={
          selectedResult && currentResults.length > 0 
            ? "overflow-x-auto scrollbar-thin" 
            : "overflow-visible"
        }>
          <Table className="min-w-max table-fixed" style={{ minWidth: `${totalTableWidth}px` }}>
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
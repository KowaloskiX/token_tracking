// components/dashboard/tenders/table/EnhancedTenderTable.tsx

import React, { useState, useEffect, useRef } from 'react';
import { Table, TableBody } from '@/components/ui/table';
import { TenderAnalysisResult } from '@/types/tenders';
import { ResizableTableHeader } from './ResizableTableHeader';
import { DynamicTableRow } from './DynamicTableRow';
import { TenderTableLoading } from './TenderTableLoading';
import { TenderTableEmpty } from './TenderTableEmpty';
import { TenderTablePagination } from './TenderTablePagination';
import { ColumnManager } from './ColumnManager';
import { useTableColumns } from '@/hooks/table/useTableColumns';

interface EnhancedTenderTableProps {
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
}

export const EnhancedTenderTable: React.FC<EnhancedTenderTableProps> = ({
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
}) => {
  const [tableWidth, setTableWidth] = useState(0);
  const tableContainerRef = useRef<HTMLDivElement>(null);

  // Use the table columns hook
  const {
    columnState,
    visibleColumns,
    totalTableWidth,
    updateColumnWidth,
    toggleColumnVisibility,
    reorderColumns,
    addCriteriaColumn,
    removeCriteriaColumn,
    setSortConfig,
    resetToDefaults,
    openColumnManager,
    closeColumnManager,
    managerState,
  } = useTableColumns({
    selectedAnalysisId: selectedAnalysis?._id,
    availableCriteria,
    tableWidth,
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

  // Determine if horizontal scrolling is needed
  const needsHorizontalScroll = totalTableWidth > tableWidth;

  return (
    <div className="w-full max-w-full">
      <div 
        className="rounded-md border shadow-sm overflow-hidden"
        ref={tableContainerRef}
      >
        {/* Scrollable table container with strict width constraints */}
        <div className="overflow-x-hidden">
          <Table className="w-full table-fixed" style={{ minWidth: `${totalTableWidth}px` }}>
            <ResizableTableHeader
              columns={visibleColumns}
              sortConfig={columnState.sortConfig}
              onSort={handleSort}
              onColumnResize={handleColumnResize}
              onOpenColumnManager={openColumnManager}
            />
            <TableBody>
              {isLoading ? (
                <TenderTableLoading
                  tableWidth={tableWidth}
                  totalFetched={totalFetched}
                  totalTendersCount={totalTendersCount}
                  columnCount={visibleColumns.length + 1} // +1 for column manager button
                />
              ) : currentResults.length === 0 ? (
                <TenderTableEmpty
                  tableWidth={tableWidth}
                  allResultsLength={allResultsLength}
                  selectedAnalysis={selectedAnalysis}
                  columnCount={visibleColumns.length + 1} // +1 for column manager button
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

        {/* Horizontal scroll indicator */}
        {needsHorizontalScroll && (
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
      <ColumnManager
        isOpen={managerState.isOpen}
        onClose={closeColumnManager}
        columns={columnState.columns}
        availableCriteria={availableCriteria}
        onToggleVisibility={toggleColumnVisibility}
        onReorderColumns={reorderColumns}
        onAddCriteriaColumn={addCriteriaColumn}
        onRemoveCriteriaColumn={removeCriteriaColumn}
        onResetToDefaults={resetToDefaults}
        onUpdateColumnWidth={updateColumnWidth}
      />
    </div>
  );
};
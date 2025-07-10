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
import { useTendersTranslations } from '@/hooks/useTranslations';
import { Skeleton } from "@/components/ui/skeleton"; // Make sure this import exists

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
  
  // Data filter props
  includeHistorical: boolean;
  onToggleHistorical: (value: boolean) => void;
  includeFiltered: boolean;
  onToggleFiltered: (value: boolean) => void;
  includeExternal: boolean;
  onToggleExternal: (value: boolean) => void;
  showIncludeExternal: boolean;
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
  isDrawerVisible = false,
  onDrawerVisibilityChange,
  includeHistorical,
  onToggleHistorical,
  includeFiltered,
  onToggleFiltered,
  includeExternal,
  onToggleExternal,
  showIncludeExternal,
}) => {
  const t = useTendersTranslations();
  const [tableWidth, setTableWidth] = useState(0);
  const [scrollState, setScrollState] = useState({
    scrollLeft: 0,
    scrollTop: 0,
    scrollWidth: 0,
    scrollHeight: 0,
    clientWidth: 0,
    clientHeight: 0,
  });
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const scrollableRef = useRef<HTMLDivElement>(null);

  // Use the table columns hook
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
    isDrawerVisible,
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

  // Monitor scroll position for gradient effects
  useEffect(() => {
    const scrollableElement = scrollableRef.current;
    if (!scrollableElement) return;

    const handleScroll = () => {
      const {
        scrollLeft,
        scrollTop,
        scrollWidth,
        scrollHeight,
        clientWidth,
        clientHeight,
      } = scrollableElement;

      setScrollState({
        scrollLeft,
        scrollTop,
        scrollWidth,
        scrollHeight,
        clientWidth,
        clientHeight,
      });
    };

    scrollableElement.addEventListener('scroll', handleScroll);
    
    // Call immediately to set initial state
    handleScroll();

    return () => {
      scrollableElement.removeEventListener('scroll', handleScroll);
    };
  }, [currentResults]); // Add currentResults as dependency

  // Also add another useEffect to recalculate when table width changes
  useEffect(() => {
    const scrollableElement = scrollableRef.current;
    if (!scrollableElement) return;

    // Recalculate scroll state when table dimensions change
    const {
      scrollLeft,
      scrollTop,
      scrollWidth,
      scrollHeight,
      clientWidth,
      clientHeight,
    } = scrollableElement;

    setScrollState({
      scrollLeft,
      scrollTop,
      scrollWidth,
      scrollHeight,
      clientWidth,
      clientHeight,
    });
  }, [tableWidth, totalTableWidth]); // Recalculate when dimensions change

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

  // Calculate scroll gradients
  const calculateScrollGradients = () => {
    const { scrollLeft, scrollTop, scrollWidth, scrollHeight, clientWidth, clientHeight } = scrollState;
    
    const horizontalScrollable = scrollWidth > clientWidth;
    const verticalScrollable = scrollHeight > clientHeight;
    
    let leftGradient = 0;
    let rightGradient = 0;
    let topGradient = 0;
    let bottomGradient = 0;
    
    if (horizontalScrollable) {
      const maxScrollLeft = scrollWidth - clientWidth;
      leftGradient = scrollLeft > 0 ? Math.min(scrollLeft / 50, 1) : 0;
      rightGradient = scrollLeft < maxScrollLeft ? Math.min((maxScrollLeft - scrollLeft) / 50, 1) : 0;
    }
    
    if (verticalScrollable) {
      const maxScrollTop = scrollHeight - clientHeight;
      topGradient = scrollTop > 0 ? Math.min(scrollTop / 50, 1) : 0;
      bottomGradient = scrollTop < maxScrollTop ? Math.min((maxScrollTop - scrollTop) / 50, 1) : 0;
    }
    
    return { leftGradient, rightGradient, topGradient, bottomGradient, horizontalScrollable, verticalScrollable };
  };

  const { leftGradient, rightGradient, topGradient, bottomGradient, horizontalScrollable, verticalScrollable } = calculateScrollGradients();

  return (
    <div className="w-full max-w-full relative flex flex-col h-full">
      {/* Loading overlay */}
      {isLoading && (
        <div 
          className="absolute inset-0 flex items-center justify-center z-50 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse 400px 200px at center, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 30%, hsl(var(--background) / 0.7) 50%, hsl(var(--background) / 0.3) 70%, transparent 100%)`
          }}
        >
          <div className="flex flex-col items-center justify-center space-y-4 rounded-lg p-6">
            <div className="flex items-center space-x-3">
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
            <div className="w-64 space-y-2">
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-2 bg-primary rounded-full transition-all duration-700 ease-out"
                  style={{ width: `${progressPercentage}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground text-center">
                {progressPercentage}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Table container */}
      <div
        className="flex-1 rounded-md border shadow-sm overflow-hidden relative min-h-0"
        ref={tableContainerRef}
      >
        {/* Scroll gradient overlays - DISABLED */}
        {/* 
        {leftGradient > 0 && (
          <div
            className="absolute top-0 left-0 w-20 z-10 pointer-events-none transition-opacity duration-300"
            style={{
              background: `linear-gradient(to right, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 30%, hsl(var(--background) / 0.6) 50%, hsl(var(--background) / 0.3) 70%, transparent 100%)`,
              opacity: leftGradient,
              bottom: horizontalScrollable ? '10px' : '0',
            }}
          />
        )}
        {rightGradient > 0 && (
          <div
            className="absolute top-0 w-20 z-10 pointer-events-none transition-opacity duration-300"
            style={{
              background: `linear-gradient(to left, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 30%, hsl(var(--background) / 0.6) 50%, hsl(var(--background) / 0.3) 70%, transparent 100%)`,
              opacity: rightGradient,
              right: verticalScrollable ? '10px' : '0',
              bottom: horizontalScrollable ? '10px' : '0',
            }}
          />
        )}
        {topGradient > 0 && (
          <div
            className="absolute top-0 left-0 h-20 z-10 pointer-events-none transition-opacity duration-300"
            style={{
              background: `linear-gradient(to bottom, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 30%, hsl(var(--background) / 0.6) 50%, hsl(var(--background) / 0.3) 70%, transparent 100%)`,
              opacity: topGradient,
              right: verticalScrollable ? '10px' : '0',
            }}
          />
        )}
        {bottomGradient > 0 && (
          <div
            className="absolute left-0 h-20 z-10 pointer-events-none transition-opacity duration-300"
            style={{
              background: `linear-gradient(to top, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 30%, hsl(var(--background) / 0.6) 50%, hsl(var(--background) / 0.3) 70%, transparent 100%)`,
              opacity: bottomGradient,
              bottom: horizontalScrollable ? '10px' : '0',
              right: verticalScrollable ? '10px' : '0',
            }}
          />
        )}
        */}

        {/* Scrollable table container */}
        <div 
          ref={scrollableRef}
          className="h-full scrollbar-table flex-1"
          style={{
            overflowY: 'auto',
            overflowX: 'auto'
          }}
        >
          <div 
            className="table-container-inner"
            style={{ 
              width: totalTableWidth > tableWidth ? `${totalTableWidth}px` : '100%',
              minWidth: '100%',
              overflow: 'clip',
              display: 'block'
            }}
          >
            <Table className="table-fixed w-full">
              <ResizableTableHeader
                columns={visibleColumns}
                sortConfig={columnState.sortConfig}
                onSort={handleSort}
                onColumnResize={handleColumnResize}
                onOpenTableLayout={openTableLayout}
                isResizeDisabled={false}
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
                  currentResults.map((result: TenderAnalysisResult) => {
                    // Check if this is a pending analysis
                    const isPending = (result as any).isPending;
                    
                    return (
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
                        isPending={isPending} // Pass pending state
                      />
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Horizontal scroll indicator */}
        {needsHorizontalScroll && currentResults.length > 0 && !isLoading && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary/20 to-transparent pointer-events-none" />
        )}
      </div>

      {/* Pagination */}
      <div className="flex-shrink-0">
        <TenderTablePagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={onPageChange}
        />
      </div>

      {/* Table Settings Dialog */}
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
        includeHistorical={includeHistorical}
        onToggleHistorical={onToggleHistorical}
        includeFiltered={includeFiltered}
        onToggleFiltered={onToggleFiltered}
        includeExternal={includeExternal}
        onToggleExternal={onToggleExternal}
        showIncludeExternal={showIncludeExternal}
      />
    </div>
  );
};
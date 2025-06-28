// src/components/dashboard/tenders/table/TenderTable.tsx
import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2 } from 'lucide-react';
import { cn } from "@/lib/utils";
import { TenderAnalysisResult } from "@/types/tenders";
import { TableColumn, SortableField } from '@/types/table';
import { ResizableTableHeader } from "./ResizableTableHeader";
import { TableCellRenderer } from "./TableCellRenderer";
import { useTendersTranslations } from "@/hooks/useTranslations";

interface TenderTableProps {
  results: TenderAnalysisResult[];
  selectedResult: TenderAnalysisResult | null;
  tableWidth: number;
  isLoading: boolean;
  totalFetched: number;
  totalTendersCount: number | null;
  allResults: TenderAnalysisResult[];
  selectedAnalysis: any;
  getTenderBoards: (tenderId: string) => string[];
  boardsLoading: boolean;
  isUpdatedAfterOpened: (result: TenderAnalysisResult) => boolean;
  calculateDaysRemaining: (deadlineStr: string) => number;
  calculateProgressPercentage: (createdAt: string, deadlineStr: string) => number;
  formatDate: (dateStr: string) => string;
  extractHour: (dateStr: string) => string;
  formatDateTime: (dateTimeStr: string) => string;
  truncateText: (text: string, maxLength: number) => string;
  onRowClick: (result: TenderAnalysisResult, event?: React.MouseEvent) => Promise<void>;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => Promise<void>;
  onUnopened: (result: TenderAnalysisResult) => Promise<void>;
  onDelete: (event: React.MouseEvent, resultId: string) => Promise<void>;
  onAddToKanban: (result: TenderAnalysisResult) => void;
  
  // New props for dynamic columns
  visibleColumns?: TableColumn[];
  onColumnResize?: (columnId: string, width: number) => void;
  onSort?: (field: SortableField) => void;
  sortConfig?: {
    field: SortableField;
    direction: 'asc' | 'desc';
  } | null;
}

export const TenderTable: React.FC<TenderTableProps> = ({
  results,
  selectedResult,
  tableWidth,
  isLoading,
  totalFetched,
  totalTendersCount,
  allResults,
  selectedAnalysis,
  getTenderBoards,
  boardsLoading,
  isUpdatedAfterOpened,
  calculateDaysRemaining,
  calculateProgressPercentage,
  formatDate,
  extractHour,
  formatDateTime,
  truncateText,
  onRowClick,
  onStatusChange,
  onUnopened,
  onDelete,
  onAddToKanban,
  visibleColumns = [],
  onColumnResize,
  onSort,
  sortConfig
}) => {
  const t = useTendersTranslations();

  // Filter columns for responsive display
  const getVisibleColumnsForWidth = () => {
    if (!visibleColumns || visibleColumns.length === 0) {
      // Fallback to original layout if no columns provided
      return [];
    }

    return visibleColumns.filter(column => {
      if (!column.responsive_breakpoint) return true;
      
      switch (column.responsive_breakpoint) {
        case 'sm':
          return tableWidth >= 640;
        case 'md':
          return tableWidth >= 768;
        case 'lg':
          return tableWidth >= 1024;
        case 'xl':
          return tableWidth >= 1280;
        default:
          return true;
      }
    });
  };

  const displayColumns = getVisibleColumnsForWidth();
  const totalColumns = displayColumns.length;

  const renderTableHeaders = () => {
    return displayColumns.map((column) => (
      <ResizableTableHeader
        key={column.id}
        column={column}
        onResize={(width) => onColumnResize?.(column.id, width)}
        onSort={onSort}
        sortConfig={sortConfig}
      />
    ));
  };

  const renderTableRow = (result: TenderAnalysisResult) => {
    const boardNames = getTenderBoards(result._id!);
    
    return (
      <TableRow
        key={result._id}
        className={cn(
          "cursor-pointer hover:bg-secondary/70 transition-colors",
          selectedResult?._id === result._id
            ? "bg-secondary-hover !border-l-2 !border-l-primary shadow-sm"
            : (!result.opened_at || result.opened_at === "")
              ? "bg-green-600/5 font-semibold !border-l-2 !border-l-green-600/70 shadow-sm"
              : isUpdatedAfterOpened(result)
                ? "bg-orange-700/5 !border-l-2 !border-l-orange-600"
                : "bg-background"
        )}
        onClick={(e) => onRowClick(result, e)}
      >
        {displayColumns.map((column) => {
          // Get the value based on column type
          let value: any;
          switch (column.field_name) {
            case 'name':
              value = result.tender_metadata.name;
              break;
            case 'organization':
              value = result.tender_metadata.organization;
              break;
            case 'initiation_date':
              value = result.tender_metadata.initiation_date;
              break;
            case 'submission_deadline':
              value = result.tender_metadata.submission_deadline;
              break;
            case 'tender_score':
              value = result.tender_score;
              break;
            case 'status':
              value = result.status;
              break;
            default:
              value = null;
          }

          return (
            <TableCellRenderer
              key={column.id}
              column={column}
              result={result}
              value={value}
              selectedResult={selectedResult}
              boardNames={boardNames}
              boardsLoading={boardsLoading}
              isUpdatedAfterOpened={isUpdatedAfterOpened}
              calculateDaysRemaining={calculateDaysRemaining}
              calculateProgressPercentage={calculateProgressPercentage}
              formatDate={formatDate}
              extractHour={extractHour}
              formatDateTime={formatDateTime}
              truncateText={truncateText}
              onStatusChange={onStatusChange}
              onUnopened={onUnopened}
              onDelete={onDelete}
              onAddToKanban={onAddToKanban}
              tableWidth={tableWidth}
            />
          );
        })}
      </TableRow>
    );
  };

  // If no columns are provided or visible, show fallback message
  if (!visibleColumns || visibleColumns.length === 0) {
    return (
      <div className="rounded-md border shadow-sm overflow-hidden">
        <div className="p-8 text-center text-muted-foreground">
          <p>No table layout configured. Please configure your table columns.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-md border shadow-sm overflow-hidden">
      <Table className="w-full">
        <TableHeader className="bg-white/20 shadow">
          <TableRow>
            {renderTableHeaders()}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={totalColumns} className="h-[500px]">
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
          ) : results.length === 0 ? (
            <TableRow>
              <TableCell colSpan={totalColumns} className="text-center text-muted-foreground py-20">
                {allResults.length > 0 ?
                  t('tenders.list.noTenders') :
                  selectedAnalysis ?
                    t('tenders.list.noResults') :
                    t('tenders.list.selectAnalysis')
                }
              </TableCell>
            </TableRow>
          ) : (
            results.map(renderTableRow)
          )}
        </TableBody>
      </Table>
    </div>
  );
};
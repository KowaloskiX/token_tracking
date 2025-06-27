// src/components/dashboard/tenders/table/TenderTable.tsx
// Simplest approach: Just add resize functionality to your original table

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
import { TenderRow } from "./TenderRow";
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
  
  // Optional props 
  visibleColumns?: any[];
  onColumnResize?: (columnId: string, width: number) => void;
  onSort?: (field: any) => void;
  sortConfig?: any;
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
  onAddToKanban
}) => {
  const t = useTendersTranslations();

  return (
    <div className="rounded-md border shadow-sm overflow-hidden">
      {/* 
        Key changes from your original:
        1. table-fixed -> table-auto (let Tailwind handle sizing)
        2. Add resize-x to headers for built-in CSS resize
        3. Use responsive Tailwind classes instead of conditional rendering
      */}
      <Table className="w-full table-auto">
        <TableHeader className="bg-white/20 shadow">
          <TableRow>
            <TableHead className={cn("text-xs resize-x overflow-hidden", tableWidth < 700 ? "w-[8%]" : "w-[4%]")}>
              {/* Empty header for source icons */}
            </TableHead>
            
            <TableHead className={cn("text-xs resize-x overflow-hidden", tableWidth < 700 ? "w-[40%]" : "w-[25%]")}>
              {t('tenders.list.order')}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[15%] hidden lg:table-cell">
              {t('tenders.details.client')}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[8%] hidden lg:table-cell">
              {t('tenders.details.publicationDate')}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[8%] hidden lg:table-cell">
              {/* Empty header for progress bar */}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[10%] hidden lg:table-cell">
              {t('tenders.details.submissionDeadline')}
            </TableHead>
            
            {/* Mobile date headers */}
            <TableHead className="text-xs resize-x overflow-hidden w-[12%] table-cell lg:hidden">
              {t('tenders.details.publicationDate')}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[20%] table-cell lg:hidden">
              {t('tenders.details.submissionDeadline')}
            </TableHead>
            
            <TableHead className="text-xs resize-x overflow-hidden w-[10%] hidden lg:table-cell">
              {t('tenders.list.boardStatus')}
            </TableHead>
            
            <TableHead className={cn("text-xs resize-x overflow-hidden", tableWidth < 700 ? "w-[15%]" : "w-[10%]")}>
              {t('tenders.list.relevance')}
            </TableHead>
            
            <TableHead className={cn("text-xs resize-x overflow-hidden", tableWidth < 700 ? "w-[3%]" : "w-[3%]")}>
              {/* Empty header for actions */}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
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
          ) : results.length === 0 ? (
            <TableRow>
              <TableCell colSpan={tableWidth >= 700 ? 9 : 6} className="text-center text-muted-foreground py-20">
                {allResults.length > 0 ?
                  t('tenders.list.noTenders') :
                  selectedAnalysis ?
                    t('tenders.list.noResults') :
                    t('tenders.list.selectAnalysis')
                }
              </TableCell>
            </TableRow>
          ) : (
            results.map((result: TenderAnalysisResult) => (
              <TenderRow
                key={result._id}
                result={result}
                selectedResult={selectedResult}
                tableWidth={tableWidth}
                boardNames={getTenderBoards(result._id!)}
                boardsLoading={boardsLoading}
                isUpdatedAfterOpened={isUpdatedAfterOpened}
                calculateDaysRemaining={calculateDaysRemaining}
                calculateProgressPercentage={calculateProgressPercentage}
                formatDate={formatDate}
                extractHour={extractHour}
                formatDateTime={formatDateTime}
                truncateText={truncateText}
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
  );
};
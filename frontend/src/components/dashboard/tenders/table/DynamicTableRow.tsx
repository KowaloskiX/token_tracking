// components/dashboard/tenders/table/DynamicTableRow.tsx

import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TenderAnalysisResult } from '@/types/tenders';
import { ColumnConfig, CriteriaColumnConfig, isCriteriaColumn } from '@/types/tableColumns';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import TenderSourceIcon from '../TenderSourceIcon';
import { TenderRowActions } from './TenderRowActions';
import { TenderBoardBadge } from './TenderBoardBadge';
import { ScoreIndicator } from './ScoreIndicator';
import { DeadlineProgressBar } from './DeadlineProgressBar';
import { useTendersTranslations } from '@/hooks/useTranslations';
import { formatDate, extractHour, formatDateTime, truncateText } from '@/utils/tenderDateUtils';

interface DynamicTableRowProps {
  result: TenderAnalysisResult;
  selectedResult: TenderAnalysisResult | null;
  columns: ColumnConfig[];
  isUpdatedAfterOpened: (result: TenderAnalysisResult) => boolean;
  calculateDaysRemaining: (deadlineStr: string) => number;
  getTenderBoards: (tenderId: string) => string[];
  boardsLoading: boolean;
  onRowClick: (result: TenderAnalysisResult, event?: React.MouseEvent) => void;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => void;
  onUnopened: (result: TenderAnalysisResult) => void;
  onDelete: (event: React.MouseEvent, resultId: string) => void;
  onAddToKanban: (result: TenderAnalysisResult) => void;
}

export const DynamicTableRow: React.FC<DynamicTableRowProps> = ({
  result,
  selectedResult,
  columns,
  isUpdatedAfterOpened,
  calculateDaysRemaining,
  getTenderBoards,
  boardsLoading,
  onRowClick,
  onStatusChange,
  onUnopened,
  onDelete,
  onAddToKanban
}) => {
  const t = useTendersTranslations();
  
  const hasUpdate = isUpdatedAfterOpened(result);
  const daysRemaining = calculateDaysRemaining(result.tender_metadata.submission_deadline);

  const voivodeship = result.location?.voivodeship &&
    result.location.voivodeship !== "UNKNOWN" ?
    result.location.voivodeship.charAt(0).toUpperCase() +
    result.location.voivodeship.slice(1).toLowerCase() :
    "-";

  // Helper function to get consistent cell styles
  const getCellStyle = (column: ColumnConfig) => ({
    width: `${column.width}px`,
    minWidth: `${column.minWidth}px`,
    maxWidth: `${column.maxWidth}px`,
  });

  const getCriteriaValue = (criteriaName: string): boolean | null => {
    if (!result.criteria_analysis || !Array.isArray(result.criteria_analysis)) {
      return null;
    }
    
    const criteriaResult = result.criteria_analysis.find(
      ca => ca.criteria === criteriaName
    );
    
    return criteriaResult?.analysis?.criteria_met ?? null;
  };

  const renderCriteriaCell = (column: CriteriaColumnConfig) => {
    const value = getCriteriaValue(column.criteriaName);
    
    if (value === null) {
      return (
        <div className="flex items-center justify-center">
          <span className="text-muted-foreground text-xs">-</span>
        </div>
      );
    }

    return (
      <div className="flex items-center justify-center">
        {value ? (
          <Badge variant="default" className="bg-green-600/80 hover:bg-green-600/80 text-xs">
            ✓ {t('tenders.criteria.met')}
          </Badge>
        ) : (
          <Badge variant="outline" className="border-red-200 text-red-600 text-xs">
            ✗ {t('tenders.criteria.notMet')}
          </Badge>
        )}
      </div>
    );
  };

  const renderColumnCell = (column: ColumnConfig): React.ReactElement => {
    switch (column.type) {
      case 'source':
        return (
          <TableCell 
            className="relative font-medium" 
            style={getCellStyle(column)}
          >
            {!result.opened_at && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="absolute top-1 left-1">
                      <Badge variant="outline" className="bg-green-400/20 text-green-700 border-green-700/20 px-0.5 flex items-center justify-center h-4">
                        <Sparkles className="h-2.5 w-2.5" />
                      </Badge>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p className="text-xs">{t('tenders.tooltips.updated', { time: formatDateTime(result.updated_at!) })}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            <TenderSourceIcon source={result.source} url={result.tender_url} />
          </TableCell>
        );

      case 'name':
        return (
          <TableCell style={getCellStyle(column)}>
            <div className="flex flex-col">
              <div className="flex items-center overflow-hidden">
                <span className="truncate">
                  {truncateText(result.tender_metadata.name, Math.floor(column.width / 8))}
                </span>
              </div>
              <div className="text-xs text-foreground/50 font-medium mt-0.5 flex gap-2 items-center">
                {voivodeship !== "-" && <span className="truncate">{truncateText(voivodeship, 25)}</span>}
                <span>{"#" + result.order_number}</span>
              </div>
            </div>
          </TableCell>
        );

      case 'organization':
        return (
          <TableCell style={getCellStyle(column)}>
            <span className="truncate block">
              {truncateText(result.tender_metadata.organization, Math.floor(column.width / 8))}
            </span>
          </TableCell>
        );

      case 'publication_date':
        return (
          <TableCell style={getCellStyle(column)}>
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {formatDate(result.tender_metadata.initiation_date || result.tender_metadata.submission_deadline)
                .split('.').slice(0, 2).join('.')}
            </span>
          </TableCell>
        );

      case 'deadline_progress':
        return (
          <TableCell className="px-2" style={getCellStyle(column)}>
            <DeadlineProgressBar
              createdAt={result.created_at}
              submissionDeadline={result.tender_metadata.submission_deadline}
              daysRemaining={daysRemaining}
            />
          </TableCell>
        );

      case 'submission_deadline':
        return (
          <TableCell style={getCellStyle(column)}>
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500 whitespace-nowrap">
                {!result.tender_metadata.submission_deadline ||
                  result.tender_metadata.submission_deadline.includes('NaN') ?
                  "-" : formatDate(result.tender_metadata.submission_deadline)}
              </span>
              <span className="text-xs text-foreground/50 font-medium">
                {extractHour(result.tender_metadata.submission_deadline)}
              </span>
            </div>
          </TableCell>
        );

      case 'board_status':
        return (
          <TableCell style={getCellStyle(column)}>
            <TenderBoardBadge 
              result={result} 
              getTenderBoards={getTenderBoards} 
              boardsLoading={boardsLoading} 
            />
          </TableCell>
        );

      case 'score':
        return (
          <TableCell style={getCellStyle(column)}>
            <ScoreIndicator score={result.tender_score} />
          </TableCell>
        );

      case 'criteria':
        return (
          <TableCell style={getCellStyle(column)}>
            {isCriteriaColumn(column) ? renderCriteriaCell(column) : (
              <span className="text-muted-foreground">-</span>
            )}
          </TableCell>
        );

      case 'actions':
        return (
          <TableCell className="p-1" style={getCellStyle(column)}>
            <TenderRowActions
              result={result}
              onStatusChange={onStatusChange}
              onUnopened={onUnopened}
              onDelete={onDelete}
              onAddToKanban={onAddToKanban}
            />
          </TableCell>
        );

      default:
        return (
          <TableCell style={getCellStyle(column)}>
            <span className="text-muted-foreground">-</span>
          </TableCell>
        );
    }
  };

  return (
    <TableRow
      className={cn(
        "cursor-pointer hover:bg-secondary/70 transition-colors",
        selectedResult?._id === result._id
          ? "bg-secondary-hover"
          : ((!result.opened_at || result.opened_at === "")
            ? "bg-green-600/5 font-semibold"
            : hasUpdate
              ? "bg-orange-700/5"
              : "bg-background"),
        selectedResult?._id === result._id
          ? "!border-l-2 !border-l-primary shadow-sm"
          : !result.opened_at && selectedResult?._id !== result._id
            ? "!border-l-2 !border-l-green-600/70 shadow-sm"
            : hasUpdate && result.opened_at && selectedResult?._id !== result._id
              ? "!border-l-2 !border-l-orange-600"
              : ""
      )}
      onClick={(e) => onRowClick(result, e)}
    >
      {columns.map((column) => (
        <React.Fragment key={column.id}>
          {renderColumnCell(column)}
        </React.Fragment>
      ))}
      
      {/* Column manager placeholder cell */}
      <TableCell className="w-10" />
    </TableRow>
  );
};
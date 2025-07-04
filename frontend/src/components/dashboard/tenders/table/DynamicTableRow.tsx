import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Sparkles, CheckCircle, XCircle } from 'lucide-react';
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

const getCriteriaValue = (criteriaName: string): { met: boolean | null; summary: string; confidence: number } => {
  if (!result.criteria_analysis || !Array.isArray(result.criteria_analysis)) {
    return { met: null, summary: '', confidence: 0 };
  }
  
  // Find criteria by name (which matches what we use for sorting)
  const criteriaResult = result.criteria_analysis.find(
    ca => ca.criteria === criteriaName
  );
  
  if (!criteriaResult) {
    return { met: null, summary: '', confidence: 0 };
  }
  
  return {
    met: criteriaResult.analysis?.criteria_met ?? null,
    summary: criteriaResult.analysis?.summary || '',
    confidence: criteriaResult.analysis?.confidence_level || 0
  };
};

const renderCriteriaCell = (column: CriteriaColumnConfig) => {
  const { met, summary, confidence } = getCriteriaValue(column.criteriaName);
  
  if (met === null) {
    return (
      <div className="flex items-center justify-center">
        <span className="text-muted-foreground text-xs">-</span>
      </div>
    );
  }

  // Handle different display modes
  if (column.displayMode === 'indicator') {
    // Simple indicator mode - just show met/not met with icon
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center justify-center gap-2 p-1 cursor-help">
              {met ? (
                <CheckCircle className="w-4 h-4 text-green-600" />
              ) : (
                <XCircle className="w-4 h-4 text-red-400" />
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[400px]">
            <div className="text-xs space-y-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${met ? 'bg-green-600' : 'bg-red-400'}`} />
                <p className="font-medium">{column.criteriaName}</p>
              </div>
              {summary && (
                <div className="border-t pt-2">
                  <p className="text-muted-foreground leading-relaxed">
                    {summary}
                  </p>
                </div>
              )}
              {confidence > 0 && (
                <div className="border-t pt-2">
                  <p className="text-muted-foreground text-[10px]">
                    Confidence: {(confidence * 100).toFixed(0)}%
                  </p>
                </div>
              )}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Text mode - show summary text (original behavior)
  if (!summary) {
    return (
      <div className="flex items-center justify-center">
        <span className="text-muted-foreground text-xs">-</span>
      </div>
    );
  }

  // Truncate summary based on column width
  const maxLength = Math.floor(column.width / 2); // Approximate character width
  const truncatedSummary = summary.length > maxLength 
    ? `${summary.substring(0, maxLength - 3)}...` 
    : summary;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-start gap-1 p-1 cursor-help w-full">
            {/* Status indicator */}
            <div className="flex-shrink-0 mt-0.5">
              {met ? (
                <div className="w-2 h-2 rounded-full bg-green-600/80" />
              ) : (
                <div className="w-2 h-2 rounded-full bg-red-400/80" />
              )}
            </div>
            
            {/* Criteria text */}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium leading-tight text-left">
                {truncatedSummary}
              </p>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[400px]">
          <div className="text-xs space-y-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${met ? 'bg-green-600' : 'bg-red-400'}`} />
              <p className="font-medium">{column.criteriaName}</p>
            </div>
            <div className="border-t pt-2">
              <p className="text-muted-foreground leading-relaxed">
                {summary}
              </p>
            </div>
            {confidence > 0 && (
              <div className="border-t pt-2">
                <p className="text-muted-foreground text-[10px]">
                  Confidence: {(confidence * 100).toFixed(0)}%
                </p>
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
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
            <div className="flex items-start overflow-hidden">
                <span className="line-clamp-3 font-medium">
                  {result.tender_metadata.name}
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
            <span className="truncate block font-medium">
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
          <TableCell className="p-0" style={getCellStyle(column)}>
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
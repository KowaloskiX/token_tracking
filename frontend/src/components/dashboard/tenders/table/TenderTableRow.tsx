import React from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Sparkles, MoreVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TenderAnalysisResult } from '@/types/tenders';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import TenderSourceIcon from '../TenderSourceIcon';
import { TenderRowActions } from './TenderRowActions';
import { TenderBoardBadge } from './TenderBoardBadge';
import { ScoreIndicator } from './ScoreIndicator';
import { useTendersTranslations } from '@/hooks/useTranslations';
import { formatDate, extractHour, formatDateTime, calculateProgressPercentage, truncateText } from '@/utils/tenderDateUtils';

interface TenderTableRowProps {
  result: TenderAnalysisResult;
  selectedResult: TenderAnalysisResult | null;
  tableWidth: number;
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

export const TenderTableRow: React.FC<TenderTableRowProps> = ({
  result,
  selectedResult,
  tableWidth,
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
      <TableCell className="relative font-medium">
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
      
      <TableCell>
        <div className="flex flex-col">
          <div className="flex items-center">
            {truncateText(result.tender_metadata.name, tableWidth < 700 ? 60 : 85)}
          </div>
          <div className="text-xs text-foreground/50 font-medium mt-0.5 flex gap-2 items-center">
            {voivodeship !== "-" && <span>{truncateText(voivodeship, 25)}</span>}
            <span>{"#" + result.order_number}</span>
          </div>
        </div>
      </TableCell>
      
      {tableWidth >= 700 && (
        <TableCell>{truncateText(result.tender_metadata.organization, 25)}</TableCell>
      )}
      
      {tableWidth >= 700 && (
        <>
          <TableCell>
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {formatDate(result.tender_metadata.initiation_date || result.tender_metadata.submission_deadline).split('.').slice(0, 2).join('.')}
            </span>
          </TableCell>
          <TableCell className="px-2">
            <div className="w-full bg-secondary-hover rounded-full h-2 -ml-5">
              <div
                className={`h-2 rounded-full ${!result.tender_metadata.submission_deadline ||
                  result.tender_metadata.submission_deadline.includes('NaN') ? "bg-gray-400" :
                  daysRemaining < 0 ? "bg-gray-400" :
                    daysRemaining <= 3 ? "bg-red-600 opacity-70" :
                      daysRemaining <= 10 ? "bg-amber-600 opacity-70" :
                        daysRemaining <= 21 ? "bg-yellow-600 opacity-70" :
                          "bg-green-600 opacity-70"
                  }`}
                style={{
                  width: `${!result.tender_metadata.submission_deadline ||
                    result.tender_metadata.submission_deadline.includes('NaN') ? "100" :
                    calculateProgressPercentage(result.created_at, result.tender_metadata.submission_deadline)
                    }%`
                }}
              ></div>
            </div>
          </TableCell>
          <TableCell>
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
        </>
      )}
      
      {tableWidth < 700 && (
        <>
          <TableCell>
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {formatDate(result.tender_metadata.initiation_date || result.tender_metadata.submission_deadline).split('.').slice(0, 2).join('.')}
            </span>
          </TableCell>
          <TableCell>
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
        </>
      )}
      
      {tableWidth >= 700 && (
        <TableCell>
          <TenderBoardBadge 
            result={result} 
            getTenderBoards={getTenderBoards} 
            boardsLoading={boardsLoading} 
          />
        </TableCell>
      )}
      
      <TableCell>
        <ScoreIndicator score={result.tender_score} />
      </TableCell>
      
      <TableCell className={cn("p-1", tableWidth < 700 && "p-0")}>
        <TenderRowActions
          result={result}
          onStatusChange={onStatusChange}
          onUnopened={onUnopened}
          onDelete={onDelete}
          onAddToKanban={onAddToKanban}
        />
      </TableCell>
    </TableRow>
  );
};
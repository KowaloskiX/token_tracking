import React from 'react';
import { TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { cn } from "@/lib/utils";
import { TableColumn } from '@/types/table';
import { TenderAnalysisResult } from "@/types/tenders";
import TenderSourceIcon from "../TenderSourceIcon";
import { ScoreIndicator } from "./ScoreIndicator";
import { StatusBadge } from "./StatusBadge";
import { TenderActions } from "./TenderActions";
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TableCellRendererProps {
  column: TableColumn;
  result: TenderAnalysisResult;
  value?: any;
  selectedResult: TenderAnalysisResult | null;
  boardNames: string[];
  boardsLoading: boolean;
  isUpdatedAfterOpened: (result: TenderAnalysisResult) => boolean;
  calculateDaysRemaining: (deadlineStr: string) => number;
  calculateProgressPercentage: (createdAt: string, deadlineStr: string) => number;
  formatDate: (dateStr: string) => string;
  extractHour: (dateStr: string) => string;
  formatDateTime: (dateTimeStr: string) => string;
  truncateText: (text: string, maxLength: number) => string;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => Promise<void>;
  onUnopened: (result: TenderAnalysisResult) => Promise<void>;
  onDelete: (event: React.MouseEvent, resultId: string) => Promise<void>;
  onAddToKanban: (result: TenderAnalysisResult) => void;
  tableWidth: number;
}

export const TableCellRenderer: React.FC<TableCellRendererProps> = ({
  column,
  result,
  value,
  selectedResult,
  boardNames,
  boardsLoading,
  isUpdatedAfterOpened,
  calculateDaysRemaining,
  calculateProgressPercentage,
  formatDate,
  extractHour,
  formatDateTime,
  truncateText,
  onStatusChange,
  onUnopened,
  onDelete,
  onAddToKanban,
  tableWidth
}) => {
  const t = useTendersTranslations();
  const renderCellContent = () => {
    switch (column.field_type) {
      case 'source':
        return <TenderSourceIcon source={result.source} url={result.tender_url} />;

      case 'text':
        if (column.field_name === 'name') {
          const voivodeship = result.location?.voivodeship &&
            result.location.voivodeship !== "UNKNOWN" ?
            result.location.voivodeship.charAt(0).toUpperCase() +
            result.location.voivodeship.slice(1).toLowerCase() :
            "-";

          return (
            <div className="flex flex-col">
              <div className="flex items-center">
                {truncateText(result.tender_metadata.name, tableWidth < 700 ? 60 : 85)}
              </div>
              <div className="text-xs text-foreground/50 font-medium mt-0.5 flex gap-2 items-center">
                {voivodeship !== "-" && <span>{truncateText(voivodeship, 25)}</span>}
                <span>{"#" + result.order_number}</span>
              </div>
            </div>
          );
        }
        return truncateText(value || '-', 30);

      case 'organization':
        return truncateText(result.tender_metadata.organization, 25);

      case 'date':
        const dateValue = column.field_name === 'initiation_date' 
          ? result.tender_metadata.initiation_date 
          : result.tender_metadata.submission_deadline;
        return (
          <span className="text-xs text-gray-500 whitespace-nowrap">
            {formatDate(dateValue || result.tender_metadata.submission_deadline).split('.').slice(0, 2).join('.')}
          </span>
        );

      case 'deadline':
        return (
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
        );

      case 'progress':
        const daysRemaining = calculateDaysRemaining(result.tender_metadata.submission_deadline);
        return (
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
        );

      case 'status':
        return (
          <StatusBadge 
            result={result} 
            boardNames={boardNames} 
            boardsLoading={boardsLoading} 
          />
        );

      case 'score':
        return <ScoreIndicator score={result.tender_score} />;

      case 'criteria':
        if (!column.criteria_name) return '-';
        
        const criteriaResult = result.criteria_analysis?.find(ca => ca.criteria === column.criteria_name);
        
        if (!criteriaResult) {
          return (
            <div className="flex items-center justify-center">
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </div>
          );
        }

        const isMet = criteriaResult.analysis?.criteria_met === true;
        const confidence = criteriaResult.analysis?.confidence_level || 0;
        const summary = criteriaResult.analysis?.summary || '';
        
        return (
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center justify-center">
                  {isMet ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-600" />
                  )}
                </div>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[300px] max-h-[200px] overflow-y-auto" sideOffset={5}>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">
                      {isMet ? t('tenders.criteria.met') : t('tenders.criteria.notMet')}
                    </span>
                  </div>
                  {summary && (
                    <div className="text-xs text-muted-foreground break-words">
                      {summary}
                    </div>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );

      case 'actions':
        return (
          <TenderActions
            result={result}
            onStatusChange={onStatusChange}
            onUnopened={onUnopened}
            onDelete={onDelete}
            onAddToKanban={onAddToKanban}
            tableWidth={tableWidth}
          />
        );

      default:
        return value || '-';
    }
  };

  return (
    <TableCell 
      className={cn(
        column.field_type === 'progress' && "px-2",
        column.field_type === 'actions' && tableWidth < 700 ? "p-0" : "p-1",
        column.field_type === 'criteria' && "text-center",
        column.field_type === 'source' && "relative font-medium"
      )}
      style={{ 
        width: `${column.width}px`,
        minWidth: `${column.min_width}px`,
        maxWidth: column.max_width ? `${column.max_width}px` : undefined
      }}
    >
      {renderCellContent()}
    </TableCell>
  );
};
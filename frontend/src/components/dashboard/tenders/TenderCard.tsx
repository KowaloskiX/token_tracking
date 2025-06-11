import React from 'react';
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertCircle,
  Archive,
  EyeOff,
  Calendar as CalendarIcon,
  CheckCircle,
  ListCheck,
  MoreVertical,
  Sparkles,
  Trash,
  Clock,
  MapPin,
  Building,
  RefreshCw
} from "lucide-react";
import TenderSourceIcon from "./TenderSourceIcon";
import { TenderAnalysisResult } from "@/types/tenders";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

// Helper function to format date/time
const formatDateTime = (dateTimeStr: string) => {
  if (!dateTimeStr) return "-";
  try {
    const date = new Date(dateTimeStr);
    if (isNaN(date.getTime())) return "-";
    return date.toLocaleString('pl-PL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (e) {
    console.error("Error formatting date:", dateTimeStr, e);
    return "-";
  }
};

// Props Interface
interface TenderCardProps {
  result: TenderAnalysisResult;
  isSelected: boolean;
  onClick: () => void;
  onDelete: (event: React.MouseEvent, resultId: string) => Promise<void>;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => Promise<void>;
  onUnopened: (result: TenderAnalysisResult) => Promise<void>;
  onAddToKanban: (result: TenderAnalysisResult) => void;
  hasUpdate: boolean;
  formatDate: (dateStr: string) => string;
  calculateDaysRemaining: (deadlineStr: string) => number;
  calculateProgressPercentage: (createdAt: string, deadlineStr: string) => number;
}

// Component Definition
const TenderCard: React.FC<TenderCardProps> = ({
  result,
  isSelected,
  onClick,
  onDelete,
  onStatusChange,
  onUnopened,
  onAddToKanban,
  hasUpdate,
  formatDate,
  calculateDaysRemaining,
  calculateProgressPercentage,
}) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  
  const daysRemaining = calculateDaysRemaining(result.tender_metadata.submission_deadline || "");

  const voivodeship =
    result.location?.voivodeship && result.location.voivodeship !== "UNKNOWN"
      ? result.location.voivodeship.charAt(0).toUpperCase() +
        result.location.voivodeship.slice(1).toLowerCase()
      : null;

  const progressColor =
    !result.tender_metadata.submission_deadline ||
    result.tender_metadata.submission_deadline.includes("NaN")
      ? "bg-stone-300"
      : daysRemaining < 0
      ? "bg-stone-300"
      : daysRemaining <= 3
      ? "bg-red-500/70"
      : daysRemaining <= 10
      ? "bg-amber-600/70"
      : daysRemaining <= 21
      ? "bg-yellow-600/70"
      : "bg-green-600/70";

  const getStatusBadge = () => {
    const status = result.status || "inactive";
    switch (status) {
      case "inactive":
        return (
          <Badge
            variant="outline"
            className="border-zinc-200 text-zinc-400 font-normal"
          >
            {t('tenders.status.inactive')}
          </Badge>
        );
      case "active":
        return (
          <Badge
            variant="default"
            className="bg-green-600/80 hover:bg-green-600/80 font-normal"
          >
            {t('tenders.status.active')}
          </Badge>
        );
      case "archived":
        return (
          <Badge
            variant="secondary"
            className="bg-secondary text-primary/70 hover:bg-secondary font-normal"
          >
            {t('tenders.status.archived')}
          </Badge>
        );
      default:
        return <Badge variant="outline">{t('tenders.status.unknown')}</Badge>;
    }
  };

  const ScoreIndicator = ({ score }: { score: number }) => {
    const percentage = score * 100;
    let color = "bg-red-500/80";
    if (percentage >= 60) color = "bg-green-600/80";
    else if (percentage >= 45) color = "bg-yellow-500/80";
    return (
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${color}`} />
        <span>{percentage.toFixed(1)}%</span>
      </div>
    );
  };

  // Get formatted dates for timeline
  const publicationDate = formatDate(
    result.tender_metadata.initiation_date ||
    result.tender_metadata.submission_deadline ||
    ""
  );
  
  const submissionDate = !result.tender_metadata.submission_deadline ||
    result.tender_metadata.submission_deadline.includes("NaN")
    ? "-"
    : formatDate(result.tender_metadata.submission_deadline || "");
    
  const progress = calculateProgressPercentage(
    result.created_at || new Date().toISOString(),
    result.tender_metadata.submission_deadline || ""
  );

  const getDaysRemainingText = () => {
    if (!result.tender_metadata.submission_deadline ||
        result.tender_metadata.submission_deadline.includes("NaN") ||
        isNaN(daysRemaining)) {
      return "-";
    }
    
    if (daysRemaining < 0) return t('tenders.details.finished');
    if (daysRemaining === 0) return t('tenders.details.today');
    if (daysRemaining === 1) return `1 ${t('tenders.details.day')}`;
    return `${daysRemaining} ${t('tenders.details.days')}`;
  };

  return (
    <div
      className={cn(
        "relative border rounded-md p-4 mb-2 cursor-pointer transition-all",
        "hover:bg-secondary/70 hover:shadow-sm",
        isSelected
          ? "bg-secondary-hover border-primary/30 shadow-md"
          : !result.opened_at || result.opened_at === ""
          ? "bg-green-600/5 border-l-4 border-l-green-600/70"
          : hasUpdate
          ? "bg-orange-700/5 border-l-4 border-l-orange-600"
          : "bg-background border"
      )}
      onClick={onClick}
    >
      {/* Main Content Layout */}
      <div className="flex flex-col space-y-3">
        {/* Top Row: Title and Source INLINE */}
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0 flex items-start">            
            <div className="flex-1 min-w-0 flex flex-col">
              {/* Title inline with source icon and status badges */}
              <div className='flex gap-2 items-start'>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className='flex items-center gap-1'>
                    <div className="flex-shrink-0 p-1 bg-secondary/60 rounded-md mr-1 mt-0.5">
                    <TenderSourceIcon source={result.source} url={result.tender_url} />
                  </div>
                    <h3 className="text-sm font-medium line-clamp-2 leading-snug">
                      {result.tender_metadata.name}
                    </h3> 
                  </div>

                    {/* Notification Badges - now placed here instead of absolute positioning */}
                    {!result.opened_at && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              className="bg-green-400/20 text-green-700 border-green-700/20 px-1 flex items-center justify-center h-5 flex-shrink-0"
                            >
                              <Sparkles className="h-3 w-3 mr-1" />
                              {t('tenders.details.new')}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            <p className="text-xs">{t('tenders.tooltips.newTender')}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                    
                    {hasUpdate && result.opened_at && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              className="bg-orange-400/20 text-orange-700 border-orange-700/20 px-1 flex items-center justify-center h-5 flex-shrink-0"
                            >
                              <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                              {t('tenders.details.updated')}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            <p className="text-xs">{t('tenders.tooltips.updatedAfterOpen')}</p>
                            {result.updated_at && (
                              <p className="text-xs">{t('tenders.tooltips.updateTime')}: {formatDateTime(result.updated_at)}</p>
                            )}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                
                  {/* Organization and metadata below title */}
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
                    <Badge variant="outline" className="text-xs font-mono px-1.5 py-0">
                      #{result.order_number}
                    </Badge>
                    <div className="flex items-center text-xs text-stone-500">
                      <Building className="h-3 w-3 mr-1 flex-shrink-0" />
                      <span className="truncate max-w-[200px] sm:max-w-[300px] md:max-w-[400px]">
                        {result.tender_metadata.organization}
                      </span>
                    </div>
                    {voivodeship && (
                      <div className="flex items-center text-xs text-stone-500">
                        <MapPin className="h-3 w-3 mr-1 flex-shrink-0" />
                        <span>{voivodeship}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Actions Button */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => e.stopPropagation()}
                className="h-8 w-8 p-0 ml-2 flex-shrink-0"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {result.status !== "active" && (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(result._id!, "active");
                  }}
                >
                  <CheckCircle className="mr-2 h-4 w-4 text-green-500" />
                  {t('tenders.status.activate')}
                </DropdownMenuItem>
              )}
              {result.status === "active" && (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(result._id!, "inactive");
                  }}
                >
                  <AlertCircle className="mr-2 h-4 w-4 text-gray-500" />
                  {t('tenders.status.deactivate')}
                </DropdownMenuItem>
              )}
              {result.status !== "archived" && (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(result._id!, "archived");
                  }}
                >
                  <Archive className="mr-2 h-4 w-4 text-gray-700" />
                  {t('tenders.status.archive')}
                </DropdownMenuItem>
              )}

              {result.opened_at && result.opened_at !== "" && (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    onUnopened(result);
                  }}
                >
                  <EyeOff className="mr-2 h-4 w-4 text-gray-700" />
                  {t('tenders.status.markUnread')}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation();
                  onAddToKanban(result);
                }}
                disabled={result.status !== "active"}
              >
                <ListCheck className="mr-2 h-4 w-4" />
                {t('tenders.actions.addToKanban')}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(e, result._id!); 
                }}
                className="text-destructive focus:text-destructive"
              >
                <Trash className="mr-2 h-4 w-4" />
                {commonT('delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Bottom Row: Meta information */}
        <div className="flex flex-wrap justify-between items-center gap-y-2 gap-x-4 pt-2 border-t border-border/50">
          {/* Left Side: Enhanced Timeline Visualization */}
          <div className="flex-1 min-w-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex flex-col space-y-1">
                    {/* Timeline visualization */}
                    <div className="flex items-center space-x-1 mb-1">
                      <div className="flex items-center text-xs text-stone-500 min-w-[85px]">
                        <Clock className="h-3 w-3 mr-1 flex-shrink-0" />
                        <span className="whitespace-nowrap">{publicationDate}</span>
                      </div>
                      
                      <div className="px-1 flex-1 flex items-center">
                        <div className="h-1 bg-secondary-hover rounded-full w-full relative">
                          <div 
                            className={`absolute top-0 left-0 h-1 rounded-full transition-all duration-500 ${progressColor}`} 
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </div>
                      
                      <div className="flex items-center text-xs text-stone-500 min-w-[85px] justify-end">
                        <span className="whitespace-nowrap">{submissionDate}</span>
                        <CalendarIcon className="h-3 w-3 ml-1 flex-shrink-0" />
                      </div>
                    </div>
                    
                    {/* Date labels and remaining days */}
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-stone-500 font-medium">
                        {t('tenders.details.publicationDate')}
                      </span>
                      
                      {!result.tender_metadata.submission_deadline ||
                      result.tender_metadata.submission_deadline.includes("NaN") ? null : (
                        <Badge
                          className="text-xs px-1.5 py-0 leading-none"
                          variant="outline"
                        >
                          <span
                            className={`text-xs font-medium ${
                              daysRemaining < 0
                                ? "text-stone-500 opacity-70"
                                : daysRemaining <= 3
                                ? "text-red-600 opacity-70"
                                : daysRemaining <= 10
                                ? "text-amber-600 opacity-70"
                                : daysRemaining <= 21
                                ? "text-yellow-600 opacity-70"
                                : "text-green-600 opacity-70"
                            }`}
                          >
                            {getDaysRemainingText()}
                          </span>
                        </Badge>
                      )}
                      
                      <span className="text-xs text-stone-500 font-medium">
                        {t('tenders.details.submissionDate')}
                      </span>
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">{t('tenders.details.timeElapsed')}: {progress.toFixed(0)}%</p>
                  {daysRemaining > 0 && <p className="text-xs">{t('tenders.details.timeRemaining')}: {daysRemaining} {t('tenders.details.days')}</p>}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Right Side: Status and Score */}
          <div className="flex items-center space-x-3 flex-shrink-0">
            {getStatusBadge()}
            <Badge className="bg-secondary text-primary gap-1.5 py-1 px-2">
              <ScoreIndicator score={result.tender_score} />
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TenderCard;
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Button } from "@/components/ui/button";
import { Calendar, Clock, MoreHorizontal, Trash } from "lucide-react";
import { KanbanTenderItem } from "@/types/kanban";
import { TenderAnalysisResult } from "@/types/tenders";
import { format } from "date-fns";
import TenderSourceIcon from "../TenderSourceIcon";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

// Helper function to safely format dates
const safeFormatDate = (dateString: string | null | undefined): string | null => {
  if (!dateString) return null;
  
  const date = new Date(dateString);
  return !isNaN(date.getTime()) ? format(date, "dd.MM.yyyy") : null;
};

interface KanbanItemProps {
  item: KanbanTenderItem;
  onDelete: () => void;
  backgroundColor?: string;
  onDragStart: (e: React.DragEvent<HTMLDivElement>, itemId: string) => void;
  activeTenders: TenderAnalysisResult[];
  onTenderSelect?: (tenderResultId: string) => void;
}

export function KanbanItem({
  item,
  onDelete,
  backgroundColor,
  onDragStart,
  activeTenders,
  onTenderSelect
}: KanbanItemProps) {
  const router = useRouter();
  const tender = activeTenders.find(t => t._id === item.tender_analysis_result_id);
  const tenderName = tender?.tender_metadata?.name || "Loading...";
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();
  
  // Format dates if they exist and are valid
  const initiationDate = safeFormatDate(tender?.tender_metadata?.initiation_date);
  const submissionDeadline = safeFormatDate(tender?.tender_metadata?.submission_deadline);

  const handleClick = () => {
    if (onTenderSelect && item.tender_analysis_result_id) {
      onTenderSelect(item.tender_analysis_result_id);
    } else {
      router.push(`/dashboard/tenders/${item.tender_analysis_result_id}`);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete();
  };

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, item.id)}
      className="group p-2 relative shadow-sm rounded-md transition-colors cursor-grab active:cursor-grabbing shadow-sm hover:shadow"
      style={{
        backgroundColor: backgroundColor ? `${backgroundColor}20` : undefined,
      }}
    >
      <div className="hover:bg-opacity-20 transition-colors rounded-md">
        <div className="p-3">
          {/* Top section with ID and Menu */}
          <div className="flex justify-between items-start mb-2">
            <div className="flex items-center gap-2">
              {tender?.source && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <TenderSourceIcon source={tender.source} url={tender.tender_url} />
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {tender.source}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
              <span className="text-xs font-mono text-muted-foreground/50">
                #{tender?.order_number}
              </span>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem
                  className="text-destructive"
                  onClick={handleDeleteClick}
                >
                  <Trash className="mr-2 h-4 w-4" />
                  {tCommon('delete')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          {/* Tender name */}
          <div 
            className="flex items-start gap-2 cursor-pointer mb-2"
            onClick={handleClick}
          >
            <HoverCard>
              <HoverCardTrigger asChild>
                <h3 className="text-sm font-medium line-clamp-2">
                  {tenderName}
                </h3>
              </HoverCardTrigger>
              <HoverCardContent className="max-w-xs p-2 text-sm" side="top">
                {tenderName}
              </HoverCardContent>
            </HoverCard>
          </div>
          
          {/* Dates section */}
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            {initiationDate && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                <span>{tCommon('published')}: {initiationDate}</span>
              </div>
            )}
            {submissionDeadline && (
              <div className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                <span>{tCommon('deadline')}: {submissionDeadline}</span>
              </div>
            )}
          </div>
          
        </div>
      </div>
      
      {/* Visual indicator for dragging */}
      <div className="absolute inset-0 pointer-events-none opacity-0 group-active:opacity-100 bg-primary/10 rounded-md border-2 border-primary/30"></div>
    </div>
  );
}
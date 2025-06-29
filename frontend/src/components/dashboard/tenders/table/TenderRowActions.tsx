import React from 'react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { 
  CheckCircle, 
  AlertCircle, 
  Archive, 
  EyeOff, 
  Trash, 
  MoreVertical, 
  ListCheck 
} from 'lucide-react';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderRowActionsProps {
  result: TenderAnalysisResult;
  onStatusChange: (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => void;
  onUnopened: (result: TenderAnalysisResult) => void;
  onDelete: (event: React.MouseEvent, resultId: string) => void;
  onAddToKanban: (result: TenderAnalysisResult) => void;
}

export const TenderRowActions: React.FC<TenderRowActionsProps> = ({
  result,
  onStatusChange,
  onUnopened,
  onDelete,
  onAddToKanban
}) => {
  const t = useTendersTranslations();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="ghost" 
          size="sm" 
          className="h-6 w-6 p-0" 
          onClick={(e) => e.stopPropagation()}
        >
          <MoreVertical className="h-3 w-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {result.status !== 'active' && (
          <DropdownMenuItem 
            onClick={(e) => { 
              e.stopPropagation(); 
              onStatusChange(result._id!, 'active'); 
            }}
          >
            <CheckCircle className="mr-2 h-4 w-4 text-green-500" />
            {t('tenders.status.activate')}
          </DropdownMenuItem>
        )}
        
        {result.status === 'active' && (
          <DropdownMenuItem 
            onClick={(e) => { 
              e.stopPropagation(); 
              onStatusChange(result._id!, 'inactive'); 
            }}
          >
            <AlertCircle className="mr-2 h-4 w-4 text-gray-500" />
            {t('tenders.status.deactivate')}
          </DropdownMenuItem>
        )}
        
        {result.status !== 'archived' && (
          <DropdownMenuItem 
            onClick={(e) => { 
              e.stopPropagation(); 
              onStatusChange(result._id!, 'archived'); 
            }}
          >
            <Archive className="mr-2 h-4 w-4 text-gray-700" />
            {t('tenders.status.archive')}
          </DropdownMenuItem>
        )}

        {(result.opened_at && result.opened_at !== '') && (
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
          onClick={(e) => onDelete(e, result._id!)} 
          className="text-destructive focus:text-destructive"
        >
          <Trash className="mr-2 h-4 w-4" />
          {t('tenders.status.delete')}
        </DropdownMenuItem>
        
        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation();
            onAddToKanban(result);
          }}
          disabled={result.status !== 'active'}
        >
          <ListCheck className="mr-2 h-4 w-4" />
          {t('tenders.kanban.addToKanban')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
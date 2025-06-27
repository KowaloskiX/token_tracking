// src/components/dashboard/tenders/table/ResizableTableHeader.tsx

import React, { useState, useRef, useCallback } from 'react';
import { TableHead } from "@/components/ui/table";
import { ArrowUpDown, Clock, CalendarIcon, Percent, RefreshCw, GripVertical } from 'lucide-react';
import { cn } from "@/lib/utils";
import { TableColumn, SortableField } from '@/types/table';
import { useTendersTranslations } from "@/hooks/useTranslations";

interface ResizableTableHeaderProps {
  column: TableColumn;
  onResize: (width: number) => void;
  onSort?: (field: SortableField) => void;
  sortConfig?: {
    field: SortableField;
    direction: 'asc' | 'desc';
  } | null;
  isResizing?: boolean;
  onResizeStart?: () => void;
  onResizeEnd?: () => void;
}

export const ResizableTableHeader: React.FC<ResizableTableHeaderProps> = ({
  column,
  onResize,
  onSort,
  sortConfig,
  isResizing = false,
  onResizeStart,
  onResizeEnd
}) => {
  const t = useTendersTranslations();
  const [isDragging, setIsDragging] = useState(false);
  const headerRef = useRef<HTMLTableCellElement>(null);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setIsDragging(true);
    startXRef.current = e.clientX;
    startWidthRef.current = column.width;
    onResizeStart?.();

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDragging && moveEvent.clientX !== startXRef.current) {
        const diff = moveEvent.clientX - startXRef.current;
        const newWidth = Math.max(
          column.min_width,
          Math.min(column.max_width || 500, startWidthRef.current + diff)
        );
        onResize(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      onResizeEnd?.();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [column.width, column.min_width, column.max_width, onResize, onResizeStart, onResizeEnd, isDragging]);

  const handleSort = useCallback(() => {
    if (column.sortable && onSort && !isDragging) {
      const sortableFields: SortableField[] = [
        'submission_deadline', 
        'tender_score', 
        'updated_at', 
        'created_at', 
        'initiation_date'
      ];
      
      if (sortableFields.includes(column.field_name as SortableField)) {
        onSort(column.field_name as SortableField);
      }
    }
  }, [column.sortable, column.field_name, onSort, isDragging]);

  const getSortIcon = () => {
    switch (column.field_name) {
      case 'submission_deadline':
        return <CalendarIcon className="mr-2 h-4 w-4" />;
      case 'tender_score':
        return <Percent className="mr-2 h-4 w-4" />;
      case 'updated_at':
        return <RefreshCw className="mr-2 h-4 w-4" />;
      case 'created_at':
      case 'initiation_date':
        return <Clock className="mr-2 h-4 w-4" />;
      default:
        return column.sortable ? <ArrowUpDown className="mr-2 h-4 w-4" /> : null;
    }
  };

  const getSortIndicator = () => {
    if (sortConfig?.field === column.field_name) {
      return sortConfig.direction === 'asc' ? '↑' : '↓';
    }
    return '';
  };

  const getDisplayName = () => {
    switch (column.field_name) {
      case 'submission_deadline':
        return t('tenders.details.submissionDeadline');
      case 'tender_score':
        return t('tenders.list.relevance');
      case 'updated_at':
        return t('tenders.filters.sortByLastUpdate');
      case 'created_at':
        return t('tenders.filters.sortByCreationDate');
      case 'initiation_date':
        return t('tenders.details.publicationDate');
      case 'name':
        return t('tenders.list.order');
      case 'organization':
        return t('tenders.details.client');
      case 'status':
        return t('tenders.list.boardStatus');
      default:
        return column.display_name;
    }
  };

  return (
    <TableHead
      ref={headerRef}
      className={cn(
        "text-xs relative group select-none border-r border-border/40",
        column.sortable && !isDragging && "cursor-pointer hover:bg-muted/50",
        isDragging && "select-none bg-muted/30"
      )}
      style={{ 
        width: `${column.width}px`,
        minWidth: `${column.min_width}px`,
        maxWidth: column.max_width ? `${column.max_width}px` : undefined,
        position: 'relative'
      }}
      onClick={handleSort}
    >
      <div className="flex items-center justify-between pr-4 h-full">
        <div className="flex items-center min-w-0 flex-1">
          {getSortIcon()}
          <span className={cn(
            "truncate",
            column.field_type === 'criteria' && "max-w-[100px]"
          )} title={getDisplayName()}>
            {getDisplayName()}
          </span>
          {getSortIndicator() && (
            <span className="ml-1 text-xs font-bold">{getSortIndicator()}</span>
          )}
        </div>
      </div>

      {/* Resize handle */}
      <div
        className={cn(
          "absolute right-0 top-0 w-2 h-full cursor-col-resize group-hover:bg-primary/20 hover:bg-primary/30 transition-colors z-10",
          isDragging && "bg-primary/40"
        )}
        onMouseDown={handleMouseDown}
        onClick={(e) => e.stopPropagation()}
        style={{ 
          right: '-1px',
          background: isDragging ? 'rgba(var(--primary), 0.4)' : undefined 
        }}
      >
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-4 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity">
          <GripVertical className="w-3 h-3 text-muted-foreground" />
        </div>
      </div>
    </TableHead>
  );
};
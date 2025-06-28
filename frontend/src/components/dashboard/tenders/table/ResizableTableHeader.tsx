// src/components/dashboard/tenders/table/ResizableTableHeader.tsx
import React, { useState, useRef, useCallback, useEffect } from 'react';
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
}

export const ResizableTableHeader: React.FC<ResizableTableHeaderProps> = ({
  column,
  onResize,
  onSort,
  sortConfig
}) => {
  const t = useTendersTranslations();
  const [isResizing, setIsResizing] = useState(false);
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartWidth, setResizeStartWidth] = useState(0);
  const headerRef = useRef<HTMLTableCellElement>(null);
  const resizeHandleRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setIsResizing(true);
    setResizeStartX(e.clientX);
    setResizeStartWidth(column.width);

    // Add global styles for better UX during resize
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.body.style.pointerEvents = 'none';
    
    // Re-enable pointer events on the resize handle
    if (resizeHandleRef.current) {
      resizeHandleRef.current.style.pointerEvents = 'auto';
    }

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const diff = moveEvent.clientX - resizeStartX;
      const newWidth = Math.max(
        column.min_width,
        Math.min(column.max_width || 800, resizeStartWidth + diff)
      );
      onResize(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      
      // Restore global styles
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.body.style.pointerEvents = '';
      
      if (resizeHandleRef.current) {
        resizeHandleRef.current.style.pointerEvents = '';
      }
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [column.width, column.min_width, column.max_width, onResize, resizeStartX, resizeStartWidth]);

  const handleSort = useCallback(() => {
    if (column.sortable && onSort && !isResizing) {
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
  }, [column.sortable, column.field_name, onSort, isResizing]);

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

  // Prevent click events during resize
  const handleHeaderClick = useCallback((e: React.MouseEvent) => {
    if (!isResizing) {
      handleSort();
    }
  }, [isResizing, handleSort]);

  return (
    <TableHead
      ref={headerRef}
      className={cn(
        "text-xs relative group select-none border-r border-border/40 transition-colors",
        column.sortable && !isResizing && "cursor-pointer hover:bg-muted/50",
        isResizing && "bg-muted/30"
      )}
      style={{ 
        width: `${column.width}px`,
        minWidth: `${column.min_width}px`,
        maxWidth: column.max_width ? `${column.max_width}px` : undefined,
        position: 'relative'
      }}
      onClick={handleHeaderClick}
    >
      <div className="flex items-center justify-between pr-4 h-full">
        <div className="flex items-center min-w-0 flex-1">
          {getSortIcon()}
          <span className={cn(
            "truncate font-medium",
            column.field_type === 'criteria' && "max-w-[100px]"
          )} title={getDisplayName()}>
            {getDisplayName()}
          </span>
          {getSortIndicator() && (
            <span className="ml-1 text-xs font-bold text-primary">{getSortIndicator()}</span>
          )}
        </div>
      </div>

      {/* Improved resize handle */}
      <div
        ref={resizeHandleRef}
        className={cn(
          "absolute right-0 top-0 w-1 h-full cursor-col-resize z-20 transition-all duration-150",
          "hover:w-2 hover:bg-primary/30",
          "group-hover:bg-primary/20",
          isResizing && "w-2 bg-primary/50"
        )}
        onMouseDown={handleMouseDown}
        onClick={(e) => e.stopPropagation()}
        style={{ 
          right: '-2px'
        }}
      >
        {/* Visual indicator */}
        <div className={cn(
          "absolute right-0 top-1/2 -translate-y-1/2 w-4 h-8 flex items-center justify-center transition-opacity",
          "opacity-0 group-hover:opacity-100 hover:opacity-100",
          isResizing && "opacity-100"
        )}>
          <GripVertical className="w-3 h-3 text-primary" />
        </div>
        
        {/* Invisible expanded hit area for easier grabbing */}
        <div 
          className="absolute inset-0 w-4 -translate-x-2"
          style={{ cursor: 'col-resize' }}
        />
      </div>
    </TableHead>
  );
};
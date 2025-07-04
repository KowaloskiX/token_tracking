import React, { useState, useRef, useCallback } from 'react';
import { TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ColumnConfig, CriteriaColumnConfig, SortDirection, StandardColumnConfig, isCriteriaColumn } from '@/types/tableColumns';
import { useTendersTranslations } from '@/hooks/useTranslations';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface ResizableTableHeaderProps {
    columns: ColumnConfig[];
    sortConfig: {
        columnId: string;
        direction: SortDirection;
    } | null;
    onSort: (columnId: string, direction: SortDirection) => void;
    onColumnResize: (columnId: string, newWidth: number) => void;
    onOpenTableLayout: () => void;
    isResizeDisabled?: boolean; // NEW: Add prop to disable resizing
}

export const ResizableTableHeader: React.FC<ResizableTableHeaderProps> = ({
    columns,
    sortConfig,
    onSort,
    onColumnResize,
    onOpenTableLayout,
    isResizeDisabled = false, // NEW: Default to false
}) => {
    const t = useTendersTranslations();
    const [resizing, setResizing] = useState<string | null>(null);
    const headerRef = useRef<HTMLTableRowElement>(null);
    
    // Use refs to track resizing state for event handlers
    const resizingRef = useRef<string | null>(null);
    const resizeStartXRef = useRef<number>(0);
    const resizeStartWidthRef = useRef<number>(0);
    const justFinishedResizingRef = useRef<boolean>(false);

    const handleSort = (column: ColumnConfig) => {
        if (!column.sortable) return;
        
        // Prevent sorting if we just finished resizing
        if (justFinishedResizingRef.current) {
            justFinishedResizingRef.current = false;
            return;
        }

        // For criteria columns, we need to use the criteria name as the sort identifier
        // This matches what the data structure expects in useTenderTableData.tsx
        const sortIdentifier = isCriteriaColumn(column) 
            ? (column as CriteriaColumnConfig).criteriaName 
            : column.id;

        let newDirection: SortDirection = 'asc';

        if (sortConfig?.columnId === sortIdentifier) {
            // Cycle through: asc → desc → null → asc
            if (sortConfig.direction === 'asc') {
                newDirection = 'desc';
            } else if (sortConfig.direction === 'desc') {
                newDirection = null;
            } else {
                newDirection = 'asc'; // null → asc (this handles the case when direction is null)
            }
        } else {
            // Set default direction based on column type for first click
            if (column.type === 'score') {
                newDirection = 'desc'; // Scores default to descending (highest first)
            } else if (column.type === 'criteria') {
                newDirection = 'asc'; // Criteria default to ascending (met criteria first)
            } else if (column.id === 'updated_at' || column.id === 'created_at') {
                newDirection = 'desc'; // Dates default to descending (newest first)
            } else {
                newDirection = 'asc'; // Everything else defaults to ascending
            }
        }

        // Pass the sort identifier to the parent component
        onSort(sortIdentifier, newDirection);
    };

    const getSortIcon = (column: ColumnConfig) => {
        if (!column.sortable) return null;

        // Check if this column is currently being sorted using the same identifier logic
        const sortIdentifier = isCriteriaColumn(column) 
            ? (column as CriteriaColumnConfig).criteriaName 
            : column.id;

        const isActive = sortConfig?.columnId === sortIdentifier;

        if (!isActive) {
            return <ArrowUpDown className="h-3 w-3 opacity-40 group-hover:opacity-60 transition-opacity" />;
        }

        if (sortConfig?.direction === 'asc') {
            return <ArrowUp className="h-3 w-3 text-foreground" />;
        } else if (sortConfig?.direction === 'desc') {
            return <ArrowDown className="h-3 w-3 text-foreground" />;
        }

        return <ArrowUpDown className="h-3 w-3 opacity-40 group-hover:opacity-60 transition-opacity" />;
    };

    const handleResizeStart = useCallback((e: React.MouseEvent, columnId: string) => {
        e.preventDefault();
        e.stopPropagation();

        // Don't allow resizing if disabled (when sidebar is open)
        if (isResizeDisabled) return;

        const column = columns.find(col => col.id === columnId);
        if (!column || !column.resizable) return;

        // Update both state and ref
        setResizing(columnId);
        resizingRef.current = columnId;
        resizeStartXRef.current = e.clientX;
        resizeStartWidthRef.current = column.width;

        const handleMouseMove = (e: MouseEvent) => {
            // Use ref instead of state to avoid closure issues
            if (!resizingRef.current) return;

            const deltaX = e.clientX - resizeStartXRef.current;
            const newWidth = Math.max(
                column.minWidth,
                Math.min(column.maxWidth, resizeStartWidthRef.current + deltaX)
            );

            onColumnResize(columnId, newWidth);
        };

        const handleMouseUp = () => {
            // Set flag to prevent immediate sorting after resize
            if (resizingRef.current) {
                justFinishedResizingRef.current = true;
                // Clear the flag after a short delay
                setTimeout(() => {
                    justFinishedResizingRef.current = false;
                }, 50);
            }
            
            setResizing(null);
            resizingRef.current = null;
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            
            // Add visual feedback that resize is complete
            if (headerRef.current) {
                headerRef.current.style.userSelect = '';
            }
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };

        // Prevent text selection during resize
        if (headerRef.current) {
            headerRef.current.style.userSelect = 'none';
        }
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'col-resize';

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }, [columns, onColumnResize, isResizeDisabled]); // NEW: Add isResizeDisabled to dependencies

    const getColumnLabel = (column: ColumnConfig): string => {
        // For criteria columns, show the criteria name with a tooltip indicator
        if (isCriteriaColumn(column)) {
            const criteriaColumn = column as CriteriaColumnConfig;
            // Truncate long criteria names for header display
            const maxLength = Math.floor(criteriaColumn.width / 8); // Approximate character width
            const truncated = criteriaColumn.criteriaName.length > maxLength
                ? criteriaColumn.criteriaName.substring(0, maxLength - 3) + '...'
                : criteriaColumn.criteriaName;
            return truncated;
        }

        // For standard columns, use translations
        const standardColumn = column as StandardColumnConfig;
        switch (standardColumn.type) {
            case 'source':
                return ''; // No label for source icon
            case 'name':
                return t('tenders.list.order');
            case 'organization':
                return t('tenders.details.client');
            case 'publication_date':
                return t('tenders.details.publicationDate');
            case 'deadline_progress':
                return ''; // Progress bar has no text label
            case 'submission_deadline':
                return t('tenders.details.submissionDeadline');
            case 'board_status':
                return t('tenders.list.boardStatus');
            case 'score':
                return t('tenders.list.relevance');
            case 'actions':
                return ''; // Actions column has no label
            default:
                return standardColumn.label || '';
        }
    };

    return (
        <TableHeader className="bg-card border-b sticky top-0">
            <TableRow ref={headerRef}>
                {columns.map((column, index) => {
                    const isLastColumn = index === columns.length - 1;

                    // Determine if this column is sorted using the same identifier logic as handleSort
                    const sortIdentifier = isCriteriaColumn(column) 
                        ? (column as CriteriaColumnConfig).criteriaName 
                        : column.id;
                    const isSorted = sortConfig?.columnId === sortIdentifier;

                    return (
                        <TableHead
                            key={column.id}
                            className={cn(
                                "text-xs font-medium relative select-none group bg-card",
                                column.sortable && "cursor-pointer hover:bg-muted/50 transition-colors",
                                isSorted && "bg-muted",
                                resizing === column.id && "bg-muted",
                                isResizeDisabled && "resize-disabled" // NEW: Add class when resize is disabled
                            )}
                            style={{
                                width: `${column.width}px`,
                                minWidth: `${column.minWidth}px`,
                                maxWidth: `${column.maxWidth}px`
                            }}
                            onClick={(e) => {
                                // Don't sort if clicking on the resize handle area (and resizing is not disabled)
                                if (!isResizeDisabled) {
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    const clickX = e.clientX - rect.left;
                                    const cellWidth = rect.width;
                                    
                                    // If clicking in the rightmost 6px of the cell (resize handle area), don't sort
                                    if (clickX > cellWidth - 6 && column.resizable && !isLastColumn) {
                                        return;
                                    }
                                }
                                
                                handleSort(column);
                            }}
                        >
                            {/* Column content */}
                            <div className="flex items-center justify-between pr-2">
                                <div className="flex items-center gap-1 min-w-0">
                                    {isCriteriaColumn(column) ? (
                                        <TooltipProvider>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <span className="truncate cursor-help">
                                                        {getColumnLabel(column)}
                                                    </span>
                                                </TooltipTrigger>
                                                <TooltipContent side="bottom" className="max-w-[300px] border-border bg-card">
                                                    <p className="text-xs font-medium text-foreground">{(column as CriteriaColumnConfig).criteriaName}</p>
                                                    <p className="text-xs text-muted-foreground mt-1">{t('columns.clickToSort')}</p>
                                                    {isResizeDisabled && (
                                                        <p className="text-xs text-amber-600 mt-1">Resize disabled in compact view</p>
                                                    )}
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    ) : (
                                        <span className="truncate">
                                            {getColumnLabel(column)}
                                        </span>
                                    )}
                                    {isCriteriaColumn(column) && (
                                        <span className="text-[10px] opacity-60 whitespace-nowrap text-muted-foreground">
                                            ✓
                                        </span>
                                    )}
                                </div>

                                {column.sortable && (
                                    <div className="flex-shrink-0">
                                        {getSortIcon(column)}
                                    </div>
                                )}
                            </div>

                            {/* Resize handle - Modified to show disabled state */}
                            {column.resizable && !isLastColumn && (
                                <div
                                    className={cn(
                                        "absolute top-0 right-0 w-1.5 h-full z-10",
                                        isResizeDisabled 
                                            ? "cursor-not-allowed opacity-30" // NEW: Disabled state
                                            : "cursor-col-resize opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-border active:bg-muted",
                                        resizing === column.id && !isResizeDisabled && "opacity-100 bg-muted"
                                    )}
                                    onMouseDown={(e) => handleResizeStart(e, column.id)}
                                    title={
                                        isResizeDisabled 
                                            ? "Resizing disabled in compact view" 
                                            : "Drag to resize column"
                                    }
                                >
                                    {/* Subtle resize indicator */}
                                    <div className={cn(
                                        "absolute top-1/2 left-1/2 w-0.5 h-4 bg-muted-foreground transform -translate-x-1/2 -translate-y-1/2 transition-opacity",
                                        isResizeDisabled 
                                            ? "opacity-30" 
                                            : "opacity-60 group-hover:opacity-100"
                                    )} />
                                </div>
                            )}
                        </TableHead>
                    );
                })}

                {/* Column manager button */}
                <TableHead className="w-1 text-center bg-card">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onOpenTableLayout}
                        className="h-6 w-6 -ml-4 p-0 opacity-60 hover:opacity-100 cursor-pointer hover:bg-none transition-all"
                        title={t('columns.manageColumns')}
                    >
                        <Settings className="h-3 w-3" />
                    </Button>
                </TableHead>
            </TableRow>
        </TableHeader>
    );
};
import React, { useState, useRef, useCallback } from 'react';
import { TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    GripVertical,
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
}

export const ResizableTableHeader: React.FC<ResizableTableHeaderProps> = ({
    columns,
    sortConfig,
    onSort,
    onColumnResize,
    onOpenTableLayout,
}) => {
    const t = useTendersTranslations();
    const [resizing, setResizing] = useState<string | null>(null);
    const [resizeStartX, setResizeStartX] = useState(0);
    const [resizeStartWidth, setResizeStartWidth] = useState(0);
    const headerRef = useRef<HTMLTableRowElement>(null);

    const handleSort = (column: ColumnConfig) => {
        if (!column.sortable) return;

        let newDirection: SortDirection = 'asc';

        // Create a column identifier for sorting
        let columnIdentifier = column.id;
        if (isCriteriaColumn(column)) {
            // For criteria columns, use the criteria name for sorting
            columnIdentifier = (column as CriteriaColumnConfig).criteriaName;
        }

        if (sortConfig?.columnId === columnIdentifier) {
            if (sortConfig.direction === 'asc') {
                newDirection = 'desc';
            } else if (sortConfig.direction === 'desc') {
                newDirection = null;
            }
        } else {
            // Set default direction based on column type
            if (column.type === 'score' || column.type === 'criteria') {
                newDirection = 'desc'; // Scores and criteria default to descending (best first)
            } else if (column.id === 'updated_at' || column.id === 'created_at') {
                newDirection = 'desc'; // Dates default to descending (newest first)
            }
        }

        onSort(column.id, newDirection);
    };


    const getSortIcon = (column: ColumnConfig) => {
        if (!column.sortable) return null;

        // Check if this column is currently being sorted
        let columnIdentifier = column.id;
        if (isCriteriaColumn(column)) {
            columnIdentifier = (column as CriteriaColumnConfig).criteriaName;
        }

        const isActive = sortConfig?.columnId === columnIdentifier;

        if (!isActive) {
            return <ArrowUpDown className="h-3 w-3 opacity-50" />;
        }

        if (sortConfig?.direction === 'asc') {
            return <ArrowUp className="h-3 w-3" />;
        } else if (sortConfig?.direction === 'desc') {
            return <ArrowDown className="h-3 w-3" />;
        }

        return <ArrowUpDown className="h-3 w-3 opacity-50" />;
    };

    const handleResizeStart = useCallback((e: React.MouseEvent, columnId: string) => {
        e.preventDefault();
        e.stopPropagation();

        const column = columns.find(col => col.id === columnId);
        if (!column || !column.resizable) return;

        setResizing(columnId);
        setResizeStartX(e.clientX);
        setResizeStartWidth(column.width);

        const handleMouseMove = (e: MouseEvent) => {
            if (!resizing) return;

            const deltaX = e.clientX - resizeStartX;
            const newWidth = Math.max(
                column.minWidth,
                Math.min(column.maxWidth, resizeStartWidth + deltaX)
            );

            onColumnResize(columnId, newWidth);
        };

        const handleMouseUp = () => {
            setResizing(null);
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }, [columns, resizing, resizeStartX, resizeStartWidth, onColumnResize]);

    const getColumnLabel = (column: ColumnConfig): string => {
        // For criteria columns, show the criteria name with a tooltip indicator
        if (isCriteriaColumn(column)) {
            const criteriaColumn = column as CriteriaColumnConfig;
            // Truncate long criteria names for header display
            const maxLength = Math.floor(criteriaColumn.width / 1); // Approximate character width
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
        <TableHeader className="bg-white/20 shadow sticky top-0 z-10">
            <TableRow ref={headerRef}>
                {columns.map((column, index) => {
                    const isLastColumn = index === columns.length - 1;

                    // Determine if this column is sorted (handling criteria columns)
                    let columnIdentifier = column.id;
                    if (isCriteriaColumn(column)) {
                        columnIdentifier = (column as CriteriaColumnConfig).criteriaName;
                    }
                    const isSorted = sortConfig?.columnId === columnIdentifier;

                    return (
                        <TableHead
                            key={column.id}
                            className={cn(
                                "text-xs font-medium relative select-none group",
                                column.sortable && "cursor-pointer hover:bg-muted/50",
                                isSorted && "bg-primary/5"
                            )}
                            style={{
                                width: `${column.width}px`,
                                minWidth: `${column.minWidth}px`,
                                maxWidth: `${column.maxWidth}px`
                            }}
                            onClick={() => handleSort(column)}
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
                                                <TooltipContent side="bottom" className="max-w-[300px]">
                                                    <p className="text-xs font-medium">{(column as CriteriaColumnConfig).criteriaName}</p>
                                                    <p className="text-xs text-muted-foreground mt-1">{t('columns.clickToSort')}</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    ) : (
                                        <span className="truncate">
                                            {getColumnLabel(column)}
                                        </span>
                                    )}
                                    {isCriteriaColumn(column) && (
                                        <span className="text-[10px] opacity-50 whitespace-nowrap">
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

                            {/* Resize handle */}
                            {column.resizable && !isLastColumn && (
                                <div
                                    className={cn(
                                        "absolute top-0 right-0 w-1 h-full cursor-col-resize",
                                        "opacity-0 group-hover:opacity-100 transition-opacity",
                                        "hover:bg-primary/20 active:bg-primary/40",
                                        resizing === column.id && "opacity-100 bg-primary/40"
                                    )}
                                    onMouseDown={(e) => handleResizeStart(e, column.id)}
                                >
                                    <div className="absolute top-1/2 right-0 transform -translate-y-1/2 -translate-x-1/2">
                                        <GripVertical className="h-3 w-3 rotate-90" />
                                    </div>
                                </div>
                            )}
                        </TableHead>
                    );
                })}

                {/* Column manager button */}
                <TableHead className="w-10 text-center">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onOpenTableLayout}
                        className="h-6 w-6 p-0 opacity-50 hover:opacity-100"
                        title={t('columns.manageColumns')}
                    >
                        <Settings className="h-3 w-3" />
                    </Button>
                </TableHead>
            </TableRow>
        </TableHeader>
    );
};
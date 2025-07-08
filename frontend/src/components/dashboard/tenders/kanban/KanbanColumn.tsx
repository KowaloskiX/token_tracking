import React, { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { MoreHorizontal, Trash, Pencil, CirclePlus, ArrowUpDown, GripVertical } from "lucide-react";
import { KanbanColumn as IKanbanColumn, KanbanTenderItem, COLUMN_COLORS, DEFAULT_COLUMN_COLOR } from "@/types/kanban";
import { KanbanItem } from "./KanbanItem";
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { useKanban } from "@/context/KanbanContext";
import { Input } from "@/components/ui/input";
import { 
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { useRouter } from "next/navigation";
import { TenderAnalysisResult } from "@/types/tenders";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface KanbanColumnProps {
  boardId: string;
  column: IKanbanColumn;
  onTenderOrderUpdated?: (updatedItems: KanbanTenderItem[]) => Promise<void>;
  onTenderDragStart?: (tenderId: string) => void;
  activeTenders: TenderAnalysisResult[];
  onTenderSelect?: (tenderResultId: string) => void;
  drawerRef?: React.RefObject<{ setVisibility: (value: boolean) => void }>;
  onDropFromDifferentColumn?: (e: React.DragEvent<HTMLDivElement>, targetColumnId: string) => void;
}

type SortType = 'submission_deadline' | 'publication_date' | null;

const MIN_COLUMN_WIDTH = 320; // Minimum width in pixels (equivalent to w-80)

// Helper functions for localStorage
const getColumnWidthKey = (boardId: string, columnId: string) => 
  `kanban_column_width_${boardId}_${columnId}`;

const saveColumnWidth = (boardId: string, columnId: string, width: number) => {
  try {
    if (width === MIN_COLUMN_WIDTH) {
      // Remove from localStorage if it's the default width
      localStorage.removeItem(getColumnWidthKey(boardId, columnId));
    } else {
      // Only save if it's different from default
      localStorage.setItem(getColumnWidthKey(boardId, columnId), width.toString());
    }
  } catch (error) {
    console.error('Failed to save column width:', error);
  }
};

const loadColumnWidth = (boardId: string, columnId: string): number => {
  try {
    const saved = localStorage.getItem(getColumnWidthKey(boardId, columnId));
    // Return saved width if exists, otherwise return default
    return saved ? Math.max(MIN_COLUMN_WIDTH, parseInt(saved)) : MIN_COLUMN_WIDTH;
  } catch (error) {
    console.error('Failed to load column width:', error);
    return MIN_COLUMN_WIDTH;
  }
};

export function KanbanColumn({ 
  boardId, 
  column, 
  onTenderOrderUpdated, 
  onTenderDragStart,
  activeTenders,
  onTenderSelect,
  drawerRef,
  onDropFromDifferentColumn
}: KanbanColumnProps) {
  const router = useRouter();
  const { deleteColumnAction, updateColumnAction, deleteTenderItemAction } = useKanban();
  const [editMode, setEditMode] = useState(false);
  const [columnName, setColumnName] = useState(column.name);
  const [tenderItems, setTenderItems] = useState<KanbanTenderItem[]>(column.tenderItems || []);
  const [draggedTenderId, setDraggedTenderId] = useState<string | null>(null);
  const [isUpdatingName, setIsUpdatingName] = useState(false);
  const [sortType, setSortType] = useState<SortType>(null);
  
  // Resize functionality with localStorage persistence
  const [columnWidth, setColumnWidth] = useState(() => loadColumnWidth(boardId, column.id));
  const [isResizing, setIsResizing] = useState(false);
  const columnRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);
  
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  useEffect(() => {
    if (!isUpdatingName) {
      setColumnName(column.name);
    }
  }, [column.name, isUpdatingName]);

  useEffect(() => {
    setTenderItems(column.tenderItems || []);
  }, [column.tenderItems]);

  // Load saved width when column changes
  useEffect(() => {
    setColumnWidth(loadColumnWidth(boardId, column.id));
  }, [boardId, column.id]);

  // Mouse resize handlers
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !columnRef.current) return;
      
      e.preventDefault();
      const rect = columnRef.current.getBoundingClientRect();
      const newWidth = Math.max(MIN_COLUMN_WIDTH, e.clientX - rect.left);
      setColumnWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      
      // Save the final width to localStorage
      saveColumnWidth(boardId, column.id, columnWidth);
    };

    if (isResizing) {
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, boardId, column.id, columnWidth]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
  };

  // Function to get tender data by ID
  const getTenderData = useCallback((tenderResultId: string): TenderAnalysisResult | undefined => {
    return activeTenders.find(tender => tender._id === tenderResultId);
  }, [activeTenders]);

  // Function to sort tender items
  const getSortedTenderItems = useCallback(() => {
    // ✅ FIXED: Just return current state since sorting updates it directly
    return tenderItems;
  }, [tenderItems]);

  // ✅ SIMPLE: Handle sort with seamless database save (like drag and drop)
  const handleSort = async (type: 'submission_deadline' | 'publication_date') => {
    setSortType(type);
    console.log(`Sorting column "${column.name}" by ${type}`);
    
    // Get the sorted items immediately
    const sortedItems = [...tenderItems].sort((a, b) => {
      const tenderA = getTenderData(a.tender_analysis_result_id);
      const tenderB = getTenderData(b.tender_analysis_result_id);

      if (!tenderA || !tenderB) return 0;

      let dateA: Date, dateB: Date;

      if (type === 'submission_deadline') {
        // Handle potentially undefined submission_deadline
        const deadlineA = tenderA.tender_metadata.submission_deadline;
        const deadlineB = tenderB.tender_metadata.submission_deadline;
        
        // If either deadline is undefined, put those items at the end
        if (!deadlineA && !deadlineB) return 0;
        if (!deadlineA) return 1;
        if (!deadlineB) return -1;
        
        dateA = new Date(deadlineA);
        dateB = new Date(deadlineB);
      } else { // publication_date
        dateA = new Date(tenderA.created_at);
        dateB = new Date(tenderB.created_at);
      }

      return dateA.getTime() - dateB.getTime();
    });

    // Update order numbers for the sorted items
    const reorderedItems = sortedItems.map((item, idx) => ({
      ...item,
      order: idx + 1,
    }));

    // ✅ Update local state immediately (no flash)
    setTenderItems(reorderedItems);

    // ✅ Save to database in background (seamless like drag and drop)
    if (onTenderOrderUpdated) {
      try {
        await onTenderOrderUpdated(reorderedItems);
      } catch (error) {
        console.error("Failed to save sort order:", error);
        // Revert on error
        setTenderItems(column.tenderItems || []);
      }
    }
  };

  const handleUpdateColumn = async (updates: Partial<IKanbanColumn>) => {
    setIsUpdatingName(true);
    
    try {
      if (updates.name) {
        setColumnName(updates.name);
      }
      setEditMode(false);
      
      await updateColumnAction(boardId, column.id, { ...column, ...updates });
    } catch (err) {
      console.error("Failed to update column:", err);
      setColumnName(column.name);
    } finally {
      setIsUpdatingName(false);
    }
  };

  const handleTenderDragStart = useCallback(
    (e: React.DragEvent<HTMLDivElement>, id: string) => {
      onTenderDragStart?.(id);
      setDraggedTenderId(id);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", `tender-${id}`);
      e.stopPropagation();
    },
    [onTenderDragStart]
  );

  const handleTenderDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const handleTenderDrop = useCallback(
    async (e: React.DragEvent<HTMLDivElement>, dropTargetId: string) => {
      e.preventDefault();
      e.stopPropagation();
      
      const draggedData = e.dataTransfer.getData("text/plain");
      
      if (draggedData.startsWith("tender-") && !tenderItems.some(item => item.id === draggedTenderId)) {
        if (onDropFromDifferentColumn) {
          onDropFromDifferentColumn(e, column.id);
          return;
        }
      }
      
      if (draggedTenderId && draggedTenderId !== dropTargetId) {
        const draggedIndex = tenderItems.findIndex(item => item.id === draggedTenderId);
        const dropIndex = tenderItems.findIndex(item => item.id === dropTargetId);
        
        if (draggedIndex === -1 || dropIndex === -1) return;
    
        const newTenderItems = [...tenderItems];
        const [draggedItem] = newTenderItems.splice(draggedIndex, 1);
        newTenderItems.splice(dropIndex, 0, draggedItem);
    
        const reordered = newTenderItems.map((item, idx) => ({
          ...item,
          order: idx + 1,
        }));
    
        setTenderItems(reordered);
        setDraggedTenderId(null);
    
        if (onTenderOrderUpdated) {
          onTenderOrderUpdated(reordered).catch(error => {
            console.error("Failed to update tender order:", error);
            setTenderItems(column.tenderItems || []);
          });
        }
      }
    },
    [tenderItems, draggedTenderId, column.tenderItems, onTenderOrderUpdated, onDropFromDifferentColumn, column.id]
  );

  const handleDeleteTenderItem = async (itemId: string) => {
    const updatedItems = tenderItems.filter(item => item.id !== itemId);
    setTenderItems(updatedItems);
    
    try {
      await deleteTenderItemAction(boardId, column.id, itemId);
      if (onTenderOrderUpdated) {
        await onTenderOrderUpdated(updatedItems);
      }
    } catch (error) {
      console.error("Failed to delete tender item:", error);
      setTenderItems(column.tenderItems || []);
    }
  };

  const sortedTenderItems = getSortedTenderItems();

  return (
    <div 
      ref={columnRef}
      className="p-4 bg-secondary rounded-md space-y-3 shadow-sm flex flex-col border border-secondary-border relative"
      style={{
        width: `${columnWidth}px`,
        backgroundColor: column.color ? `${column.color}20` : undefined,
        '--column-color-hover-bg': column.color ? `${column.color}40` : 'hsl(var(--accent)) / 0.4'
      } as React.CSSProperties}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
      }}
      onDrop={(e) => {
        const draggedData = e.dataTransfer.getData("text/plain");
        if (draggedData.startsWith("tender-") && onDropFromDifferentColumn) {
          onDropFromDifferentColumn(e, column.id);
        }
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-1">
          <Popover>
            <PopoverTrigger>
              <div 
                className="w-4 h-4 rounded-full cursor-pointer border"
                style={{ backgroundColor: column.color || DEFAULT_COLUMN_COLOR }}
              />
            </PopoverTrigger>
            <PopoverContent className="w-auto p-2 grid grid-cols-4 gap-2">
              {COLUMN_COLORS.map((color) => (
                <button
                  key={color}
                  className="w-6 h-6 rounded-full border cursor-pointer"
                  style={{ backgroundColor: color }}
                  onClick={() => handleUpdateColumn({ color })}
                />
              ))}
            </PopoverContent>
          </Popover>
          {editMode ? (
            <Input
              value={columnName}
              onChange={(e) => setColumnName(e.target.value)}
              onBlur={() => handleUpdateColumn({ name: columnName })}
              onKeyDown={(e) => e.key === 'Enter' && handleUpdateColumn({ name: columnName })}
              className="h-7 px-2 py-1 text-sm font-semibold"
              autoFocus
            />
          ) : (
            <h2 
              className="text-sm font-semibold cursor-pointer hover:text-primary transition-colors"
              onClick={() => setEditMode(true)}
            >
              {columnName}
            </h2>
          )}
        </div>
        <div className="flex items-center gap-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-7 w-7 focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
              >
                <ArrowUpDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => handleSort('submission_deadline')}>
                {tCommon('deadline')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleSort('publication_date')}>
                {tCommon('published')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-7 w-7 focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => setEditMode(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                {tCommon('rename')}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  const confirmDelete = window.confirm(
                    "Are you sure you want to delete this column and all its items?"
                  );
                  if (confirmDelete) {
                    deleteColumnAction(boardId, column.id);
                  }
                }}
                className="text-destructive"
              >
                <Trash className="mr-2 h-4 w-4" />
                {tCommon('delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div 
        className="space-y-2 flex-1 overflow-y-auto min-h-[100px]"
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }}
      >
        {sortedTenderItems.length === 0 && (
          <div 
            className="flex items-center justify-center h-20 text-xs text-muted-foreground italic"
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
            }}
            onDrop={(e) => {
              const draggedData = e.dataTransfer.getData("text/plain");
              if (draggedData.startsWith("tender-") && onDropFromDifferentColumn) {
                onDropFromDifferentColumn(e, column.id);
              }
            }}
          >
            {t('tenders.board.noItems')}
          </div>
        )}
        
        {sortedTenderItems.map((item, index) => (
          <div
            key={item.id}
            onDragOver={handleTenderDragOver}
            onDrop={(e) => handleTenderDrop(e, item.id)}
          >
            <KanbanItem 
              item={item} 
              itemPosition={index + 1}
              onDelete={() => handleDeleteTenderItem(item.id)}
              backgroundColor={column.color || COLUMN_COLORS[0]}
              onDragStart={handleTenderDragStart}
              activeTenders={activeTenders}
              onTenderSelect={onTenderSelect}
            />
          </div>
        ))}
      </div>

      <Button 
        variant="ghost" 
        size="sm" 
        className="w-full justify-start mt-auto px-4 rounded-md transition-all duration-200 hover:bg-[var(--column-color-hover-bg)] hover:text-foreground text-muted-foreground group"
        onClick={() => router.push('/dashboard/tenders')}
      >
        <CirclePlus className="mr-2 h-5 w-5 stroke-[1.5] transition-colors group-hover:stroke-foreground" />
        <span className="font-medium transition-colors">{t('tenders.board.addTender')}</span>
      </Button>

      {/* Resize handle */}
      <div
        ref={resizeRef}
        className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 transition-colors group"
        onMouseDown={handleResizeStart}
      >
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-8 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-primary/10 rounded-l-md">
          <GripVertical className="h-4 w-4 text-primary/40" />
        </div>
      </div>
    </div>
  );
}
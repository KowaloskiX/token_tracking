// In KanbanLayout.tsx
import React, { useRef, useState, useEffect } from "react";
import { KanbanBoard } from "@/types/kanban";
import { KanbanColumn } from "./KanbanColumn";
import { NewColumnDialog } from "./NewColumnDialog";
import { Button } from "@/components/ui/button";
import { CirclePlus } from "lucide-react";
import { useTender } from "@/context/TenderContext";
import { toast } from "@/hooks/use-toast";
import { TenderAnalysisResult } from "@/types/tenders";
import { useKanban } from "@/context/KanbanContext";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

interface KanbanLayoutProps {
  board: KanbanBoard;
  onBoardUpdated: () => Promise<void>;
  onTenderSelect?: (tenderResultId: string) => void;
  drawerRef?: React.RefObject<{ setVisibility: (value: boolean) => void }>;
}

async function saveColumnsOrderToDB(
  board: KanbanBoard,
  boardId: string,
  updatedColumns: any[]
) {
  try {
    const token = localStorage.getItem("token");
    const payload = {
      user_id: board.user_id,
      name: board.name,
      columns: updatedColumns.map((col) => ({
        _id: col.id,
        name: col.name,
        order: col.order,
        color: col.color,
        tender_items: col.tenderItems.map((tender: any) => ({
          _id: tender.id,
          tender_analysis_result_id: tender.tender_analysis_result_id,
          order: tender.order,
          board_id: tender.board_id || boardId,
          column_id: tender.column_id || col.id,
        })),
      })),
    };

    const response = await fetch(`${serverUrl}/boards/${boardId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Failed to update board columns: ${response.statusText}`);
    }
    
    return true;
  } catch (err) {
    console.error("Column order save error:", err);
    return false;
  }
}

async function fetchTendersForBoard(board: KanbanBoard): Promise<TenderAnalysisResult[]> {
  const tenderAnalysisIds = new Set<string>();
  
  board.columns.forEach(column => {
    column.tenderItems?.forEach(item => {
      if (item.tender_analysis_result_id) {
        tenderAnalysisIds.add(item.tender_analysis_result_id);
      }
    });
  });
  
  if (tenderAnalysisIds.size === 0) {
    return [];
  }
  
  const ids = Array.from(tenderAnalysisIds);
  
  try {
    const token = localStorage.getItem("token");
    const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;
    
    const response = await fetch(`${serverUrl}/tender-results/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify(ids)
    });
    
    if (!response.ok) {
      console.error('Failed to fetch tender results in batch:', response.statusText);
      return [];
    }
    
    return await response.json();
  } catch (error) {
    console.error("Error fetching tenders for board:", error);
    return [];
  }
}

export function KanbanLayout({ 
  board, 
  onBoardUpdated, 
  onTenderSelect, 
  drawerRef 
}: KanbanLayoutProps) {
  const [draggedTenderId, setDraggedTenderId] = useState<string | null>(null);
  const [draggedFromColumnId, setDraggedFromColumnId] = useState<string | null>(null);
  const { fetchAllActiveTenders, activeTenders } = useTender();
  const { moveTenderItemAction, selectedBoard } = useKanban();
  const [boardTenders, setBoardTenders] = useState<TenderAnalysisResult[]>([]);

  const [columns, setColumns] = useState(board.columns);
  const [draggedColumnId, setDraggedColumnId] = useState<string | null>(null);
  const [showNewColumnDialog, setShowNewColumnDialog] = useState(false);
  const [isDraggingTender, setIsDraggingTender] = useState(false);
  const [pendingServerOperations, setPendingServerOperations] = useState(0);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  const columnsCount = columns.length;
  const isEmpty = columnsCount === 0;
  
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  // This effect synchronizes the columns state with the latest data from context or props
  useEffect(() => {
    if (pendingServerOperations === 0) {
      if (selectedBoard && selectedBoard.id === board.id) {
        const sorted = [...(selectedBoard.columns || [])].sort(
          (a, b) => (a.order ?? 0) - (b.order ?? 0)
        );
        setColumns(sorted);
      } else {
        const sorted = [...(board.columns || [])].sort(
          (a, b) => (a.order ?? 0) - (b.order ?? 0)
        );
        setColumns(sorted);
      }
    }
  }, [board.columns, selectedBoard, pendingServerOperations, board.id]);

  useEffect(() => {
    fetchAllActiveTenders();
  }, [fetchAllActiveTenders]);

  useEffect(() => {
    const checkOverflow = () => {
      if (scrollContainerRef.current) {
        const isActuallyOverflowing = 
          scrollContainerRef.current.scrollWidth > scrollContainerRef.current.clientWidth;
        
        setIsOverflowing(isActuallyOverflowing);
      }
    };
    
    checkOverflow();
    window.addEventListener('resize', checkOverflow);
    
    if (columns) {
      checkOverflow();
    }
    
    return () => {
      window.removeEventListener('resize', checkOverflow);
    };
  }, [columns]);

  useEffect(() => {
    const loadBoardTenders = async () => {
      const tenders = await fetchTendersForBoard(board);
      setBoardTenders(tenders);
    };
    
    loadBoardTenders();
  }, [board]);
  
  const allTenders = [...boardTenders];
  activeTenders.forEach(tender => {
    if (!boardTenders.some(bt => bt._id === tender._id)) {
      allTenders.push(tender);
    }
  });

  const handleDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    columnId: string
  ) => {
    if (!isDraggingTender) {
      setDraggedColumnId(columnId);
      e.dataTransfer.effectAllowed = "move";
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleColumnDrop = async (
    e: React.DragEvent<HTMLDivElement>,
    dropTargetId: string
  ) => {
    e.preventDefault();
    if (draggedColumnId && draggedColumnId !== dropTargetId && !isDraggingTender) {
      const draggedIndex = columns.findIndex((c) => c.id === draggedColumnId);
      const dropIndex = columns.findIndex((c) => c.id === dropTargetId);
      if (draggedIndex === -1 || dropIndex === -1) return;

      const newColumns = [...columns];
      const [draggedColumn] = newColumns.splice(draggedIndex, 1);
      newColumns.splice(dropIndex, 0, draggedColumn);

      const reordered = newColumns.map((col, idx) => ({
        ...col,
        order: idx + 1,
      }));

      setColumns(reordered);
      setDraggedColumnId(null);

      setPendingServerOperations(prev => prev + 1);

      try {
        const success = await saveColumnsOrderToDB(board, board.id, reordered);
        if (!success) {
          toast({
            title: t('tenders.board.columnOrderSaveFailed'),
            description: t('tenders.board.changesRevertedOnRefresh'),
            variant: "destructive",
          });
        }
        
        onBoardUpdated().catch(console.error);
      } catch (err) {
        console.error("Drag-drop error:", err);
        toast({
          title: t('tenders.board.columnOrderSaveFailed'),
          description: t('tenders.board.changesRevertedOnRefresh'),
          variant: "destructive",
        });
      } finally {
        setPendingServerOperations(prev => prev - 1);
      }
    }
  };

  const handleTenderDrop = async (
    e: React.DragEvent<HTMLDivElement>,
    targetColumnId: string
  ) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (isDraggingTender && draggedTenderId && draggedFromColumnId && draggedFromColumnId !== targetColumnId) {
      setDraggedTenderId(null);
      setDraggedFromColumnId(null);
      setIsDraggingTender(false);
      
      try {
        await moveTenderItemAction(
          board.id,
          draggedTenderId,
          draggedFromColumnId,
          targetColumnId
        );
      } catch (error) {
        console.error("Move failed:", error);
        toast({
          title: t('tenders.board.moveItemFailed'),
          description: t('tenders.board.changeReverted'),
          variant: "destructive",
        });
      }
    }
  };

  const handleTenderItemClick = (tenderResultId: string) => {
    if (onTenderSelect) {
      onTenderSelect(tenderResultId);
    }
  };

  const renderColumns = () => (
    <div className="relative flex">
      <div
        ref={scrollContainerRef}
        className="overflow-x-auto pb-4 flex-1 scrollbar-hide"
      >
        <div
          className={`flex gap-4 ${
            isEmpty ? "justify-center min-h-[300px] items-center" : ""
          }`}
          style={{
            width: isEmpty ? "100%" : "auto",
            paddingRight: isEmpty ? "0" : "72px",
          }}
        >
          {columns.map((column) => (
            <div
              key={column.id}
              draggable={!isDraggingTender}
              onDragStart={(e) => handleDragStart(e, column.id)}
              onDragOver={handleDragOver}
              onDrop={(e) => {
                if (isDraggingTender) {
                  handleTenderDrop(e, column.id);
                } else if (draggedColumnId) {
                  handleColumnDrop(e, column.id);
                }
              }}
            >
              <KanbanColumn
                boardId={board.id}
                column={column}
                onTenderDragStart={(tenderId) => {
                  setDraggedTenderId(tenderId);
                  setDraggedFromColumnId(column.id);
                  setIsDraggingTender(true);
                }}
                onTenderOrderUpdated={async (localUpdatedItems: any[]) => {
                  const updatedColumns = columns.map(col => {
                    if (col.id === column.id) {
                      return {
                        ...col,
                        tenderItems: localUpdatedItems
                      };
                    }
                    return col;
                  });
                  
                  setColumns(updatedColumns);
                  setPendingServerOperations(prev => prev + 1);
                  
                  try {
                    await saveTendersOrderToDB(board.id, column, localUpdatedItems);
                    onBoardUpdated().catch(console.error);
                  } catch (err) {
                    console.error("Failed to update tender order:", err);
                    toast({
                      title: t('tenders.board.saveOrderFailed'),
                      description: t('tenders.board.changesRevertedOnRefresh'),
                      variant: "destructive",
                    });
                  } finally {
                    setPendingServerOperations(prev => prev - 1);
                  }
                }}
                activeTenders={allTenders}
                onTenderSelect={handleTenderItemClick}
                drawerRef={drawerRef}
                onDropFromDifferentColumn={handleTenderDrop}
              />
            </div>
          ))}
        </div>
      </div>

      {!isEmpty && (
        <div 
          className="sticky right-0 pr-4 pl-0 h-56"
          style={{ width: "288px" }}
        >
          <div className="w-72 h-full flex flex-col justify-center items-center p-4 bg-background/50 backdrop-blur-sm rounded-md border-2 border-dashed border-stone-300 hover:border-primary/40 transition-all duration-200 shadow-sm hover:shadow cursor-pointer group"
            onClick={() => setShowNewColumnDialog(true)}
          >
            <CirclePlus className="h-8 w-8 mb-2 text-muted-foreground/70 group-hover:text-primary/70 transition-colors" />
            <span className="text-sm font-medium text-muted-foreground/80 group-hover:text-foreground transition-colors">{t('tenders.board.addColumn')}</span>
          </div>
        </div>
      )}

      {isOverflowing && !isEmpty && (
        <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-background to-transparent z-10 pointer-events-none" />
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-4 relative">
      {isEmpty ? (
        <div className="flex flex-col items-center justify-center min-h-[300px]">
          <Button
            variant="outline"
            className="px-24 py-16 border-2 border-dashed border-secondary-border bg-background/50 backdrop-blur-sm hover:bg-secondary/40 hover:border-primary flex flex-col justify-center items-center gap-2 shadow-sm transition-all duration-200"
            onClick={() => setShowNewColumnDialog(true)}
          >
            <CirclePlus className="h-6 w-6" />
            <span className="text-sm">{t('tenders.board.addColumn')}</span>
          </Button>
        </div>
      ) : (
        renderColumns()
      )}

      <NewColumnDialog
        boardId={board.id}
        open={showNewColumnDialog}
        onOpenChange={setShowNewColumnDialog}
      />

      {pendingServerOperations > 0 && (
        <div className="fixed bottom-4 left-4 bg-background shadow-md rounded-full py-1 px-3 text-xs flex items-center gap-2 border z-50">
          <div className="animate-spin h-3 w-3 border border-primary border-t-transparent rounded-full"></div>
          <span>{t('tenders.board.synchronizingChanges')}</span>
        </div>
      )}
    </div>
  );
}

// Helper function to handle tender order updates
async function saveTendersOrderToDB(
  boardId: string,
  column: any,
  updatedTenders: any[]
) {
  try {
    const token = localStorage.getItem("token");
    const columnId = column._id || column.id;
    const payload = {
      name: column.name,
      order: column.order,
      tender_items: updatedTenders.map((tender, index) => ({
        _id: tender.id,
        tender_analysis_result_id: tender.tender_analysis_result_id,
        order: index + 1,
        board_id: tender.board_id || boardId,
        column_id: tender.column_id || columnId,
      })),
    };

    const response = await fetch(
      `${serverUrl}/boards/${boardId}/columns/${columnId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        credentials: "include",
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to update tender order: ${response.statusText}`);
    }
    
    return true;
  } catch (err) {
    console.error("Failed to save tender order:", err);
    return false;
  }
}
"use client";

import { useCallback, useEffect, useState, useRef, SetStateAction } from "react";
import { useParams, useRouter } from "next/navigation";
import { useDashboard } from "@/hooks/useDashboard";
import { useKanban } from "@/context/KanbanContext";
import { KanbanLayout } from "@/components/dashboard/tenders/kanban/KanbanLayout";
import { KanbanBoardTabs } from "@/components/dashboard/tenders/kanban/KanbanBoard";
import { NewBoardDialog } from "@/components/dashboard/tenders/kanban/NewBoardDialog";
import TenderResultSidebar from "@/components/dashboard/tenders/TenderResultSidebar";
import { Button } from "@/components/ui/button";
import { Loader2, Pencil, Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { DeleteBoardDialog } from "@/components/dashboard/tenders/kanban/DeleteBoardDialog";
import { TenderAnalysisResult } from "@/types/tenders";
import { getBoards } from "@/utils/kanbanActions";
import { useTendersTranslations } from "@/hooks/useTranslations";

export default function BoardManagementPage() {
  const router = useRouter();
  const { boardId } = useParams();
  const { user } = useDashboard();
  const t = useTendersTranslations();
  const { 
    boards,
    selectedBoard,
    isLoading,
    fetchAllBoards,
    fetchBoardById,
    setSelectedBoard,
    updateBoardAction,
    clearError
  } = useKanban();
  
  // Determine ownership/admin rights
  const isOwner = selectedBoard?.user_id === user?._id;
  const isAdmin = user?.role === "admin";
  const canManage = isOwner || isAdmin;
  
  const [selectedTenderResult, setSelectedTenderResult] = useState<TenderAnalysisResult | null>(null);
  const drawerRef = useRef<{ setVisibility: (value: boolean) => void }>(null);
  const [isFetchingTender, setIsFetchingTender] = useState<boolean>(false);

  const [showNewBoardDialog, setShowNewBoardDialog] = useState(false);
  const [boardNotFound, setBoardNotFound] = useState(false);
  const [editBoardName, setEditBoardName] = useState(false);
  const [boardName, setBoardName] = useState(selectedBoard?.name || "");
  const editContainerRef = useRef<HTMLDivElement>(null);

  const refreshCurrentBoard = useCallback(async () => {
    if (!boardId) return;
    
    try {
      const board = await fetchBoardById(boardId.toString());
      setSelectedBoard(board);
      setBoardNotFound(false);
    } catch (error) {
      setBoardNotFound(true);
      setSelectedBoard(null);
    }
  }, [boardId, fetchBoardById, setSelectedBoard]);

  useEffect(() => {
    const loadBoards = async () => {
      if (user?._id) {
        await fetchAllBoards();
      }
    };
    loadBoards();
  }, [user?._id]);

  useEffect(() => {
    setBoardName(selectedBoard?.name || "");
  }, [selectedBoard]);

  useEffect(() => {
    const loadBoard = async () => {
      if (!boardId || !user?._id) return;
      
      try {
        await fetchBoardById(boardId.toString());
        setBoardNotFound(false);
      } catch (error) {
        console.error("Error loading board:", error);
        setBoardNotFound(true);
        
        if (boards && boards.length > 0) {
          router.push(`/dashboard/tenders/management/${boards[0].id}`);
        }
      } finally {
        clearError();
      }
    };
    
    loadBoard();
  }, [boardId, user?._id]);

  const handleBoardSelect = useCallback((boardId: string) => {
    if (boardId !== selectedBoard?.id) {
      router.push(`/dashboard/tenders/management/${boardId}`);
    }
  }, [router, selectedBoard?.id]);

  const handleBoardRename = async () => {
    if (!boardName.trim() || !selectedBoard) return;

    try {
      await updateBoardAction(selectedBoard.id, { name: boardName });
      setEditBoardName(false);
    } catch (err) {
      setBoardName(selectedBoard.name);
      setEditBoardName(false);
    }
  };

  const handleTenderSelect = useCallback((tenderResultId: string) => {
    if (isFetchingTender) return;
    
    const fetchTender = async () => {
      setIsFetchingTender(true);
      try {
        const token = localStorage.getItem("token");
        
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-results/batch`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify([tenderResultId])
          }
        );
        
        if (!response.ok) {
          throw new Error("Failed to load tender details");
        }
        
        const data = await response.json();
        if (data && data.length > 0) {
          setSelectedTenderResult(data[0]);
          drawerRef.current?.setVisibility(true);
        } else {
          throw new Error("No tender details found");
        }
      } catch (error) {
        console.error("Failed to load tender details:", error);
      } finally {
        setIsFetchingTender(false);
      }
    };
    
    fetchTender();
  }, [isFetchingTender]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full w-full p-8">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  
  return (
    <div className="p-4 w-full h-full flex flex-col space-y-4">
      <header className="flex items-center justify-between gap-4 flex-shrink-0">
        {selectedBoard ? (
          <>
            {editBoardName ? (
              <div ref={editContainerRef} className="flex items-center gap-2">
                <Input
                  className="border rounded px-2 py-1 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-black max-w-[240px]"
                  value={boardName}
                  onChange={(e) => setBoardName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleBoardRename();
                    if (e.key === 'Escape') {
                      setBoardName(selectedBoard.name);
                      setEditBoardName(false);
                    }
                  }}
                  autoFocus
                />
                <Button
                  size="sm"
                  className="h-7 w-7 bg-black hover:bg-black/90"
                  onClick={handleBoardRename}
                >
                  <Check className="h-4 w-4 text-white" />
                </Button>
              </div>
            ) : (
              <h1 className="text-xl font-semibold flex items-center gap-2">
                {selectedBoard.name}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 hover:bg-accent text-neutral-400 hover:text-foreground"
                  onClick={() => setEditBoardName(true)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              </h1>
            )}
            {canManage && (
              <DeleteBoardDialog
                boardId={selectedBoard.id}
                boardName={selectedBoard.name}
                onDeleted={async () => {
                  const currentBoardId = selectedBoard.id;
                  const freshBoards = await getBoards();
                
                  if (freshBoards.length > 0) {
                    const otherBoard = freshBoards.find(b => b.id !== currentBoardId);
                    if (otherBoard) {
                      router.push(`/dashboard/tenders/management/${otherBoard.id}`);
                    } else {
                      router.push(`/dashboard/tenders/management/${freshBoards[0].id}`);
                    }
                  } else {
                    router.push('/dashboard/tenders/management');
                    setTimeout(() => setShowNewBoardDialog(true), 100);
                  }
                }}
              />
            )}
          </>
        ) : (
          <h1 className="text-xl font-semibold">{t('tenders.board.management')}</h1>
        )}
      </header>

      {boards.length > 0 && (
        <div className="border-b pb-2 flex-shrink-0">
          <KanbanBoardTabs 
            boards={boards}
            currentBoardId={selectedBoard?.id}
            onBoardSelect={handleBoardSelect}
            onNewBoard={() => setShowNewBoardDialog(true)}
          />
        </div>
      )}

      {boardNotFound ? (
        <div className="p-4 text-center space-y-4">
          <h2 className="text-xl">{t('tenders.board.notFound')}</h2>
          <Button onClick={() => setShowNewBoardDialog(true)}>
            {t('tenders.board.createNewBoard')}
          </Button>
        </div>
      ) : selectedBoard ? (
        <div className="w-full relative flex-1 min-h-0">
          <div className="absolute inset-0 overflow-y-auto scrollbar-table">
            <div className="min-w-max pb-4 h-full">
              <KanbanLayout 
                board={selectedBoard} 
                onBoardUpdated={refreshCurrentBoard}
                onTenderSelect={handleTenderSelect} 
                drawerRef={drawerRef}
              />
            </div>
          </div>
          
          <div className="fixed right-0 top-0 h-screen">
            <TenderResultSidebar 
                result={selectedTenderResult}
                drawerRef={drawerRef} allResults={[]} 
                setAllResults={function (value: SetStateAction<TenderAnalysisResult[]>): void {
                  console.log("")
                }}
            />
          </div>
        </div>
      ) : (
        <div className="p-4 text-center">
          <p className="text-muted-foreground">{t('tenders.board.selectCreateBoard')}</p>
        </div>
      )}

      <NewBoardDialog 
        open={showNewBoardDialog} 
        onOpenChange={(open: boolean) => {
          setShowNewBoardDialog(open);
          clearError();
        }}
        onBoardCreated={async (newBoardId) => {
          await fetchAllBoards();
          
          router.push(`/dashboard/tenders/management/${newBoardId}`);
          
          const newBoard = await fetchBoardById(newBoardId);
          setSelectedBoard(newBoard);
          setShowNewBoardDialog(false);
        }}
      />
    </div>
  );
}
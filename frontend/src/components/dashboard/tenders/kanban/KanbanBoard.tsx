"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KanbanBoard } from "@/types/kanban";
import { Plus } from "lucide-react";
import { useEffect } from "react";

interface KanbanBoardTabsProps {
  boards: KanbanBoard[];
  currentBoardId?: string;
  onBoardSelect?: (boardId: string) => void;
  onNewBoard?: () => void;
}

export function KanbanBoardTabs({ 
  boards, 
  currentBoardId,
  onBoardSelect,
  onNewBoard
}: KanbanBoardTabsProps) {
  const validBoards = boards.filter(board => 
    board?.id && typeof board.id === "string"
  );
  useEffect(() => {
    if (currentBoardId && validBoards.some(b => b.id === currentBoardId)) {
      onBoardSelect?.(currentBoardId);
    }
  }, [validBoards, currentBoardId, onBoardSelect]);

  return (
    <Tabs 
      value={currentBoardId} 
      onValueChange={(value) => {
        if (value === "new-board") {
          onNewBoard?.();
        } else if (value !== currentBoardId && onBoardSelect) {
          onBoardSelect(value);
        }
      }}
      className="mb-4"
    >
      <TabsList className="inline-flex flex-wrap h-auto py-2 px-3 bg-muted/20 gap-3 rounded-lg border shadow-sm">
        {validBoards.map((board) => (
          <TabsTrigger 
            key={board.id} 
            value={board.id}
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm px-4 py-2 text-sm rounded-md transition-all border bg-background hover:bg-muted/50 text-muted-foreground shadow-sm"
          >
            {board.name}
          </TabsTrigger>
        ))}
        {onNewBoard && (
          <TabsTrigger
            value="new-board"
            className="px-4 py-2 text-sm rounded-md transition-all flex items-center border-dashed border-2 bg-background hover:bg-muted/50 text-muted-foreground hover:text-primary border-primary/30 hover:border-primary"
          >
            <Plus className="h-4 w-4 mr-2" />
            Nowa tablica
          </TabsTrigger>
        )}
      </TabsList>
    </Tabs>
  );
}
import { useState, useCallback, useEffect } from 'react';

interface KanbanBoardTenderItem {
  id?: string;
  board_id: string;
  column_id: string;
  tender_analysis_result_id: string;
  order: number;
  created_at?: string;
  updated_at?: string;
}

interface KanbanColumn {
  id?: string;
  name: string;
  order?: number;
  color?: string;
  limit?: number;
  tender_items: KanbanBoardTenderItem[];
}

interface KanbanBoard {
  id?: string;
  _id?: string;
  user_id: string;
  org_id?: string;
  name: string;
  shared_with: string[];
  created_at?: string;
  updated_at?: string;
  columns: KanbanColumn[];
  assigned_users: string[];
}

export const useKanbanBoards = () => {
  const [kanbanBoards, setKanbanBoards] = useState<KanbanBoard[]>([]);
  const [boardsLoading, setBoardsLoading] = useState(false);

  const fetchKanbanBoards = useCallback(async () => {
    try {
      setBoardsLoading(true);
      const token = localStorage.getItem("token") || "";
      const url = `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/boards`;
      console.log("Fetching kanban boards from:", url);

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const boards = await response.json();
        console.log("Successfully fetched boards:", boards);
        console.log("Board structure sample:", boards[0] ? {
          name: boards[0].name,
          columnsCount: boards[0].columns?.length,
          firstColumnSample: boards[0].columns?.[0] ? {
            name: boards[0].columns[0].name,
            tenderItemsCount: boards[0].columns[0].tender_items?.length
          } : null
        } : "No boards found");
        setKanbanBoards(boards);
      } else {
        console.error("Failed to fetch kanban boards", {
          status: response.status,
          statusText: response.statusText,
          url: response.url
        });
        setKanbanBoards([]);
      }
    } catch (error) {
      console.error("Error fetching kanban boards:", error);
      setKanbanBoards([]);
    } finally {
      setBoardsLoading(false);
    }
  }, []);

  const getTenderBoards = useCallback((tenderId: string): string[] => {
    const boardNames: string[] = [];
    for (const board of kanbanBoards) {
      for (const column of board.columns) {
        const hasItem = column.tender_items.some(item => item.tender_analysis_result_id === tenderId);
        if (hasItem) {
          boardNames.push(board.name);
          break;
        }
      }
    }
    return boardNames;
  }, [kanbanBoards]);

  useEffect(() => {
    fetchKanbanBoards();
  }, [fetchKanbanBoards]);

  return {
    kanbanBoards,
    boardsLoading,
    fetchKanbanBoards,
    getTenderBoards
  };
};
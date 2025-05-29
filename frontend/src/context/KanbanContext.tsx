"use client";

import {
  createContext,
  useState,
  useContext,
  useCallback,
  useEffect,
  useRef,
} from "react";
import {
  getBoards,
  createBoard,
  updateBoard,
  deleteBoard,
  getColumns,
  createColumn,
  updateColumn,
  deleteColumn,
  getTenderItems,
  createTenderItem,
  updateTenderItem,
  deleteTenderItem,
  getBoardById,
} from "@/utils/kanbanActions";
import { KanbanBoard, KanbanColumn, KanbanTenderItem, MoveTenderRequest } from "@/types/kanban";

const STORAGE_KEY = "kanban_state";

interface KanbanState {
  boards: KanbanBoard[];
  selectedBoard: KanbanBoard | null;
}

interface KanbanContextType extends KanbanState {
  isLoading: boolean;
  error: string | null;

  fetchAllBoards: () => Promise<void>;
  fetchBoardById: (boardId: string) => Promise<KanbanBoard | null>;
  createBoardAction: (boardData: Partial<KanbanBoard>) => Promise<KanbanBoard>;
  updateBoardAction: (boardId: string, boardData: Partial<KanbanBoard>) => Promise<KanbanBoard>;
  deleteBoardAction: (boardId: string) => Promise<void>;

  createColumnAction: (boardId: string, columnData: Partial<KanbanColumn>) => Promise<KanbanColumn>;
  updateColumnAction: (boardId: string, columnId: string, columnData: Partial<KanbanColumn>) => Promise<KanbanColumn>;
  deleteColumnAction: (boardId: string, columnId: string) => Promise<void>;
  fetchColumns: (boardId: string) => Promise<KanbanColumn[] | null>;

  createTenderItemAction: (
    boardId: string,
    columnId: string,
    itemData: Partial<KanbanTenderItem>
  ) => Promise<KanbanTenderItem>;
  updateTenderItemAction: (
    boardId: string,
    columnId: string,
    itemId: string,
    itemData: Partial<KanbanTenderItem>
  ) => Promise<KanbanTenderItem>;
  deleteTenderItemAction: (
    boardId: string,
    columnId: string,
    itemId: string
  ) => Promise<void>;
  moveTenderItemAction: (
    boardId: string,
    tenderId: string,
    sourceColumnId: string,
    targetColumnId: string
  ) => Promise<void>;
  fetchTenderItems: (boardId: string, columnId: string) => Promise<KanbanTenderItem[] | null>;

  setSelectedBoard: (board: KanbanBoard | null) => void;
  clearError: () => void;
  reset: () => void;
}

const KanbanContext = createContext<KanbanContextType | undefined>(undefined);

function getStoredState(): KanbanState | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch (error) {
    console.error("Error parsing stored Kanban state:", error);
    return null;
  }
}

const initialState: KanbanState = {
  boards: [],
  selectedBoard: null,
};

export function KanbanProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<KanbanState>(() => {
    const stored = getStoredState();
    return stored || initialState;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Add a map to track in-progress tender moves
  const inProgressMoves = useRef<Map<string, boolean>>(new Map());

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  }, [state]);

  const handleError = (err: any) => {
    const message = err?.message || "An error occurred";
    setError(message);
    setIsLoading(false);
  };

  const fetchAllBoards = useCallback(async () => {
    try {
      setIsLoading(true);
      const boardsData = await getBoards();
      setState((prev) => ({ ...prev, boards: boardsData }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchBoardById = useCallback(async (boardId: string): Promise<KanbanBoard | null> => {
    try {
      setIsLoading(true);
      const board = await getBoardById(boardId);
      setState((prev) => ({
        ...prev,
        boards: prev.boards.some(b => b.id === board.id)
          ? prev.boards.map(b => b.id === board.id ? board : b)
          : [...prev.boards, board],
        selectedBoard: board,
      }));
      return board;
    } catch (err) {
      handleError(err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createBoardAction = useCallback(
    async (boardData: Partial<KanbanBoard>): Promise<KanbanBoard> => {
      try {
        setIsLoading(true);
        const newBoard = await createBoard(boardData);
        setState((prev) => ({
          ...prev,
          boards: [...prev.boards, newBoard],
          selectedBoard: newBoard,
        }));
        return newBoard;
      } catch (err: any) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const updateBoardAction = useCallback(
    async (boardId: string, boardData: Partial<KanbanBoard>): Promise<KanbanBoard> => {
      try {
        setIsLoading(true);
        const updatedBoard = await updateBoard(boardId, boardData);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map((b) => (b.id === boardId ? updatedBoard : b)),
          selectedBoard: prev.selectedBoard?.id === boardId ? updatedBoard : prev.selectedBoard,
        }));
        return updatedBoard;
      } catch (err: any) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const deleteBoardAction = useCallback(async (boardId: string): Promise<void> => {
    try {
      setIsLoading(true);
      await deleteBoard(boardId);
      setState((prev) => ({
        ...prev,
        boards: prev.boards.filter((b) => b.id !== boardId),
        selectedBoard: prev.selectedBoard?.id === boardId ? null : prev.selectedBoard,
      }));
    } catch (err) {
      handleError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createColumnAction = useCallback(
    async (boardId: string, columnData: Partial<KanbanColumn>): Promise<KanbanColumn> => {
      try {
        setIsLoading(true);
        const newColumn = await createColumn(boardId, columnData);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board => 
            board.id === boardId 
              ? { ...board, columns: [...board.columns, newColumn] }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId 
            ? { ...prev.selectedBoard, columns: [...prev.selectedBoard.columns, newColumn] }
            : prev.selectedBoard
        }));
        return newColumn;
      } catch (err: any) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const updateColumnAction = useCallback(
    async (boardId: string, columnId: string, columnData: Partial<KanbanColumn>): Promise<KanbanColumn> => {
      try {
        setIsLoading(true);
        const updatedColumn = await updateColumn(boardId, columnId, columnData);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board => 
            board.id === boardId
              ? { 
                  ...board, 
                  columns: board.columns.map(col => 
                    col.id === columnId ? updatedColumn : col
                  ) 
                }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId
            ? { 
                ...prev.selectedBoard, 
                columns: prev.selectedBoard.columns.map(col => 
                  col.id === columnId ? updatedColumn : col
                ) 
              }
            : prev.selectedBoard
        }));
        return updatedColumn;
      } catch (err: any) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const deleteColumnAction = useCallback(
    async (boardId: string, columnId: string): Promise<void> => {
      try {
        setIsLoading(true);
        await deleteColumn(boardId, columnId);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board => 
            board.id === boardId
              ? { 
                  ...board, 
                  columns: board.columns.filter(col => col.id !== columnId) 
                }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId
            ? { 
                ...prev.selectedBoard, 
                columns: prev.selectedBoard.columns.filter(col => col.id !== columnId) 
              }
            : prev.selectedBoard
        }));
      } catch (err: any) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const createTenderItemAction = useCallback(
    async (boardId: string, columnId: string, itemData: Partial<KanbanTenderItem>): Promise<KanbanTenderItem> => {
      try {
        setIsLoading(true);
        const newItem = await createTenderItem(boardId, columnId, itemData);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board => 
            board.id === boardId
              ? {
                  ...board,
                  columns: board.columns.map(column =>
                    column.id === columnId
                      ? { ...column, tenderItems: [...column.tenderItems, newItem] }
                      : column
                  )
                }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId
            ? {
                ...prev.selectedBoard,
                columns: prev.selectedBoard.columns.map(column =>
                  column.id === columnId
                    ? { ...column, tenderItems: [...column.tenderItems, newItem] }
                    : column
                )
              }
            : prev.selectedBoard
        }));
        return newItem;
      } catch (err) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const updateTenderItemAction = useCallback(
    async (boardId: string, columnId: string, itemId: string, itemData: Partial<KanbanTenderItem>): Promise<KanbanTenderItem> => {
      try {
        setIsLoading(true);
        const updatedItem = await updateTenderItem(boardId, columnId, itemId, itemData);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board =>
            board.id === boardId
              ? {
                  ...board,
                  columns: board.columns.map(column =>
                    column.id === columnId
                      ? {
                          ...column,
                          tenderItems: column.tenderItems.map(item =>
                            item.id === itemId ? updatedItem : item
                          )
                        }
                      : column
                  )
                }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId
            ? {
                ...prev.selectedBoard,
                columns: prev.selectedBoard.columns.map(column =>
                  column.id === columnId
                    ? {
                        ...column,
                        tenderItems: column.tenderItems.map(item =>
                          item.id === itemId ? updatedItem : item
                        )
                      }
                    : column
                )
              }
            : prev.selectedBoard
        }));
        return updatedItem;
      } catch (err) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const deleteTenderItemAction = useCallback(
    async (boardId: string, columnId: string, itemId: string): Promise<void> => {
      try {
        setIsLoading(true);
        await deleteTenderItem(boardId, columnId, itemId);
        setState((prev) => ({
          ...prev,
          boards: prev.boards.map(board =>
            board.id === boardId
              ? {
                  ...board,
                  columns: board.columns.map(column =>
                    column.id === columnId
                      ? {
                          ...column,
                          tenderItems: column.tenderItems.filter(item => item.id !== itemId)
                        }
                      : column
                  )
                }
              : board
          ),
          selectedBoard: prev.selectedBoard?.id === boardId
            ? {
                ...prev.selectedBoard,
                columns: prev.selectedBoard.columns.map(column =>
                  column.id === columnId
                    ? {
                        ...column,
                        tenderItems: column.tenderItems.filter(item => item.id !== itemId)
                      }
                    : column
                )
              }
            : prev.selectedBoard
        }));
      } catch (err) {
        handleError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const fetchColumns = useCallback(async (boardId: string) => {
    try {
      setIsLoading(true);
      return await getColumns(boardId);
    } catch (err) {
      handleError(err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchTenderItems = useCallback(async (boardId: string, columnId: string) => {
    try {
      setIsLoading(true);
      return await getTenderItems(boardId, columnId);
    } catch (err) {
      handleError(err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const setSelectedBoard = useCallback((board: KanbanBoard | null) => {
    setState((prev) => ({ ...prev, selectedBoard: board }));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const reset = useCallback(() => {
    setState(initialState);
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const moveTenderItemAction = useCallback(
    async (
      boardId: string,
      tenderId: string,
      sourceColumnId: string,
      targetColumnId: string
    ): Promise<void> => {
      // Create a unique key for this move operation
      const moveKey = `${boardId}:${tenderId}:${sourceColumnId}:${targetColumnId}`;
      
      // Check if this exact move is already in progress
      if (inProgressMoves.current.get(moveKey)) {
        console.log("Move already in progress, skipping duplicate request");
        return;
      }
      
      // Mark this move as in progress
      inProgressMoves.current.set(moveKey, true);
      
      try {
        // First, find the tender item in the source column
        let tenderItem: KanbanTenderItem | undefined;
        
        // Make a copy of current state for optimistic updates
        setState((prev) => {
          // Find the board
          const board = prev.boards.find(b => b.id === boardId);
          if (!board) return prev; // No changes if board not found
          
          // Find the source column
          const sourceColumn = board.columns.find(c => c.id === sourceColumnId);
          if (!sourceColumn) return prev; // No changes if source column not found
          
          // Find the target column
          const targetColumn = board.columns.find(c => c.id === targetColumnId);
          if (!targetColumn) return prev; // No changes if target column not found
          
          // Find the tender item in source column
          const itemIndex = sourceColumn.tenderItems.findIndex(item => item.id === tenderId);
          if (itemIndex === -1) return prev; // No changes if item not found
          
          // Get a copy of the tender item
          tenderItem = { 
            ...sourceColumn.tenderItems[itemIndex],
            column_id: targetColumnId // Update the column_id
          };
          
          // Update the boards with the item moved
          const updatedBoards = prev.boards.map(b => {
            if (b.id !== boardId) return b;
            
            return {
              ...b,
              columns: b.columns.map(col => {
                // Remove from source column
                if (col.id === sourceColumnId) {
                  return {
                    ...col,
                    tenderItems: col.tenderItems.filter(item => item.id !== tenderId)
                  };
                }
                
                // Add to target column
                if (col.id === targetColumnId) {
                  return {
                    ...col,
                    tenderItems: [...col.tenderItems, tenderItem!]
                  };
                }
                
                return col;
              })
            };
          });
          
          // Update selected board if necessary
          let updatedSelectedBoard = prev.selectedBoard;
          if (prev.selectedBoard?.id === boardId) {
            updatedSelectedBoard = {
              ...prev.selectedBoard,
              columns: prev.selectedBoard.columns.map(col => {
                // Remove from source column
                if (col.id === sourceColumnId) {
                  return {
                    ...col,
                    tenderItems: col.tenderItems.filter(item => item.id !== tenderId)
                  };
                }
                
                // Add to target column
                if (col.id === targetColumnId) {
                  return {
                    ...col,
                    tenderItems: [...col.tenderItems, tenderItem!]
                  };
                }
                
                return col;
              })
            };
          }
          
          return {
            ...prev,
            boards: updatedBoards,
            selectedBoard: updatedSelectedBoard
          };
        });
        
        // Now perform the actual API call in the background
        const token = localStorage.getItem("token");
        const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;
        
        if (!serverUrl) {
          throw new Error("Server URL is not defined");
        }

        if (!token) {
          throw new Error("Authentication token is missing");
        }
        
        // Log request details for debugging
        console.log("Moving tender - Request details:", {
          boardId,
          tenderId,
          sourceColumnId,
          targetColumnId,
          url: `${serverUrl}/boards/${boardId}/tenders/${tenderId}/move`
        });
        
        // Create request payload using the proper interface
        const moveRequestPayload: MoveTenderRequest = {
          source_column_id: sourceColumnId,
          target_column_id: targetColumnId
        };
        
        try {
          // Try the fetch with retries if needed
          const makeRequest = async (retryCount = 0, maxRetries = 2): Promise<Response> => {
            try {
              const response = await fetch(
                `${serverUrl}/boards/${boardId}/tenders/${tenderId}/move`,
                {
                  method: "PUT",
                  headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                  },
                  credentials: "include",
                  body: JSON.stringify(moveRequestPayload)
                }
              );
              
              if (!response.ok && retryCount < maxRetries) {
                console.log(`Retrying request (${retryCount + 1}/${maxRetries})...`);
                await new Promise(resolve => setTimeout(resolve, 500)); // wait 500ms before retry
                return makeRequest(retryCount + 1, maxRetries);
              }
              
              return response;
            } catch (error) {
              if (retryCount < maxRetries) {
                console.log(`Network error, retrying (${retryCount + 1}/${maxRetries})...`);
                await new Promise(resolve => setTimeout(resolve, 500)); // wait 500ms before retry
                return makeRequest(retryCount + 1, maxRetries);
              }
              throw error;
            }
          };
          
          const moveResponse = await makeRequest();
          
          if (!moveResponse.ok) {
            let errorMessage = `Status: ${moveResponse.status} ${moveResponse.statusText}`;
            try {
              const errorText = await moveResponse.text();
              errorMessage += `, Details: ${errorText}`;
            } catch (e) {
              // If we can't get the error text, just continue
            }
            throw new Error(`Failed to move tender item: ${errorMessage}`);
          }
          
          // If successful, log the response
          console.log("Successfully moved tender item");
        } catch (fetchError: any) {
          console.error("Fetch error when moving tender:", fetchError);
          throw new Error(`Network error while moving tender: ${fetchError.message}`);
        }
      } catch (err: any) {
        handleError(err);
        
        // Revert the optimistic update on error
        fetchBoardById(boardId).catch(console.error);
        
        throw err;
      } finally {
        // Clear this move from the in-progress map after a small delay
        // This prevents immediate re-attempts but allows future moves
        setTimeout(() => {
          inProgressMoves.current.delete(moveKey);
        }, 500);
      }
    },
    [fetchBoardById]
  );

  const value: KanbanContextType = {
    ...state,
    isLoading,
    error,
    fetchAllBoards,
    fetchBoardById,
    createBoardAction,
    updateBoardAction,
    deleteBoardAction,
    createColumnAction,
    updateColumnAction,
    deleteColumnAction,
    fetchColumns,
    createTenderItemAction,
    updateTenderItemAction,
    deleteTenderItemAction,
    moveTenderItemAction,
    fetchTenderItems,
    setSelectedBoard,
    clearError,
    reset,
  };

  return <KanbanContext.Provider value={value}>{children}</KanbanContext.Provider>;
}

export function useKanban() {
  const context = useContext(KanbanContext);
  if (!context) {
    throw new Error("useKanban must be used within a KanbanProvider");
  }
  return context;
}
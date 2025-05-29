import { handleResponse } from "./api";
import { KanbanColumn, KanbanBoard, KanbanTenderItem } from "@/types/kanban";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token || ""}`,
  };
}

function parseBoard(apiBoard: any): KanbanBoard {
  return {
    id: apiBoard._id,
    user_id: apiBoard.user_id,
    org_id: apiBoard.org_id || null, // Add org_id property
    name: apiBoard.name,
    shared_with: apiBoard.shared_with,
    created_at: apiBoard.created_at,
    updated_at: apiBoard.updated_at,
    columns: (apiBoard.columns || []).map(parseColumn),
  };
}

function parseColumn(apiColumn: any): KanbanColumn {
  return {
    id: apiColumn._id,
    name: apiColumn.name,
    order: apiColumn.order,
    color: apiColumn.color,
    limit: apiColumn.limit,
    tenderItems: (apiColumn.tender_items || []).map(parseTenderItem),
  };
}

function parseTenderItem(apiItem: any): KanbanTenderItem {
  return {
    id: apiItem._id,
    board_id: apiItem.board_id,
    column_id: apiItem.column_id,
    tender_analysis_result_id: apiItem.tender_analysis_result_id,
    order: apiItem.order,
    created_at: apiItem.created_at,
    updated_at: apiItem.updated_at,
  };
}

// Board Actions
export async function getBoardById(boardId: string): Promise<KanbanBoard> {
  const response = await fetch(`${serverUrl}/boards/${boardId}`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  return parseBoard(await handleResponse(response));
}

export async function getBoards(): Promise<KanbanBoard[]> {
  const response = await fetch(`${serverUrl}/boards`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  const data = await handleResponse<any[]>(response);
  return data.map(parseBoard);
}

export async function createBoard(boardData: Partial<KanbanBoard>): Promise<KanbanBoard> {
  const response = await fetch(`${serverUrl}/boards`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(boardData),
  });
  const data = await handleResponse<any>(response);
  return parseBoard(data);
}

export async function updateBoard(boardId: string, boardData: Partial<KanbanBoard>): Promise<KanbanBoard> {
  const response = await fetch(`${serverUrl}/boards/${boardId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(boardData),
  });
  return parseBoard(await handleResponse(response));
}

export async function deleteBoard(boardId: string): Promise<void> {
  const response = await fetch(`${serverUrl}/boards/${boardId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  await handleResponse(response);
}

// Column Actions
export async function getColumns(boardId: string): Promise<KanbanColumn[]> {
  const response = await fetch(`${serverUrl}/boards/${boardId}/columns`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  const data = await handleResponse<any[]>(response);
  return data.map(parseColumn);
}

export async function createColumn(boardId: string, columnData: Partial<KanbanColumn>): Promise<KanbanColumn> {
  const response = await fetch(`${serverUrl}/boards/${boardId}/columns`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(columnData),
  });
  return parseColumn(await handleResponse(response));
}

export async function updateColumn(
  boardId: string,
  columnId: string,
  columnData: Partial<KanbanColumn>
): Promise<KanbanColumn> {
  const response = await fetch(`${serverUrl}/boards/${boardId}/columns/${columnId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(columnData),
  });
  return parseColumn(await handleResponse(response));
}

export async function deleteColumn(boardId: string, columnId: string): Promise<KanbanColumn> {
  const response = await fetch(`${serverUrl}/boards/${boardId}/columns/${columnId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  return parseColumn(await handleResponse(response));
}

// Tender Item Actions
export async function getTenderItems(boardId: string, columnId: string): Promise<KanbanTenderItem[]> {
  const response = await fetch(`${serverUrl}/boards/${boardId}/columns/${columnId}/items`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  const data = await handleResponse<any[]>(response);
  return data.map(parseTenderItem);
}

export async function createTenderItem(
  boardId: string,
  columnId: string,
  itemData: Partial<KanbanTenderItem>
): Promise<KanbanTenderItem> {
  const fullData = {
    ...itemData,
    board_id: boardId,
    column_id: columnId,
  };

  const response = await fetch(`${serverUrl}/boards/${boardId}/columns/${columnId}/items`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(fullData),
  });
  return parseTenderItem(await handleResponse(response));
}

export async function updateTenderItem(
  boardId: string,
  columnId: string,
  itemId: string,
  itemData: Partial<KanbanTenderItem>
): Promise<KanbanTenderItem> {
  const fullData = {
    ...itemData,
    board_id: boardId,
    column_id: columnId,
  };

  const response = await fetch(`${serverUrl}/boards/${boardId}/columns/${columnId}/items/${itemId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(fullData),
  });
  return parseTenderItem(await handleResponse(response));
}

export async function deleteTenderItem(
  boardId: string,
  columnId: string,
  itemId: string
): Promise<void> {
  const response = await fetch(
    `${serverUrl}/boards/${boardId}/columns/${columnId}/items/${itemId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(),
    }
  );
  await handleResponse<void>(response);
}
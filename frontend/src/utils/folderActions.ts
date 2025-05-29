import { FolderData } from "@/types";
import { handleResponse } from "./api";
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;


export const createFolder = async (folder: Partial<FolderData>): Promise<FolderData> => {
    const response = await fetch(`${serverUrl}/folders/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(folder),
    });
    if (!response.ok) throw new Error('Failed to create folder');
    return handleResponse<FolderData>(response);
  };


export const getUserFolders = async (userId: string): Promise<FolderData[]> => {
    const response = await fetch(`${serverUrl}/folders?owner_id=${userId}`);
    if (!response.ok) throw new Error('Failed to fetch folders');
    return response.json();
  };


  export const getAssistantFolders = async (assistantId: string, userId: string): Promise<FolderData[]> => {
    const response = await fetch(`${serverUrl}/folders/assistant/${assistantId}?owner_id=${userId}`);
    if (!response.ok) throw new Error('Failed to fetch folders');
    return response.json();
  };
  
  export const getAssistantRootFolders = async (assistantId: string, userId: string): Promise<FolderData[]> => {
    const response = await fetch(`${serverUrl}/folders/assistant/${assistantId}/root?owner_id=${userId}`);
    if (!response.ok) throw new Error('Failed to fetch root folders');
    return response.json();
  };


  export const getDefaultFolder = async (assistantId: string, ownerId: string): Promise<FolderData> => {
    const response = await fetch(`${serverUrl}/folders/get-default/${assistantId}/${ownerId}`);
    if (!response.ok) {
      throw new Error('Failed to get default folder');
    }
    return response.json();
  };

  export const deleteFolder = async (folderId: string): Promise<void> => {
    const response = await fetch(`${serverUrl}/folders/${folderId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete folder');
};
  

export const renameFolder = async (folderId: string, newName: string): Promise<FolderData> => {
  const response = await fetch(`${serverUrl}/folders/${folderId}/rename?new_name=${encodeURIComponent(newName)}`, {
      method: 'PATCH',
      headers: {
          'Content-Type': 'application/json'
      }
  });
  
  if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to rename folder');
  }
  
  return handleResponse<FolderData>(response);
};

// utils/assistantActions.ts
import { Assistant } from "@/types"
import { handleResponse } from "./api";
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export interface AssistantTool {
    type: string;
    [key: string]: any;
  }
export interface AssistantUpdateData {
    name?: string;
    model?: string;
    description?: string;
    system_prompt?: string;
    icon?: string;
    shared_with?: Array<Record<string, any>>;
    tools?: AssistantTool[];
    temperature?: number;
    org_id?: string | null; // Add org_id field
  }

export const updateAssistant = async (
    assistant: Assistant, 
    updatedData: AssistantUpdateData
  ): Promise<Assistant> => {
    // Remove any undefined values to avoid sending them
    const cleanedData = Object.fromEntries(
      Object.entries(updatedData).filter(([_, value]) => value !== undefined)
    );
  
    const response = await fetch(`${serverUrl}/assistants/${assistant._id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cleanedData),
      credentials: 'include', // If you're using cookies for auth
    });
    
    return handleResponse<Assistant>(response);
  };
  
  
  
  export const deleteAssistant = async (
    assistant: Assistant
  ): Promise<void> => {
    const response = await fetch(`${serverUrl}/assistants/${assistant._id}`, {
      method: 'DELETE',
    });
    
    return handleResponse<void>(response);
  };

export const createAssistant = async (assistant: Omit<Assistant, 'id' | 'created_at'>): Promise<Assistant> => {
    const response = await fetch(`${serverUrl}/assistants/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(assistant),
    });
    
    return handleResponse<Assistant>(response);
}

export const getUserAssistants = async (ownerId: string, orgId?: string): Promise<Assistant[]> => {
    try {
      const query = orgId && orgId.trim() ? `?org_id=${orgId}` : '';
      const response = await fetch(`${serverUrl}/assistants/owner/${ownerId}${query}`);
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch assistants');
      }
      
      return response.json();
    } catch (error) {
      console.error('Error fetching assistants:', error);
      throw error;
    }
  }
import { Conversation, CreateConversationRequest, PaginatedConversations } from "../types";
import { handleResponse } from "./api";
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export const createConversation = async (request: CreateConversationRequest): Promise<Conversation> =>  {
    const response = await fetch(`${serverUrl}/conversations/new`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    return handleResponse<Conversation>(response);
}

export async function deleteConversation(conversationId: string): Promise<void> {
  try {
    const response = await fetch(`${serverUrl}/conversations/${conversationId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Failed to delete conversation');
    }
  } catch (error) {
    console.error('Error deleting conversation:', error);
    throw error;
  }
}



export async function getConversation(chatId: string | null): Promise<Conversation | null> {
    if (!chatId) return null;
  
    try {
      const response = await fetch(`${serverUrl}/conversations/${chatId}`);
      if (!response.ok) throw new Error('Failed to fetch conversation');
      
      const conversation: Conversation = await response.json();
      return conversation;
    } catch (error) {
      console.error('Error fetching conversation:', error);
      throw error;
    }
  }


export async function getConversationsByAssistant(
    assistantId: string, 
    page: number = 1
  ): Promise<PaginatedConversations> {
    try {
      const response = await fetch(
        `${serverUrl}/conversations/assistant/${assistantId}?page=${page}`
      );
      
      if (!response.ok) throw new Error('Failed to fetch conversations');
      
      const paginatedConversations: PaginatedConversations = await response.json();
      return paginatedConversations;
    } catch (error) {
      console.error('Error fetching conversations:', error);
      throw error;
    }
  }


export async function checkOrCreateConversation(
    userId: string | undefined,
    assistantId: string | undefined,
    orgId?: string  // Optional orgId to be sent when applicable
  ): Promise<Conversation> {
    try {
      const response = await fetch(
        `${serverUrl}/conversations/create-if-needed`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: userId,
            assistant_id: assistantId,
            org_id: orgId,  // Include orgId if the assistant is shared
            our_rag: true
          })
        }
      );
  
      if (!response.ok) {
        throw new Error('Failed to check/create conversation');
      }
      const result: Conversation = await response.json();
      console.log(result);
      return result;
    } catch (error) {
      console.error('Error checking/creating conversation:', error);
      throw error;
    }
  }

  
  export async function updateConversationTitle(
    conversationId: string,
    title: string
  ): Promise<Conversation> {
    try {
      const response = await fetch(
        `${serverUrl}/conversations/${conversationId}/update-title`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ title }),
        }
      );
  
      return handleResponse<Conversation>(response);
    } catch (error) {
      console.error('Error updating conversation title:', error);
      throw error;
    }
  }
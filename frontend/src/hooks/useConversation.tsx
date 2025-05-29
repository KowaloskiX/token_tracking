import { useDashboard } from "@/context/DashboardContext";
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

interface CreateConversationResponse {
  _id: string;
  assistant_id: string;
  user_id: string;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
    created_at: number;
  }>;
  thread_id: string;
  title: string;
  started_at: string;
  last_updated: Date;
}

export const useConversation = () => {
  const { 
    user, 
    currentAssistant, 
    setCurrentConversation 
  } = useDashboard();

  const createNewConversation = async (initialMessage?: string) => {
    if (!user?._id || !currentAssistant?._id) {
      throw new Error('User or Assistant not found');
    }

    try {
      const response = await fetch(`${serverUrl}/conversations/new`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user._id,
          assistant_id: currentAssistant._id,
          initial_message: initialMessage,
          our_rag: currentAssistant.pinecone_config ? true : undefined
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create conversation');
      }

      const conversation: CreateConversationResponse = await response.json();
      setCurrentConversation({
        _id: conversation._id,
        assistant_id: conversation.assistant_id,
        user_id: conversation.user_id,
        messages: conversation.messages,
        thread_id: conversation.thread_id,
        title: conversation.title,
        last_updated: new Date(conversation.last_updated),
      });

      return conversation;
    } catch (error) {
      console.error('Error creating conversation:', error);
      throw error;
    }
  };

  return {
    createNewConversation,
  };
};
export interface Assistant {
    _id?: string;
    name: string;
    model: string;
    owner_id: string;
    description?: string;
    system_prompt?: string;
    org_id?: string;
    icon?: string;
    shared_with?: Record<string, any>[];
    openai_vectorstore_id?: string;
    tools?: any[];
    temperature?: number;
    openai_assistant_id?: string;
    created_at?: Date;
    pinecone_config?: {
      index_name: string;
      namespace: string;
      embedding_model: string
    };
    tender_pinecone_id?: string;
    uploaded_files_pinecone_id?: string;
  }


  export interface Conversation {
    _id: string;
    assistant_id: string;
    user_id: string;
    messages: Message[];
    thread_id: string;
    title: string;
    last_updated?: Date;
  }

  export interface Attachment {
    name: string;     
    citation?: string; 
    file_id?: string; 
  }
  
  export interface Message {
    id?: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at?: number;
    functionCall?: string;
    citations?: Array<{
      content?: string;
      filename?: string;
      file_id?: string;
    }>;
    attachments?: Array<{
      file_id?: string;
      name?: string;
      citation?: string;
    }>;
  }
  
  export interface CreateConversationRequest {
    user_id: string | undefined;
    assistant_id: string | undefined;
    initial_message?: string;
    our_rag?: boolean;
  }
  
  export interface AskAiRequest {
    prompt: string;
    model: string;
    thread_id: string;
    stream: boolean;
    assistant_id: string;
    run_id?: string;
    call_id?: string;
  }

  export interface Organization {
    _id?: string;
    name: string;
  }

  export interface User {
    _id?: string;
    org_id: string;
    email: string;
    name: string;
    google_id?: string;
    role?: string;
    created_at?: string;
    subscription?: {
      plan_type: string;
      status: string;
      stripe_customer_id: string;
    };
    daily_tokens?: number;
    total_tokens?: number;
    last_token_reset?: string;
    marketing_consent?: {
      communication_emails?: boolean;
      marketing_emails?: boolean;
      social_emails?: boolean;
      security_emails: boolean;
    };
  }

  export interface UserCreateData {
    email: string;
    password: string;
    name: string;
    org_id?: string;
    role?: string;
  }
  
  export interface UserResponse {
    _id: string;
    email: string;
    name: string;
    org_id: string;
    role: string;
    created_at: string;
  }
  
  export interface RegisterResponse {
    access_token: string;
    token_type: string;
    user: UserResponse;
  }

export interface DashboardState {
  user: User | null;
  organization: Organization | null;
  currentAssistant: Assistant | null;
  currentConversation: Conversation | null;
  conversationLoading: boolean;
  assistants: Assistant[]
}



  export interface LoginCredentials {
    email: string;
    password: string;
  }

  export interface PaginatedConversations {
    data: Conversation[];
    page: number;
    total_pages: number;
    total_items: number;
    has_next: boolean;
    has_previous: boolean;
  }


  export interface FileData {
    _id: string;
    filename: string;
    purpose: string;
    bytes: number;
    owner_id: string;
    blob_url?: string;
    url?: string;
    type: string;
    parent_folder_id?: string;
    openai_file_id: string;
    created_at?: string;
    user_file?: boolean;
  }
  
  export interface FolderData {
    _id: string;
    name: string;
    owner_id: string;
    parent_folder_id?: string;
    files: string[];
    assistant_id: string;
    subfolders: string[];
    created_at?: string;
  }
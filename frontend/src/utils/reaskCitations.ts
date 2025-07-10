// Create this file: frontend/src/utils/reaskCitations.ts

const API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export interface ReaskCitationsRequest {
  conversation_id: string;
  message_id: string;
  file_text: string;
  unfound_citations: string[];
}

export interface ReaskCitationsResponse {
  status: string;
  message: string;
  updated_citations: Array<{
    content: string;
    filename: string;
    file_id?: string;
  }>;
  replacements: Record<string, string>;
  citation_details?: Record<string, {
    confidence: 'high' | 'medium' | 'low';
    location_type: 'table' | 'body' | 'header' | 'footer' | 'other';
    replacement: string;
    reconstruction_notes?: string;
  }>;
}

export async function reaskCitationsForFile(
  request: ReaskCitationsRequest
): Promise<ReaskCitationsResponse> {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Authentication token not found');
  }

  const response = await fetch(`${API_URL}/reask-citations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}
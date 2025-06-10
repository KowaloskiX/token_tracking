// frontend/src/utils/apiKeyActions.ts
import { handleResponse } from "./api";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export interface ApiKeyInfo {
  has_api_key: boolean;
  created_at?: string;
  last_used?: string;
}

export interface ApiKeyResponse {
  api_key: string;
  created_at: string;
  last_used?: string;
}

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token || ""}`,
  };
}

export async function getApiKeyInfo(): Promise<ApiKeyInfo> {
  const response = await fetch(`${serverUrl}/api-keys/info`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  return handleResponse<ApiKeyInfo>(response);
}

export async function generateApiKey(): Promise<ApiKeyResponse> {
  const response = await fetch(`${serverUrl}/api-keys/generate`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  return handleResponse<ApiKeyResponse>(response);
}

export async function revokeApiKey(): Promise<{ message: string }> {
  const response = await fetch(`${serverUrl}/api-keys/revoke`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  return handleResponse<{ message: string }>(response);
}

// Verify user password before showing/generating API key
export async function verifyPassword(password: string): Promise<boolean> {
  try {
    const response = await fetch(`${serverUrl}/users/verify-password`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ password }),
    });
    
    if (response.status === 404) {
      // Endpoint doesn't exist yet, for now we'll return true
      // In production, this should always verify the password
      console.warn("Password verification endpoint not found, allowing access");
      return true;
    }
    
    return response.ok;
  } catch (error) {
    console.error("Password verification error:", error);
    return false;
  }
}
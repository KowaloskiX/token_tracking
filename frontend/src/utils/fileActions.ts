import { FileData } from "@/types";
import { handleResponse } from "./api";
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

// Response types for different endpoints
interface StandardUploadResponse {
  filename: string;
  bytes: number;
  owner_id: string;
  purpose: string;
  parent_folder_id?: string;
  openai_file_id: string;
  type: string;
  shared_with: any[];
  _id: string;
  created_at: string;
}

interface ExcelUploadResponse {
  message: string;
  created_files: FileData[];
}


interface FileWithOpenAIId {
  filename: string;
  openai_file_id: string;
  type?: string;
  bytes?: number;
  blob_url?: string;
}

interface BatchCreateFilesRequest {
  files: FileWithOpenAIId[];
  owner_id: string;
  assistant_id?: string;
  parent_folder_id?: string;
}

type UploadResponse = StandardUploadResponse | ExcelUploadResponse;

export const uploadFile = async (
  file: File,
  purpose: string,
  ownerId: string,
  parentFolderId: string,
  fileType: string,
  assistantId?: string 
): Promise<FileData[]> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('owner_id', ownerId);
  formData.append('parent_folder_id', parentFolderId);
  formData.append('file_type', fileType);

  if (assistantId) {
    formData.append('assistant_id', assistantId);
  }

  // Determine if this is an Excel file
  const isExcel = file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls');
  const endpoint = isExcel ? 'excel-upload-json' : '';

  const response = await fetch(`${serverUrl}/files/${endpoint}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to upload file');
  }

  const data = await handleResponse<UploadResponse>(response);
  
  // Handle different response formats
  if ('created_files' in data) {
    // Excel upload response
    return data.created_files;
  } else {
    // Standard file upload response
    return [data as FileData];
  }
};

export const getFileById = async (fileId: string): Promise<FileData> => {
  const res = await fetch(`${serverUrl}/files/${fileId}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to fetch file ${fileId}`);
  }
  return handleResponse<FileData>(res);
};

export const getFileBySingleId = async (fileId: string): Promise<FileData> => {
  // First try to get by openai_file_id
  try {
    const res = await fetch(`${serverUrl}/files/by-single-id/${fileId}`);
    if (res.ok) {
      return handleResponse<FileData>(res);
    }
  } catch (error) {
    console.log(`Failed to fetch file by openai_file_id: ${fileId}`);
  }

  // If that fails, try getting by MongoDB _id
  try {
    const res = await fetch(`${serverUrl}/files/${fileId}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Failed to fetch file ${fileId}`);
    }
    return handleResponse<FileData>(res);
  } catch (error) {
    console.error(`Failed to fetch file by _id: ${fileId}`);
    throw error;
  }
};

export const getFileByFilename = async (filename: string): Promise<FileData> => {
  const encodedFilename = encodeURIComponent(filename);
  const res = await fetch(`${serverUrl}/files/by-filename/${encodedFilename}`);
  
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to fetch file by filename ${filename}`);
  }
  
  return handleResponse<FileData>(res);
};

export const getFolderFiles = async (folderId: string): Promise<FileData[]> => {
    const response = await fetch(`${serverUrl}/files/folder/${folderId}/files`);
    if (!response.ok) throw new Error('Failed to fetch files');
    return handleResponse<FileData[]>(response);
};
  
export const deleteFile = async (fileId: string): Promise<void> => {
    const response = await fetch(`${serverUrl}/files/${fileId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete file');
};

export const renameFile = async (fileId: string, newName: string): Promise<FileData> => {
  const response = await fetch(`${serverUrl}/files/${fileId}/rename?new_name=${encodeURIComponent(newName)}`, {
      method: 'PATCH',
      headers: {
          'Content-Type': 'application/json'
      }
  });
  
  if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to rename file');
  }
  
  return handleResponse<FileData>(response);
};


export function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  
  export function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    }).format(date);
  }


  export const getFileType = (filename: string): string => {
    const extension = filename.split('.').pop()?.toLowerCase();
    return extension || 'unknown';
  };


  export const isValidFileName = (fileName: string): boolean => {
    // Basic file name validation
    const validFileNameRegex = /^[^<>:"/\\|?*\x00-\x1F]+$/;
    return validFileNameRegex.test(fileName) && fileName.trim().length > 0;
};

export const sanitizeFileName = (fileName: string): string => {
    // Remove invalid characters and trim
    return fileName
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, '')
        .trim();
};



export async function createFilesWithOpenAIId(data: BatchCreateFilesRequest): Promise<File[]> {
  const response = await fetch(`${serverUrl}/files/upload-existing-openai-files`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to create files');
  }

  return response.json();
}

export async function importTenderFiles(
  files: FileData[], 
  userId: string,
  assistantId: string
) {
  try {
    const filesData = files.map(file => ({
      filename: file.filename,
      openai_file_id: file.openai_file_id,
      type: file.filename.split('.').pop()?.toLowerCase() || 'unknown',
    }));

    return await createFilesWithOpenAIId({
      files: filesData,
      owner_id: userId,
      assistant_id: assistantId
    });
  } catch (error) {
    console.error('Failed to import files:', error);
    throw error;
  }
}


export async function enrichFiles(data: BatchCreateFilesRequest): Promise<FileData[]> {
  const response = await fetch(`${serverUrl}/files/enrich-files`, {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
  });

  if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to enrich files');
  }

  return handleResponse<FileData[]>(response);
}
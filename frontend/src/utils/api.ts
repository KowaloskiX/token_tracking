class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData = { detail: `HTTP error! status: ${response.status}` };
    try {
      errorData = await response.json();
    } catch {
    }
    throw new ApiError(response.status, errorData.detail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  try {
    return await response.json();
  } catch (error) {
    throw new ApiError(500, 'Failed to parse response');
  }
}
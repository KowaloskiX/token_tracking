import { handleResponse } from './api';
import type { SearchResponse, FilterResponse } from '@/types/observability';

const getBaseUrl = () => process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

export const observabilityApi = {
  search: async (params: any, token: string) => {
    const url = `${getBaseUrl()}/test-tender-search`;
    
    const fetchOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(params)
    };

    try {
      const response = await fetch(url, fetchOptions);
      return handleResponse<SearchResponse>(response);
    } catch (fetchError) {
      throw fetchError;
    }
  },

  getSearch: async (searchId: string, token: string) => {
    const url = `${getBaseUrl()}/tender-search/${searchId}`;
    const fetchOptions = {
      headers: { 'Authorization': `Bearer ${token}` }
    };

    try {
      const response = await fetch(url, fetchOptions);
      return handleResponse<SearchResponse>(response);
    } catch (fetchError) {
      throw fetchError;
    }
  },

  filter: async (params: any, token: string) => {
    try {
      const response = await fetch(`${getBaseUrl()}/test-tender-filter`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(params)
      });
      return handleResponse<FilterResponse>(response);
    } catch (fetchError) {
      throw fetchError;
    }
  },

  getFilter: async (filterId: string, token: string) => {
    try {
      const response = await fetch(`${getBaseUrl()}/tender-filter/${filterId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      return handleResponse<any>(response);
    } catch (fetchError) {
      throw fetchError;
    }
  }
};
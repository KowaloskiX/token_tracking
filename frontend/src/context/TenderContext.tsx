'use client';

import { AnalysisCriteria, TenderAnalysis, TenderAnalysisResult } from '@/types/tenders';
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useDashboard } from '@/hooks/useDashboard';

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;
const STORAGE_KEY = 'tender_state';

interface StoredState {
  selectedAnalysisId: string | null;
  selectedResultId: string | null;
}

const getStoredState = (): StoredState | null => {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch (error) {
    console.error('Error parsing stored tender state:', error);
    return null;
  }
};

interface TenderState {
  analyses: TenderAnalysis[];
  selectedAnalysis: TenderAnalysis | null;
  results: TenderAnalysisResult[];
  selectedResult: TenderAnalysisResult | null;
  totalResults: number;
  activeTenders: TenderAnalysisResult[];
}

const initialState: TenderState = {
  analyses: [],
  selectedAnalysis: null,
  results: [],
  selectedResult: null,
  totalResults: 0,
  activeTenders: [] // Initialize as an empty array
};

interface TenderContextType {
  analyses: TenderAnalysis[];
  selectedAnalysis: TenderAnalysis | null;
  results: TenderAnalysisResult[];
  selectedResult: TenderAnalysisResult | null;
  totalResults: number;
  activeTenders: TenderAnalysisResult[];
  isLoading: boolean;
  error: string | null;
  deleteTenderResult: (resultId: string) => Promise<void>;
  createAnalysis: (analysis: {
    name: string;
    company_description: string;
    search_phrase: string;
    sources: string[];
    criteria: AnalysisCriteria[];
  }) => Promise<void>;
  updateAnalysis: (id: string, data: Partial<TenderAnalysis>) => Promise<void>;
  assignUsers: (id: string, newUserIds: string[]) => Promise<void>;
  deleteAnalysis: (id: string) => Promise<void>;
  fetchAnalyses: () => Promise<void>;
  fetchAnalysisById: (id: string) => Promise<void>;
  markAsOpened: (id: string) => Promise<void>;
  markAsUnopened: (id: string) => Promise<void>; //here is
  updateTenderStatus: (id: string, status: 'inactive' | 'active' | 'archived' | 'inBoard') => Promise<void>;
  fetchResults: (analysisId: string, page?: number, limit?: number) => Promise<void>;
  fetchAllActiveTenders: () => Promise<void>;
  fetchTenderResultById: (resultId: string) => Promise<TenderAnalysisResult | null>;
  fetchAllResultsForAnalysis: (analysisId: string) => Promise<TenderAnalysisResult[]>;
  setSelectedResult: (result: TenderAnalysisResult | null) => void;
  setSelectedAnalysis: (analysis: TenderAnalysis | null) => void;
  clearError: () => void;
  reset: () => void;
}

const TenderContext = createContext<TenderContextType | undefined>(undefined);

export function TenderProvider({ children }: { children: React.ReactNode }) {
  const { user } = useDashboard();

  const [state, setState] = useState<TenderState>(() => {
    const stored = getStoredState();
    return {
      ...initialState,
      selectedAnalysis: stored?.selectedAnalysisId
        ? { _id: stored.selectedAnalysisId } as TenderAnalysis
        : null,
      selectedResult: stored?.selectedResultId
        ? { _id: stored.selectedResultId } as TenderAnalysisResult
        : null,
    };
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedState: StoredState = {
        selectedAnalysisId: state.selectedAnalysis?._id || null,
        selectedResultId: state.selectedResult?._id || null,
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(storedState));
      } catch (e) {
        console.warn('Failed to save to localStorage:', e);
      }
    }
  }, [state.selectedAnalysis?._id, state.selectedResult?._id]);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  };

  const handleError = (error: any) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    setError(message);
    setIsLoading(false);
  };

  const fetchAnalyses = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${serverUrl}/tender-analysis`, {
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to fetch analyses');
      const data = await response.json();
      setState(prev => ({ ...prev, analyses: data }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchAnalysisById = useCallback(async (id: string) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${serverUrl}/tender-analysis/${id}`, {
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to fetch analysis');
      const data = await response.json();
      setState(prev => ({ ...prev, selectedAnalysis: data }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createAnalysis = useCallback(async (analysisData: {
      name: string;
      company_description: string;
      search_phrase: string;
      sources: string[];
      criteria: AnalysisCriteria[];
    }) => {
      try {
        setIsLoading(true);
        const response = await fetch(`${serverUrl}/tender-analysis`, {
        method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(analysisData),
        });
      if (!response.ok) throw new Error('Failed to create analysis');
        const data = await response.json();
      setState(prev => ({
          ...prev,
          analyses: [...prev.analyses, data],
          selectedAnalysis: data,
        }));
      } catch (err) {
        handleError(err);
      } finally {
        setIsLoading(false);
      }
  }, []);

  const updateAnalysis = useCallback(async (id: string, data: Partial<TenderAnalysis>) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${serverUrl}/tender-analysis/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to update analysis');
      const updatedAnalysis = await response.json();
      setState(prev => ({
        ...prev,
        analyses: prev.analyses.map(analysis =>
          analysis._id === id ? updatedAnalysis : analysis
        ),
        selectedAnalysis: prev.selectedAnalysis?._id === id ? updatedAnalysis : prev.selectedAnalysis,
      }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);
      /**
     * Assign a new list of users to an analysis.
     * This will update both the sidebar list and whatever
     * analysis is currently open in the drawer.
     */
    const assignUsers = useCallback(
      async (id: string, newUserIds: string[]) => {
        setIsLoading(true);
        try {
          const resp = await fetch(`${serverUrl}/tender-analysis/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ assigned_users: newUserIds }),
          });
          if (!resp.ok) throw new Error('Failed to assign users');
          const updated = await resp.json() as TenderAnalysis;
          // use the existing helper to keep everything in sync
          await updateAnalysis(id, { assigned_users: updated.assigned_users });
        } catch (err) {
          handleError(err);
          throw err;
        } finally {
          setIsLoading(false);
        }
      },
      [updateAnalysis]
    );


  const deleteAnalysis = useCallback(async (id: string) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${serverUrl}/tender-analysis/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to delete analysis');
      setState(prev => ({
        ...prev,
        analyses: prev.analyses.filter(analysis => analysis._id !== id),
        selectedAnalysis: prev.selectedAnalysis?._id === id ? null : prev.selectedAnalysis,
        results: prev.selectedAnalysis?._id === id ? [] : prev.results,
        selectedResult: prev.selectedAnalysis?._id === id ? null : prev.selectedResult,
      }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * This is your existing "paginated" fetch logic, used by TendersList.
   */
  const fetchResults = useCallback(
    async (analysisId: string, page: number = 1, limit: number = 10) => {
      try {
        setIsLoading(true);

        const orgIdParam =
          user?.org_id && user.org_id.trim()
            ? `&org_id=${encodeURIComponent(user.org_id)}`
            : "";

        const response = await fetch(
          `${serverUrl}/tender-analysis/${analysisId}/results?page=${page}&limit=${limit}${orgIdParam}&include_criteria_for_filtering=true`,
          {
            headers: getAuthHeaders(),
          }
        );

        if (!response.ok) throw new Error("Failed to fetch results");
        const { results, total } = await response.json();
        setState((prev) => ({
          ...prev,
          results,
          totalResults: total,
        }));
      } catch (err) {
        handleError(err);
      } finally {
        setIsLoading(false);
      }
    },
    [user?.org_id]
  );

  const deleteTenderResult = useCallback(async (resultId: string) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${serverUrl}/tender-result/${resultId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to delete tender result');
      setState(prev => ({
        ...prev,
        results: prev.results.filter((r) => r._id !== resultId),
        selectedResult:
          prev.selectedResult?._id === resultId ? null : prev.selectedResult,
        totalResults: prev.totalResults - 1,
      }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const markAsOpened = useCallback(async (resultId: string) => {
    try {
      const response = await fetch(`${serverUrl}/tender-result/${resultId}/mark_opened`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        throw new Error(`API call failed with status ${response.status}`);
      }
      const data = await response.json();
      
      // Update the local state with the actual opened_at timestamp from backend
      setState(prev => {
        const updatedResults = prev.results.map(r =>
          r._id === resultId ? { ...r, opened_at: data.opened_at } : r
        );
        const updatedSelectedResult = prev.selectedResult?._id === resultId
          ? { ...prev.selectedResult, opened_at: data.opened_at }
          : prev.selectedResult;
        return {
          ...prev,
          results: updatedResults,
          selectedResult: updatedSelectedResult,
        };
      });
      
      return data;
    } catch (err) {
      console.error('Error marking as opened:', err);
      throw err;
    }
  }, []);

  const markAsUnopened = useCallback(async (resultId: string) => {
    try {
      const response = await fetch(`${serverUrl}/tender-result/${resultId}/mark_unopened`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        throw new Error(`API call failed with status ${response.status}`);
      }
      const data = await response.json();
      
      // Update the local state to remove opened_at
      setState(prev => {
        const updatedResults = prev.results.map(r =>
          r._id === resultId ? { ...r, opened_at: "" } : r
        );
        const updatedSelectedResult = prev.selectedResult?._id === resultId
          ? { ...prev.selectedResult, opened_at: "" }
          : prev.selectedResult;
        return {
          ...prev,
          results: updatedResults,
          selectedResult: updatedSelectedResult,
        };
      });
      
      return data;
    } catch (err) {
      console.error('Error marking as unopened:', err);
      throw err;
    }
  }, []);
  
  const updateTenderStatus = useCallback(async (resultId: string, status: 'inactive' | 'active' | 'archived' | 'inBoard') => {
    try {
      setIsLoading(true);
      const token = localStorage.getItem('token');
      if (!token) throw new Error('Authentication token not found');
      await fetch(`${serverUrl}/tender-result/${resultId}/update_status?status=${status}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      setState(prev => {
        const updatedResults = prev.results.map(r =>
          r._id === resultId ? { ...r, status } : r
        );
        const updatedSelectedResult = prev.selectedResult?._id === resultId
            ? { ...prev.selectedResult, status }
            : prev.selectedResult;
        return {
          ...prev,
          results: updatedResults,
          selectedResult: updatedSelectedResult,
        };
      });
    } catch (err) {
      handleError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchAllActiveTenders = useCallback(async () => {
    if (!state.selectedAnalysis || !state.selectedAnalysis._id) return;
    try {
      setIsLoading(true);
      const response = await fetch(
        `${serverUrl}/tender-analysis/${state.selectedAnalysis._id}/active-results`,
        { headers: getAuthHeaders() }
      );
      if (!response.ok) throw new Error('Failed to fetch active tenders');
      const data = await response.json();
      setState(prev => ({ ...prev, activeTenders: data }));
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  }, [state.selectedAnalysis?._id]);

  // -------------------------------------------------------------------------
  // NEW: Non-paginated endpoint for "all results" – does not overwrite state
  // -------------------------------------------------------------------------
  const fetchAllResultsForAnalysis = useCallback(async (analysisId: string) => {
    // This function returns ALL results from a new endpoint (if you have one),
    // so you can do local filtering/search across the entire data set.
    // Note: We do not store these "all results" in the context state,
    // to avoid conflicts with your existing paginated logic.
    try {
      setIsLoading(true);
      const orgIdParam =
        user?.org_id && user.org_id.trim()
          ? `?org_id=${encodeURIComponent(user.org_id)}`
          : "";

      // Adjust the route to match your actual "all results" endpoint
      // e.g. GET /tender-analysis/<analysis_id>/results/all
      // Include criteria for filtering to enable client-side filtering
      const separator = orgIdParam ? '&' : '?';
      const resp = await fetch(
        `${serverUrl}/tender-analysis/${analysisId}/results/all${orgIdParam}${separator}include_criteria_for_filtering=true`,
        {
          headers: getAuthHeaders(),
        }
      );
      if (!resp.ok) throw new Error("Failed to fetch all results");
      const data = await resp.json();
      // Return them so your component can store them locally
      return data as TenderAnalysisResult[];
    } catch (err) {
      handleError(err);
      return [];
    } finally {
      setIsLoading(false);
    }
  }, [user?.org_id]);

  const setSelectedAnalysis = useCallback((analysis: TenderAnalysis | null) => {
    setState(prev => {
      if (prev.selectedAnalysis?._id === analysis?._id) return prev;
      return { ...prev, selectedAnalysis: analysis };
    });
  }, []);

  const setSelectedResult = useCallback((result: TenderAnalysisResult | null) => {
    setState(prev => ({ ...prev, selectedResult: result }));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const reset = useCallback(() => {
    setState(initialState);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Fetch a single tender result with full details
  const fetchTenderResultById = useCallback(async (resultId: string): Promise<TenderAnalysisResult | null> => {
    try {
      console.log(`[TenderContext] Fetching tender result by ID: ${resultId}`);
      // Don't set global loading state to avoid UI flicker
      const token = localStorage.getItem('token');
      if (!token) {
        console.error('[TenderContext] No auth token found');
        return null;
      }

      console.time(`[TenderContext] API call for ${resultId}`);
      console.log(`[TenderContext] Making request to: ${serverUrl}/tender-result/${resultId}`);
      
      const response = await fetch(`${serverUrl}/tender-result/${resultId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      console.timeEnd(`[TenderContext] API call for ${resultId}`);
      console.log(`[TenderContext] Response status: ${response.status}`);
      
      if (!response.ok) {
        console.error(`[TenderContext] Error fetching tender result: ${response.status}`);
        return null;
      }
      
      console.time(`[TenderContext] JSON parsing for ${resultId}`);
      const data = await response.json();
      console.timeEnd(`[TenderContext] JSON parsing for ${resultId}`);
      
      console.log(`[TenderContext] Data received:`, {
        id: data._id,
        hasCriteria: !!data.criteria_analysis && Array.isArray(data.criteria_analysis),
        criteriaCount: data.criteria_analysis?.length || 0,
        hasDescription: !!data.tender_description
      });
      
      // Update the selected result in context if it matches
      setState(prev => {
        // Update the results array too if this result exists in it
        const updatedResults = prev.results.map(r => 
          r._id === resultId ? { ...r, ...data } : r
        );
        
        // Update the selected result if it's the one we just fetched
        const updatedSelectedResult = prev.selectedResult?._id === resultId
          ? { ...data }
          : prev.selectedResult;
          
        return {
          ...prev,
          results: updatedResults,
          selectedResult: updatedSelectedResult,
        };
      });
      
      return data;
    } catch (err) {
      console.error('[TenderContext] Error fetching tender result:', err);
      return null;
    }
  }, []);

  // Fetch full analysis data if we only have the ID from storage
  useEffect(() => {
    if (state.selectedAnalysis?._id && !state.selectedAnalysis?.name) {
      fetchAnalysisById(state.selectedAnalysis._id);
    }
  }, [state.selectedAnalysis?._id, fetchAnalysisById]);

  const value: TenderContextType = {
    analyses: state.analyses,
    selectedAnalysis: state.selectedAnalysis,
    results: state.results,
    selectedResult: state.selectedResult,
    totalResults: state.totalResults,
    activeTenders: state.activeTenders,
    isLoading,
    error,

    createAnalysis,
    updateAnalysis,
    assignUsers,
    deleteAnalysis,
    fetchAnalyses,
    fetchAnalysisById,
    fetchResults,
    deleteTenderResult,
    markAsOpened,//here is
    markAsUnopened,//here is
    updateTenderStatus,
    fetchAllActiveTenders,
    fetchTenderResultById,

    fetchAllResultsForAnalysis,

    setSelectedAnalysis,
    setSelectedResult,
    clearError,
    reset,
  };

  return <TenderContext.Provider value={value}>{children}</TenderContext.Provider>;
}

export function useTender() {
  const context = useContext(TenderContext);
  if (!context) {
    throw new Error("useTender must be used within a TenderProvider");
  }
  return context;
}
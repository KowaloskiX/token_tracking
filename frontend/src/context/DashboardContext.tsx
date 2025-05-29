"use client"
import React, { createContext, useState, useCallback, useEffect } from 'react';
import { User, Assistant, Conversation, DashboardState, Organization } from '../types';

const STORAGE_KEY = 'dashboard_state';


export const getStoredState = (): DashboardState | null => {
  if (typeof window === 'undefined') return null;
  
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch (error) {
    console.error('Error parsing stored dashboard state:', error);
    return null;
  }
};

interface DashboardContextType extends DashboardState {
  setUser: (user: User | null) => void;
  setOrganization: (organization: Organization | null) => void;
  setCurrentAssistant: (assistant: Assistant | null) => void;
  setCurrentConversation: (conversation: Conversation | null) => void;
  setConversationLoading: (loading: boolean) => void;
  setAssistants: (assistants: Assistant[]) => void;
  reset: () => void;
}

export const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

const initialState: DashboardState = {
  user: null,
  organization: null,
  currentAssistant: null,
  currentConversation: null,
  conversationLoading: false,
  assistants: [],
};

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  // Initialize state from localStorage or fall back to initial state
  const [state, setState] = useState<DashboardState>(() => {
    const stored = getStoredState();
    return stored || initialState;
  });

  // Persist state changes to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  }, [state]);

  const setUser = useCallback((user: User | null) => {
    setState(prev => ({ ...prev, user }));
  }, []);

  const setOrganization = useCallback((organization: Organization | null) => {
    setState(prev => ({ ...prev, organization }));
  }, []);

  const setCurrentAssistant = useCallback((assistant: Assistant | null) => {
    setState(prev => ({ ...prev, currentAssistant: assistant }));
  }, []);

  const setCurrentConversation = useCallback((conversation: Conversation | null) => {
    setState(prev => ({ ...prev, currentConversation: conversation }));
  }, []);

  const setConversationLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, conversationLoading: loading }));
  }, []);

  // New assistants management functions
  const setAssistants = useCallback((assistants: Assistant[]) => {
    setState(prev => ({ ...prev, assistants }));
  }, []);

  const reset = useCallback(() => {
    setState(initialState);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return (
    <DashboardContext.Provider
      value={{
        ...state,
        setUser,
        setOrganization,
        setCurrentAssistant,
        setCurrentConversation,
        setConversationLoading,
        setAssistants,
        reset,
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
}

// Custom hook for using the dashboard context with type safety
export function useDashboard() {
  const context = React.useContext(DashboardContext);
  if (context === undefined) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
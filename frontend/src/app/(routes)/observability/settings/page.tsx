"use client"
import { useState, useEffect } from 'react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useDashboard } from '@/context/DashboardContext';
import { SettingsForm } from '@/components/observability/SettingsForm';
import { useToast } from '@/hooks/use-toast';

export default function SettingsPage() {
  const { toast } = useToast();
  const { user } = useDashboard(); // Layout handles auth
  
  // Settings state
  const [baseUrl, setBaseUrl] = useState(process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000');
  const [authToken, setAuthToken] = useState('');

  // Load settings from localStorage
  useEffect(() => {
    const savedUrl = localStorage.getItem('observability-base-url');
    const savedToken = localStorage.getItem('observability-auth-token');
    const mainToken = localStorage.getItem('token');
    
    if (savedUrl) setBaseUrl(savedUrl);
    
    if (user && mainToken && !savedToken) {
      setAuthToken(mainToken);
    } else if (savedToken) {
      setAuthToken(savedToken);
    }
  }, [user]);

  const saveSettings = () => {
    localStorage.setItem('observability-base-url', baseUrl);
    localStorage.setItem('observability-auth-token', authToken);
    toast({
      title: "Settings saved",
      description: "Configuration has been saved to local storage"
    });
  };

  return (
    <TooltipProvider>
      <SettingsForm
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        authToken={authToken}
        setAuthToken={setAuthToken}
        onSave={saveSettings}
      />
    </TooltipProvider>
  );
}
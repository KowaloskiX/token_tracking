"use client"
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useDashboard } from '@/context/DashboardContext';
import { SingleTenderForm } from '@/components/observability/SingleTenderForm';
import { SingleTenderResults } from '@/components/observability/SingleTenderResults';
import { useToast } from '@/hooks/use-toast';
import { 
  HistoryItem, 
  SingleTenderAnalysisRequest,
  SingleTenderAnalysisResponse 
} from '@/types/observability';
import { ComparisonService } from '@/utils/comparisonService';

const LoadingSpinner = () => (
  <div className="flex h-screen items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
  </div>
);

export default function AnalyzeSingleTenderPage() {
  const { toast } = useToast();
  const { user } = useDashboard(); // Layout handles auth
  
  // Form state
  const [tenderUrl, setTenderUrl] = useState('');
  const [analysisId, setAnalysisId] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SingleTenderAnalysisResponse | null>(null);
  
  // History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  
  // Settings state
  const [baseUrl, setBaseUrl] = useState(process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000');
  const [authToken, setAuthToken] = useState('');

  // Load settings from localStorage and auto-set auth token if user is logged in
  useEffect(() => {
    const savedUrl = localStorage.getItem('observability-base-url');
    const savedToken = localStorage.getItem('observability-auth-token');
    const mainToken = localStorage.getItem('token');
    
    if (savedUrl) setBaseUrl(savedUrl);
    
    // Auto-use main app token if user is logged in and no observability-specific token is set
    if (user && mainToken && !savedToken) {
      setAuthToken(mainToken);
    } else if (savedToken) {
      setAuthToken(savedToken);
    }
  }, [user]);

  // Load history from localStorage
  useEffect(() => {
    const savedHistory = localStorage.getItem('observability-history');
    if (savedHistory) {
      try {
        setHistory(JSON.parse(savedHistory));
      } catch (error) {
        console.error('Error loading history:', error);
      }
    }
  }, []);

  // Load last analysis result from history on page load
  useEffect(() => {
    if (history.length > 0) {
      const lastAnalysisOperation = ComparisonService.findLastOperation('analyze-single-tender', history);
      if (lastAnalysisOperation && lastAnalysisOperation.results) {
        setResults(lastAnalysisOperation.results as SingleTenderAnalysisResponse);
      }
    }
  }, [history]);

  const runAnalysis = async () => {
    if (!tenderUrl.trim()) {
      toast({
        title: "Error",
        description: "Tender URL is required",
        variant: "destructive"
      });
      return;
    }

    if (!analysisId.trim()) {
      toast({
        title: "Error", 
        description: "Browser ID is required",
        variant: "destructive"
      });
      return;
    }

    setLoading(true);
    try {
      const requestBody: SingleTenderAnalysisRequest = {
        tender_url: tenderUrl,
        analysis_id: analysisId
      };

      const response = await fetch(`${baseUrl}/analyze-single-tender`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data: SingleTenderAnalysisResponse = await response.json();
      setResults(data);

      // Add to history with the analysis result ID
      const historyItem: HistoryItem = {
        id: data.result?._id || `analysis-${Date.now()}`,
        timestamp: new Date().toISOString(),
        endpoint: 'analyze-single-tender',
        status: 'success',
        params: requestBody,
        results: data
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));

      toast({
        title: "Analysis completed",
        description: "Single tender analysis completed successfully"
      });
    } catch (error) {
      console.error('Analysis error:', error);
      
      // Add error to history
      const historyItem: HistoryItem = {
        id: `error-${Date.now()}`,
        timestamp: new Date().toISOString(),
        endpoint: 'analyze-single-tender',
        status: 'error',
        params: { error: error instanceof Error ? error.message : 'Unknown error' }
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));

      toast({
        title: "Analysis failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied",
      description: "Text has been copied to clipboard"
    });
  };

  return (
    <TooltipProvider>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <SingleTenderForm
          tenderUrl={tenderUrl}
          setTenderUrl={setTenderUrl}
          analysisId={analysisId}
          setAnalysisId={setAnalysisId}
          loading={loading}
          onRunAnalysis={runAnalysis}
        />
        <SingleTenderResults
          results={results}
          onCopyText={copyToClipboard}
        />
      </div>
    </TooltipProvider>
  );
}
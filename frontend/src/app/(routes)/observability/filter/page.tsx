"use client"
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useDashboard } from '@/context/DashboardContext';
import { FilterForm } from '@/components/observability/FilterForm';
import { ResultsContainer } from '@/components/observability/ResultsContainer';
import { useToast } from '@/hooks/use-toast';
import { exportToCsv } from '@/utils/csvExporter'; // ✅ Import the proper utility
import { 
  SearchResult, 
  FilterResponse, 
  HistoryItem, 
  ComparisonData, 
  ComparisonOperation 
} from '@/types/observability';
import { ComparisonService } from '@/utils/comparisonService';

const LoadingSpinner = () => (
  <div className="flex h-screen items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
  </div>
);

export default function FilteringPage() {
  const { toast } = useToast();
  const { user, setUser } = useDashboard();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  
  // Filter form state - COMPLETELY SEPARATE
  const [filterAnalysisId, setFilterAnalysisId] = useState('');
  const [filterSearchId, setFilterSearchId] = useState('');
  const [filterCompanyDescription, setFilterCompanyDescription] = useState('');
  const [filterSearchPhrase, setFilterSearchPhrase] = useState('');
  const [filterId, setFilterId] = useState('');
  const [aiBatchSize, setAiBatchSize] = useState(20);
  const [filterSaveResults, setFilterSaveResults] = useState(true);
  const [filterTenderIdsToCompare, setFilterTenderIdsToCompare] = useState<string[]>([]);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filterResults, setFilterResults] = useState<FilterResponse | null>(null);
  
  // History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  
  // Settings state
  const [baseUrl, setBaseUrl] = useState(process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000');
  const [authToken, setAuthToken] = useState('');

  // Comparison state
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [comparisonOperation, setComparisonOperation] = useState<ComparisonOperation | null>(null);

  // Check for existing authentication (but don't require it)
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          setIsCheckingAuth(false);
          return;
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          localStorage.removeItem("token");
          console.log("Invalid token found, cleaned up");
        } else {
          const userData = await response.json();
          setUser(userData);
          console.log("User authenticated:", userData.name);
        }

      } catch (error) {
        console.error("Error checking authentication:", error);
        localStorage.removeItem("token");
      } finally {
        setIsCheckingAuth(false);
      }
    };

    checkAuth();
  }, [setUser]);

  // Load settings from localStorage and auto-set auth token if user is logged in
  useEffect(() => {
    if (!isCheckingAuth) {
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
    }
  }, [isCheckingAuth, user]);

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

  // Load last filter result from history on page load
  useEffect(() => {
    if (history.length > 0) {
      const lastFilterOperation = ComparisonService.findLastOperation('filter', history);
      if (lastFilterOperation && lastFilterOperation.results && 'total_filtered' in lastFilterOperation.results) {
        setFilterResults(lastFilterOperation.results as FilterResponse);

        // Check if there's a previous operation to compare with
        const previousFilterOperation = ComparisonService.findPreviousOperation(
          lastFilterOperation.id, 
          'filter', 
          history
        );

        if (previousFilterOperation && previousFilterOperation.results) {
          // Type guard to ensure we're comparing compatible result types
          if ('total_filtered' in previousFilterOperation.results) {
            const comparisonResults = ComparisonService.compareResults(
              lastFilterOperation.results as FilterResponse, 
              previousFilterOperation.results as FilterResponse
            );
            setComparisonData(comparisonResults);
            setComparisonOperation({
              id: previousFilterOperation.id,
              timestamp: previousFilterOperation.timestamp
            });
          } else {
            // Previous operation is not a filter result, so clear comparison
            setComparisonData(null);
            setComparisonOperation(null);
          }
        } else {
          // Clear comparison if no previous filter found
          setComparisonData(null);
          setComparisonOperation(null);
        }
      }
    }
  }, [history]);

  const runFilter = async () => {
    const hasFilterId = filterId.trim();
    const hasBrowserId = filterAnalysisId.trim();
    const hasValidManualInput = filterSearchId.trim() && filterCompanyDescription.trim() && filterSearchPhrase.trim();
    const hasSearchId = filterSearchId.trim();
    
    // If Filter ID is provided, retrieve saved results instead of filtering
    if (hasFilterId) {
      setFilterLoading(true);
      try {
        // First, get the filter results (contains IDs and counts)
        const response = await fetch(`${baseUrl}/tender-filter/${filterId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        
        // If we have a search_id, also fetch the original search results to get full tender details
        let filteredTenders: SearchResult[] = [];
        if (data.search_id && data.filtered_tenders_ids && data.filtered_tenders_ids.length > 0) {
          try {
            const searchResponse = await fetch(`${baseUrl}/tender-search/${data.search_id}`, {
              headers: {
                'Authorization': `Bearer ${authToken}`
              }
            });
            
            if (searchResponse.ok) {
              const searchData = await searchResponse.json();
              const filteredIds = new Set(data.filtered_tenders_ids);
              
              // Filter the original search results to only include the filtered tender IDs
              filteredTenders = searchData.matches?.filter((tender: SearchResult) => 
                filteredIds.has(tender.id)
              ) || [];
            }
          } catch (searchError) {
            console.warn('Could not fetch original search results for tender details:', searchError);
            // Continue without full tender details
          }
        }
        
        // Transform the response to match FilterResponse interface
        const transformedData: FilterResponse = {
          initial_ai_filter_id: data.initial_ai_filter_id,
          search_id: data.search_id || '',
          total_filtered: data.filtered_tenders_count || 0,
          total_filtered_out: data.filtered_out_count || 0,
          filtered_tenders: filteredTenders
        };

        setFilterResults(transformedData);

        // Check for last filter operation BEFORE adding to history
        const lastFilterOperation = ComparisonService.findLastOperation('filter', history);

        if (lastFilterOperation && lastFilterOperation.results) {
          // Type guard to ensure we're comparing compatible result types
          if ('total_filtered' in lastFilterOperation.results) {
            const comparisonResults = ComparisonService.compareResults(transformedData, lastFilterOperation.results as FilterResponse);
            setComparisonData(comparisonResults);
            setComparisonOperation({
              id: lastFilterOperation.id,
              timestamp: lastFilterOperation.timestamp
            });
          } else {
            // Previous operation is not a filter result, so clear comparison
            setComparisonData(null);
            setComparisonOperation(null);
          }
        } else {
          // Clear comparison if no previous filter found
          setComparisonData(null);
          setComparisonOperation(null);
        }

        // Add to history - USING NEW LIMITED SAVE METHOD
        const historyItem: HistoryItem = {
          id: data.initial_ai_filter_id,
          timestamp: new Date().toISOString(),
          endpoint: 'filter',
          status: 'success',
          params: { filter_id: filterId }, // ✅ Use the actual filter ID that was retrieved
          results: transformedData // ✅ Use transformedData instead of raw data
        };
        const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
        setHistory(newHistory);
        localStorage.setItem('observability-history', JSON.stringify(newHistory));

        toast({
          title: "Filter results retrieved",
          description: `Loaded saved filter results: ${data.filtered_tenders_count} kept, ${data.filtered_out_count} filtered out${filteredTenders.length > 0 ? ` (${filteredTenders.length} details loaded)` : ''}`
        });
        return;
      } catch (error) {
        console.error('Retrieve filter error:', error);
        
        // Clear comparison on error
        setComparisonData(null);
        setComparisonOperation(null);
        
        // Add error to history
        const historyItem: HistoryItem = {
          id: `error-${Date.now()}`,
          timestamp: new Date().toISOString(),
          endpoint: 'filter',
          status: 'error',
          params: { error: error instanceof Error ? error.message : 'Unknown error' }
        };
        const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
        setHistory(newHistory);
        localStorage.setItem('observability-history', JSON.stringify(newHistory));

        toast({
          title: "Failed to retrieve filter results",
          description: error instanceof Error ? error.message : "Unknown error",
          variant: "destructive"
        });
        return;
      } finally {
        setFilterLoading(false);
      }
    }

    // Both options now require search_id
    if (!hasSearchId) {
      toast({
        title: "Error",
        description: "Search Results ID is required for both options",
        variant: "destructive"
      });
      return;
    }

    if (!hasBrowserId && !hasValidManualInput && !hasFilterId) {
      toast({
        title: "Error",
        description: "Please provide either Browser Configuration ID, Manual Configuration, OR Filter Results ID",
        variant: "destructive"
      });
      return;
    }

    setFilterLoading(true);
    try {
      const requestBody: any = {
        search_id: filterSearchId,
        ai_batch_size: aiBatchSize,
        save_results: filterSaveResults
      };

      if (filterTenderIdsToCompare.length > 0) {
        requestBody.tender_ids_to_compare = filterTenderIdsToCompare;
      }

      if (hasBrowserId) {
        requestBody.analysis_id = filterAnalysisId;
      } else {
        requestBody.company_description = filterCompanyDescription;
        requestBody.search_phrase = filterSearchPhrase;
      }

      const response = await fetch(`${baseUrl}/test-tender-filter`, {
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

      const data: FilterResponse = await response.json();
      setFilterResults(data);

      // Check for last filter operation BEFORE adding to history
      const lastFilterOperation = ComparisonService.findLastOperation('filter', history);

      if (lastFilterOperation && lastFilterOperation.results) {
        // Type guard to ensure we're comparing compatible result types
        if ('total_filtered' in lastFilterOperation.results) {
          const comparisonResults = ComparisonService.compareResults(data, lastFilterOperation.results as FilterResponse);
          setComparisonData(comparisonResults);
          setComparisonOperation({
            id: lastFilterOperation.id,
            timestamp: lastFilterOperation.timestamp
          });
        } else {
          // Previous operation is not a filter result, so clear comparison
          setComparisonData(null);
          setComparisonOperation(null);
        }
      } else {
        // Clear comparison if no previous filter found
        setComparisonData(null);
        setComparisonOperation(null);
      }

      // Add to history - USING NEW LIMITED SAVE METHOD
      const historyItem: HistoryItem = {
        id: data.initial_ai_filter_id,
        timestamp: new Date().toISOString(),
        endpoint: 'filter',
        status: 'success',
        params: requestBody,
        results: data
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));

      toast({
        title: "Filtering completed",
        description: `Kept ${data.total_filtered}, filtered out ${data.total_filtered_out}`
      });
    } catch (error) {
      console.error('Filter error:', error);
      
      // Clear comparison on error
      setComparisonData(null);
      setComparisonOperation(null);
      
      // Add error to history
      const historyItem: HistoryItem = {
        id: `error-${Date.now()}`,
        timestamp: new Date().toISOString(),
        endpoint: 'filter',
        status: 'error',
        params: { error: error instanceof Error ? error.message : 'Unknown error' }
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));

      toast({
        title: "Filtering failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
    } finally {
      setFilterLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied",
      description: "ID has been copied to clipboard"
    });
  };

  // ✅ Replace the old exportToCsv function with this:
  const handleExportCsv = (data: SearchResult[], filename: string) => {
    // Transform the data to handle nested objects and arrays properly
    const transformedData = data.map(item => ({
      id: item.id,
      name: item.name || '',
      organization: item.organization || '',
      location: item.location || '',
      source: item.source || '',
      similarity_score: item.score || 0,
      // Handle any additional fields from SearchResult
      ...Object.fromEntries(
        Object.entries(item).filter(([key]) =>
          !['id', 'name', 'organization', 'location', 'source', 'similarity_score'].includes(key)
        )
      )
    }));

    exportToCsv(transformedData, filename);
  };

  // Don't show anything while checking auth
  if (isCheckingAuth) {
    return <LoadingSpinner />;
  }

  return (
    <TooltipProvider>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <FilterForm
          analysisId={filterAnalysisId}
          setAnalysisId={setFilterAnalysisId}
          searchId={filterSearchId}
          setSearchId={setFilterSearchId}
          companyDescription={filterCompanyDescription}
          setCompanyDescription={setFilterCompanyDescription}
          searchPhrase={filterSearchPhrase}
          setSearchPhrase={setFilterSearchPhrase}
          filterId={filterId}
          setFilterId={setFilterId}
          aiBatchSize={aiBatchSize}
          setAiBatchSize={setAiBatchSize}
          saveResults={filterSaveResults}
          setSaveResults={setFilterSaveResults}
          tenderIdsToCompare={filterTenderIdsToCompare}
          setTenderIdsToCompare={setFilterTenderIdsToCompare}
          filterLoading={filterLoading}
          onRunFilter={runFilter}
          searchResults={null}
        />
        <ResultsContainer
          type="filter"
          filterResults={filterResults}
          onCopyId={copyToClipboard}
          onExportCsv={handleExportCsv} // ✅ Use the new function
          comparison={comparisonData || undefined}
          comparisonOperation={comparisonOperation || undefined}
        />
      </div>
    </TooltipProvider>
  );
}
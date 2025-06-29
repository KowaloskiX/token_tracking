"use client"
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useDashboard } from '@/context/DashboardContext';
import { useObservability } from '@/hooks/useObservability';
import { SearchForm, FilterCondition } from '@/components/observability/SearchForm';
import { ResultsContainer } from '@/components/observability/ResultsContainer';
import { useToast } from '@/hooks/use-toast';
import { exportToCsv } from '@/utils/csvExporter'; // ✅ Import the proper utility
import type { 
  SearchResponse, 
  SearchResult, 
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

export default function SearchPage() {
  const { toast } = useToast();
  const { user, setUser } = useDashboard();
  const { runSearch, getSearch, loading: searchLoading } = useObservability();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  
  // Search form state
  const [searchAnalysisId, setSearchAnalysisId] = useState('');
  const [searchSearchId, setSearchSearchId] = useState('');
  const [searchPhrase, setSearchPhrase] = useState('');
  const [companyDescription, setCompanyDescription] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [topK, setTopK] = useState(30);
  const [saveResults, setSaveResults] = useState(true);
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [scoreThreshold, setScoreThreshold] = useState([0.5]);
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-3-large');
  const [tenderNamesIndex, setTenderNamesIndex] = useState('tenders');
  const [elasticsearchIndex, setElasticsearchIndex] = useState('tenders');
  const [filterConditions, setFilterConditions] = useState<FilterCondition[]>([]);
  const [tenderIdsToCompare, setTenderIdsToCompare] = useState<string[]>([]);
  
  // History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  
  // Settings state
  const [baseUrl, setBaseUrl] = useState(process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000');
  const [authToken, setAuthToken] = useState('');
  
  // Capture search parameters at time of search execution
  const [searchExecutionParams, setSearchExecutionParams] = useState<{sources: string[], scoreThreshold: number} | null>(null);

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

  // Load last search result from history on page load
  useEffect(() => {
    if (history.length > 0) {
      const lastSearchOperation = ComparisonService.findLastOperation('search', history);
      if (lastSearchOperation && lastSearchOperation.results && 'total_matches' in lastSearchOperation.results) {
        setSearchResults(lastSearchOperation.results as SearchResponse);
        
        // Set execution params based on the last operation
        if (lastSearchOperation.params) {
          setSearchExecutionParams({
            sources: lastSearchOperation.params.sources || [],
            scoreThreshold: lastSearchOperation.params.score_threshold || 0.5
          });
        }

        // Check if there's a previous operation to compare with
        const previousSearchOperation = ComparisonService.findPreviousOperation(
          lastSearchOperation.id, 
          'search', 
          history
        );

        if (previousSearchOperation && previousSearchOperation.results) {
          // Type guard to ensure we're comparing compatible result types
          if ('total_matches' in previousSearchOperation.results) {
            const comparisonResults = ComparisonService.compareResults(
              lastSearchOperation.results as SearchResponse, 
              previousSearchOperation.results as SearchResponse
            );
            setComparisonData(comparisonResults);
            setComparisonOperation({
              id: previousSearchOperation.id,
              timestamp: previousSearchOperation.timestamp
            });
          } else {
            // Previous operation is not a search result, so clear comparison
            setComparisonData(null);
            setComparisonOperation(null);
          }
        } else {
          // Clear comparison if no previous search found
          setComparisonData(null);
          setComparisonOperation(null);
        }
      }
    }
  }, [history]);

  const handleRunSearch = async () => {
    const hasBrowserId = searchAnalysisId && searchAnalysisId.trim().length > 0;
    const hasManualInput = (searchPhrase && searchPhrase.trim().length > 0) || (companyDescription && companyDescription.trim().length > 0) || sources.length > 0;
    const hasSearchId = searchSearchId && searchSearchId.trim().length > 0;
    
    if (!hasBrowserId && !hasManualInput && !hasSearchId) {
      toast({
        title: "Error",
        description: "Please provide either a Browser ID, Search ID, or manual search configuration",
        variant: "destructive"
      });
      return;
    }

    // If Search ID is provided, retrieve saved results instead of searching
    if (hasSearchId) {
      try {
        const data = await getSearch(searchSearchId, authToken);
        setSearchResults(data);
        
        // Capture execution params (empty for retrieval)
        setSearchExecutionParams({
          sources: [],
          scoreThreshold: 0.5
        });

        // Check for last search operation BEFORE adding to history
        const lastSearchOperation = ComparisonService.findLastOperation('search', history);

        if (lastSearchOperation && lastSearchOperation.results) {
          // Type guard to ensure we're comparing compatible result types
          if ('total_matches' in lastSearchOperation.results) {
            const comparisonResults = ComparisonService.compareResults(data, lastSearchOperation.results as SearchResponse);
            setComparisonData(comparisonResults);
            setComparisonOperation({
              id: lastSearchOperation.id,
              timestamp: lastSearchOperation.timestamp
            });
          } else {
            // Previous operation is not a search result, so clear comparison
            setComparisonData(null);
            setComparisonOperation(null);
          }
        } else {
          // Clear comparison if no previous search found
          setComparisonData(null);
          setComparisonOperation(null);
        }

        // Add to history
        const historyItem: HistoryItem = {
          id: data.search_id,
          timestamp: new Date().toISOString(),
          endpoint: 'search',
          status: 'success',
          params: { search_id: searchSearchId },
          results: data
        };
        const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
        setHistory(newHistory);
        localStorage.setItem('observability-history', JSON.stringify(newHistory));
        return;
      } catch (error) {
        // Clear comparison on error
        setComparisonData(null);
        setComparisonOperation(null);
        
        // Add error to history
        const historyItem: HistoryItem = {
          id: `error-${Date.now()}`,
          timestamp: new Date().toISOString(),
          endpoint: 'search',
          status: 'error',
          params: { error: error instanceof Error ? error.message : 'Unknown error' }
        };
        const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
        setHistory(newHistory);
        localStorage.setItem('observability-history', JSON.stringify(newHistory));
        return;
      }
    }

    // Prepare search parameters for new search
    const requestBody: any = {
      top_k: topK,
      save_results: saveResults,
      score_threshold: scoreThreshold[0],
      embedding_model: embeddingModel,
      tender_names_index_name: tenderNamesIndex,
      elasticsearch_index_name: elasticsearchIndex
    };

    if (sources.length > 0) {
      requestBody.sources = sources;
    }

    if (filterConditions.length > 0) {
      requestBody.filter_conditions = filterConditions.map(condition => {
        let value = condition.value;
        
        if (condition.op === 'in') {
          value = Array.isArray(value) ? value : [value];
        } else {
          value = Array.isArray(value) ? value[0] : value;
        }
        
        return {
          field: condition.field,
          op: condition.op,
          value: value
        };
      });
    }

    if (hasBrowserId) {
      requestBody.analysis_id = searchAnalysisId;
    }
    
    if (searchPhrase && searchPhrase.trim()) {
      requestBody.search_phrase = searchPhrase;
    }

    if (companyDescription && companyDescription.trim()) {
      requestBody.company_description = companyDescription;
    }

    if (tenderIdsToCompare.length > 0) {
      requestBody.tender_ids_to_compare = tenderIdsToCompare;
    }

    try {
      const data = await runSearch(requestBody, authToken);
      setSearchResults(data);
      
      // Capture execution params
      setSearchExecutionParams({
        sources: sources,
        scoreThreshold: scoreThreshold[0]
      });

      // Check for last search operation BEFORE adding to history
      const lastSearchOperation = ComparisonService.findLastOperation('search', history);

      if (lastSearchOperation && lastSearchOperation.results) {
        // Type guard to ensure we're comparing compatible result types
        if ('total_matches' in lastSearchOperation.results) {
          const comparisonResults = ComparisonService.compareResults(data, lastSearchOperation.results as SearchResponse);
          setComparisonData(comparisonResults);
          setComparisonOperation({
            id: lastSearchOperation.id,
            timestamp: lastSearchOperation.timestamp
          });
        } else {
          // Previous operation is not a search result, so clear comparison
          setComparisonData(null);
          setComparisonOperation(null);
        }
      } else {
        // Clear comparison if no previous search found
        setComparisonData(null);
        setComparisonOperation(null);
      }

      // Add to history - USING NEW LIMITED SAVE METHOD
      const historyItem: HistoryItem = {
        id: data.search_id,
        timestamp: new Date().toISOString(),
        endpoint: 'search',
        status: 'success',
        params: requestBody,
        results: data
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));
    } catch (error) {
      // Clear comparison on error
      setComparisonData(null);
      setComparisonOperation(null);
      
      // Add error to history
      const historyItem: HistoryItem = {
        id: `error-${Date.now()}`,
        timestamp: new Date().toISOString(),
        endpoint: 'search',
        status: 'error',
        params: { error: error instanceof Error ? error.message : 'Unknown error' }
      };
      const newHistory = ComparisonService.saveHistoryWithLimits(historyItem, history);
      setHistory(newHistory);
      localStorage.setItem('observability-history', JSON.stringify(newHistory));
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
        <SearchForm
          searchPhrase={searchPhrase}
          setSearchPhrase={setSearchPhrase}
          companyDescription={companyDescription}
          setCompanyDescription={setCompanyDescription}
          sources={sources}
          setSources={setSources}
          topK={topK}
          setTopK={setTopK}
          saveResults={saveResults}
          setSaveResults={setSaveResults}
          scoreThreshold={scoreThreshold}
          setScoreThreshold={setScoreThreshold}
          embeddingModel={embeddingModel}
          setEmbeddingModel={setEmbeddingModel}
          tenderNamesIndex={tenderNamesIndex}
          setTenderNamesIndex={setTenderNamesIndex}
          elasticsearchIndex={elasticsearchIndex}
          setElasticsearchIndex={setElasticsearchIndex}
          filterConditions={filterConditions}
          setFilterConditions={setFilterConditions}
          searchLoading={searchLoading}
          onRunSearch={handleRunSearch}
          analysisId={searchAnalysisId}
          setAnalysisId={setSearchAnalysisId}
          searchId={searchSearchId}
          setSearchId={setSearchSearchId}
          tenderIdsToCompare={tenderIdsToCompare}
          setTenderIdsToCompare={setTenderIdsToCompare}
        />
        <ResultsContainer
          type="search"
          searchResults={searchResults}
          sources={searchExecutionParams?.sources || []}
          onCopyId={copyToClipboard}
          onExportCsv={handleExportCsv} // ✅ Use the new function
          comparison={comparisonData || undefined}
          comparisonOperation={comparisonOperation || undefined}
        />
      </div>
    </TooltipProvider>
  );
}
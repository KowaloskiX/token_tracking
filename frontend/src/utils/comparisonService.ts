import { 
  SearchResult, 
  SearchResponse, 
  FilterResponse, 
  HistoryItem, 
  ComparisonData
} from '@/types/observability';

export class ComparisonService {
  // Remove duplicate prevention to allow same operation multiple times
  static saveHistoryWithLimits(newItem: HistoryItem, currentHistory: HistoryItem[]): HistoryItem[] {
    // DON'T filter out existing items with same ID - allow duplicates
    // const filteredHistory = currentHistory.filter(item => item.id !== newItem.id); // ❌ Remove this line
    
    // Separate by operation type from current history (not filtered)
    const searchOps = currentHistory.filter(item => item.endpoint === 'search');
    const filterOps = currentHistory.filter(item => item.endpoint === 'filter');
    const analysisOps = currentHistory.filter(item => item.endpoint === 'analyze-single-tender');
    
    if (newItem.endpoint === 'search') {
      // Keep only the most recent search operation (the current one will be the newest)
      const limitedSearchOps = [newItem, ...searchOps.slice(0, 1)];
      return [...limitedSearchOps, ...filterOps.slice(0, 2), ...analysisOps.slice(0, 2)];
    } else if (newItem.endpoint === 'filter') {
      // Keep only the most recent filter operation (the current one will be the newest)
      const limitedFilterOps = [newItem, ...filterOps.slice(0, 1)];
      return [...searchOps.slice(0, 2), ...limitedFilterOps, ...analysisOps.slice(0, 2)];
    } else if (newItem.endpoint === 'analyze-single-tender') {
      // Keep only the most recent 2 analysis operations (the current one will be the newest)
      const limitedAnalysisOps = [newItem, ...analysisOps.slice(0, 1)];
      return [...searchOps.slice(0, 2), ...filterOps.slice(0, 2), ...limitedAnalysisOps];
    }
    
    // Default fallback
    return [newItem, ...currentHistory.slice(0, 5)];
  }

  // Find the last operation of the same type
  static findLastOperation(
    endpoint: 'search' | 'filter' | 'analyze-single-tender', 
    history: HistoryItem[]
  ): HistoryItem | null {
    return history
      .filter(item => 
        item.endpoint === endpoint && 
        item.status === 'success' &&
        item.results
      )[0] || null; // First item is the most recent
  }

  // Find the second-to-last operation (for comparison when displaying last result)
  static findSecondLastOperation(
    endpoint: 'search' | 'filter' | 'analyze-single-tender', 
    history: HistoryItem[]
  ): HistoryItem | null {
    const successfulOps = history
      .filter(item => 
        item.endpoint === endpoint && 
        item.status === 'success' &&
        item.results
      );
    
    return successfulOps[1] || null; // Second item if it exists
  }

  // Find the previous operation relative to a specific operation ID
  static findPreviousOperation(
    currentOperationId: string,
    endpoint: 'search' | 'filter' | 'analyze-single-tender', 
    history: HistoryItem[]
  ): HistoryItem | null {
    const successfulOps = history
      .filter(item => 
        item.endpoint === endpoint && 
        item.status === 'success' &&
        item.results
      );
    
    const currentIndex = successfulOps.findIndex(item => item.id === currentOperationId);
    if (currentIndex === -1 || currentIndex === successfulOps.length - 1) {
      return null; // Operation not found or it's the oldest one
    }
    
    return successfulOps[currentIndex + 1]; // Next item in array (older operation)
  }

  // Keep existing similarity methods for potential future use
  static generateComparisonKey(params: any, endpoint: 'search' | 'filter' | 'analyze-single-tender'): string {
    if (endpoint === 'search') {
      const comparable = {
        search_phrase: params.search_phrase,
        company_description: params.company_description,
        analysis_id: params.analysis_id,
        sources: params.sources?.sort(),
        top_k: params.top_k
      };
      return btoa(JSON.stringify(comparable));
    } else if (endpoint === 'filter') {
      const comparable = {
        search_id: params.search_id,
        analysis_id: params.analysis_id,
        company_description: params.company_description,
        search_phrase: params.search_phrase
      };
      return btoa(JSON.stringify(comparable));
    } else if (endpoint === 'analyze-single-tender') {
      const comparable = {
        tender_url: params.tender_url,
        analysis_id: params.analysis_id
      };
      return btoa(JSON.stringify(comparable));
    }
    return '';
  }

  static calculateSimilarity(params1: any, params2: any, endpoint: 'search' | 'filter' | 'analyze-single-tender'): number {
    if (endpoint === 'search') {
      let score = 0;
      let factors = 0;

      if (params1.analysis_id && params1.analysis_id === params2.analysis_id) return 1.0;
      
      if (params1.search_phrase === params2.search_phrase) {
        score += 0.4;
        factors++;
      }
      if (params1.company_description === params2.company_description) {
        score += 0.3;
        factors++;
      }
      
      const sources1 = params1.sources?.sort() || [];
      const sources2 = params2.sources?.sort() || [];
      if (JSON.stringify(sources1) === JSON.stringify(sources2)) {
        score += 0.2;
        factors++;
      }
      
      if (params1.top_k === params2.top_k) {
        score += 0.1;
        factors++;
      }

      return factors > 0 ? score : 0;
    } else if (endpoint === 'filter') {
      let score = 0;
      if (params1.search_id === params2.search_id) score += 0.5;
      if (params1.analysis_id === params2.analysis_id) score += 0.3;
      if (params1.search_phrase === params2.search_phrase) score += 0.1;
      if (params1.company_description === params2.company_description) score += 0.1;
      
      return score;
    } else if (endpoint === 'analyze-single-tender') {
      let score = 0;
      if (params1.tender_url === params2.tender_url) score += 0.6;
      if (params1.analysis_id === params2.analysis_id) score += 0.4;
      
      return score;
    }
    
    return 0;
  }

  // Compare results between two operations
  static compareResults(current: SearchResponse | FilterResponse, previous: SearchResponse | FilterResponse): ComparisonData {
    let currentResults: SearchResult[] = [];
    let previousResults: SearchResult[] = [];

    if ('total_matches' in current && 'total_matches' in previous) {
      // Search results comparison
      currentResults = current.matches;
      previousResults = previous.matches;
    } else {
      // Filter results comparison
      currentResults = (current as FilterResponse).filtered_tenders;
      previousResults = (previous as FilterResponse).filtered_tenders;
    }

    const currentIds = new Set(currentResults.map(m => m.id));
    const previousIds = new Set(previousResults.map(m => m.id));
    
    const newResults = currentResults.filter(m => !previousIds.has(m.id));
    const removedResults = previousResults.filter(m => !currentIds.has(m.id));
    const commonResults = currentResults.filter(m => previousIds.has(m.id));

    return {
      new: newResults,
      removed: removedResults,
      common: commonResults,
      summary: {
        newCount: newResults.length,
        removedCount: removedResults.length,
        commonCount: commonResults.length
      }
    };
  }
}
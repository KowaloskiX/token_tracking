export interface SearchResult {
  id: string;
  name: string;
  organization: string;
  location: string;
  source: string;
  source_type: string;
  score?: number;
}

export interface SearchResponse {
  search_id: string;
  query: string;
  total_matches: number;
  matches: SearchResult[];
  detailed_results?: Record<string, any>;
}

export interface FilterResponse {
  initial_ai_filter_id: string;
  search_id: string;
  total_filtered: number;
  total_filtered_out: number;
  filtered_tenders: SearchResult[];
  comparison?: ComparisonResult;
}

export interface ComparisonResult {
  total_extra_filtered: number;
  extra_filtered: SearchResult[];
  total_covered: number;
  covered: SearchResult[];
  total_missing: number;
  missing_ids: string[];
}

export interface HistoryItem {
  id: string;
  timestamp: string;
  endpoint: 'search' | 'filter' | 'analyze-single-tender';
  status: 'success' | 'warning' | 'error';
  params: any;
  results?: SearchResponse | FilterResponse | SingleTenderAnalysisResponse;
}

export interface ComparisonData {
  new: SearchResult[];
  removed: SearchResult[];
  common: SearchResult[];
  summary: {
    newCount: number;
    removedCount: number;
    commonCount: number;
  };
}

export interface ComparisonOperation {
  id: string;
  timestamp: string;
}

// Type alias for FilterResult (same as SearchResult but used in filter context)
export type FilterResult = SearchResult;

// Type alias for cleaner component props
export interface ComparisonProps {
  comparison?: ComparisonData;
  comparisonOperation?: ComparisonOperation;
}

export interface SingleTenderAnalysisRequest {
  tender_url: string;
  analysis_id: string;
}

export interface SingleTenderAnalysisResponse {
  status: string;
  result?: TenderAnalysisResult;
  message?: string;
}

export interface TenderLocation {
  country?: string;
  voivodeship?: string;
  city?: string;
}

export interface TenderMetadata {
  name?: string;
  organization?: string;
  location?: string; // Keep this for backward compatibility
  submission_deadline?: string;
  source?: string;
}

export interface CriteriaAnalysis {
  criteria: string;
  exclude_from_score?: boolean; // Add this property
  analysis?: {
    score?: number;
    explanation?: string;
    relevant_content?: string;
    weight?: number;
    criteria_met?: boolean;
    confidence?: string;
    summary?: string;
  };
  citations?: {
    source: string;
    text: string;
    keyword?: string;
  }[];
}

export interface UploadedFile {
  filename: string;
  blob_url?: string;
  url?: string;
  bytes?: number;
  type?: string;
}

export interface TenderAnalysisResult {
  _id: string; // Change from id to _id to match API response
  user_id?: string;
  tender_analysis_id?: string;
  tender_url?: string;
  source?: string; // Add this since it's in the API response
  tender_metadata?: TenderMetadata;
  tender_score?: number;
  tender_description?: string;
  criteria_analysis?: CriteriaAnalysis[];
  uploaded_files?: UploadedFile[];
  location?: TenderLocation;
  created_at?: string;
  updated_at?: string;
}
import { SOURCE_CONFIG } from "@/app/constants/tenders";
import { FileData } from ".";

export interface Citation {
  text: string;
  source?: string;
  keyword?: string;
  file_id?: string;
  sanitized_filename?: string;
}

export interface AnalysisCriteria {
  name: string;
  description: string;
  weight: number;
  is_disqualifying?: boolean;
  exclude_from_score?: boolean;
  instruction?: string;
  subcriteria?: string[];
  keywords?: string;
}

export interface TenderMetadata {
  name: string;
  organization: string;
  submission_deadline?: string;
  initiation_date?: string;
  procedure_type: string;
}

export interface CriteriaAnalysisResult {
  criteria: string;
  analysis: {
    summary: string;
    confidence_level: number;
    weight: number;
    [key: string]: any;
  };
  exclude_from_score?: boolean;
  is_disqualifying?: boolean;
  citations?: Citation[];
}

export interface TenderAnalysisResult {
  
  _id?: string;
  user_id: string;
  tender_analysis_id: string;
  tender_url: string;
  location?: any;
  source?: string;
  tender_score: number;
  tender_metadata: TenderMetadata;
  criteria_analysis: CriteriaAnalysisResult[];
  company_match_explanation: string;
  assistant_id: string;
  updates: any[];
  uploaded_files: FileData[];
  pinecone_config?: {
    index_name: string;
    namespace: string;
    embedding_model: string
  };
  tender_pinecone_id?: string;
  tender_description?: string;
  status: 'inactive' | 'active' | 'archived' | 'inBoard' | 'filtered' | 'external';
  updated_at: string;
  created_at: string;
  opened_at: string;
  order_number: string;
  finished_id?: string;
  external_compare_status?: 'our_unique' | 'overlap_oferent' | 'overlap_bizpol' | 'external_unique';
}

export interface TenderAnalysis {
  _id?: string;
  user_id: string;
  name: string;
  org_id?: string;
  company_description: string;
  search_phrase: string;
  sources?: string[];
  criteria: AnalysisCriteria[];
  filtering_rules?: string;
  last_run?: string;
  created_at: string;
  updated_at: string;
  assigned_users?: string[];
  email_recipients?: string[];
  include_external_sources?: boolean; // NEW: Include external sources in analysis
}

// Request/Response types for API operations
export interface CreateTenderAnalysisDTO {
  name: string;
  company_description: string;
  search_phrase: string;
  criteria: AnalysisCriteria[];
}

export interface UpdateTenderAnalysisDTO {
  name?: string;
  company_description?: string;
  search_phrase?: string;
  criteria?: AnalysisCriteria[];
}

// API Response types
export interface TenderAnalysisResponse {
  data: TenderAnalysis;
  message?: string;
}

export interface TenderAnalysisListResponse {
  data: TenderAnalysis[];
  total: number;
  page: number;
  per_page: number;
}

export interface TenderAnalysisResultsResponse {
  data: TenderAnalysisResult[];
  total: number;
}

export interface DeleteTenderAnalysisResponse {
  message: string;
  deleted_results: number;
}

// Additional utility types
export type TenderAnalysisStatus = 'draft' | 'running' | 'completed' | 'failed';

export interface TenderAnalysisWithStatus extends TenderAnalysis {
  status: TenderAnalysisStatus;
  error?: string;
  progress?: number;
}

// Sorting and filtering types
export interface TenderAnalysisFilters {
  search?: string;
  startDate?: string;
  endDate?: string;
  status?: TenderAnalysisStatus;
}

export interface TenderAnalysisSortOptions {
  field: keyof TenderAnalysis;
  direction: 'asc' | 'desc';
}

// Error types
export interface TenderAnalysisError {
  code: string;
  message: string;
  details?: Record<string, any>;
}



export interface TenderSourceIconProps {
  source?: string;
  url?: string;
}

export interface TenderAnalysisUpdate {
  _id: string;
  tender_analysis_result_id: string;
  updated_files: FileData[];
  update_date: string;
  update_link?: string;
}
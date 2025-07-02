// types/tableColumns.ts

export type ColumnType = 
  | 'source' 
  | 'name' 
  | 'organization' 
  | 'publication_date' 
  | 'deadline_progress' 
  | 'submission_deadline' 
  | 'board_status' 
  | 'score' 
  | 'actions'
  | 'criteria'; // Dynamic criteria columns

export type SortDirection = 'asc' | 'desc' | null;

export interface BaseColumnConfig {
  id: string;
  type: ColumnType;
  key: string; // Data key or identifier
  label: string;
  width: number; // Width in pixels
  minWidth: number;
  maxWidth: number;
  visible: boolean;
  sortable: boolean;
  resizable: boolean;
  order: number; // Display order
}

export interface StandardColumnConfig extends BaseColumnConfig {
  type: Exclude<ColumnType, 'criteria'>;
}

export interface CriteriaColumnConfig extends BaseColumnConfig {
  type: 'criteria';
  criteriaName: string; // The specific criteria this column represents
  criteriaId: string;
}

export type ColumnConfig = StandardColumnConfig | CriteriaColumnConfig;

export interface TableColumnState {
  columns: ColumnConfig[];
  sortConfig: {
    columnId: string;
    direction: SortDirection;
  } | null;
}

export interface TableLayoutState {
  isOpen: boolean;
  draggedColumn: string | null;
  availableCriteria: Array<{
    id: string;
    name: string;
    description?: string;
  }>;
}

// For backend integration
export interface BackendColumnConfig {
  id: string;
  type: string;
  key: string;
  label: string;
  width: number;
  visible: boolean;
  order: number;
  criteria_id?: string; // For criteria columns
  user_id: string;
  analysis_id: string;
  created_at: string;
  updated_at: string;
}

export const DEFAULT_COLUMNS: StandardColumnConfig[] = [
  {
    id: 'source',
    type: 'source',
    key: 'source',
    label: 'Source',
    width: 40,
    minWidth: 30,
    maxWidth: 60,
    visible: true,
    sortable: true, // Enable sorting for source
    resizable: true,
    order: 0,
  },
  {
    id: 'name',
    type: 'name',
    key: 'tender_metadata.name',
    label: 'Order',
    width: 160,
    minWidth: 150,
    maxWidth: 250,
    visible: true,
    sortable: true,
    resizable: true,
    order: 1,
  },
  {
    id: 'organization',
    type: 'organization',
    key: 'tender_metadata.organization',
    label: 'Client',
    width: 150,
    minWidth: 120,
    maxWidth: 200,
    visible: true,
    sortable: true,
    resizable: true,
    order: 2,
  },
  {
    id: 'publication_date',
    type: 'publication_date',
    key: 'tender_metadata.initiation_date',
    label: 'Publication Date',
    width: 80,
    minWidth: 70,
    maxWidth: 120,
    visible: true,
    sortable: true,
    resizable: true,
    order: 3,
  },
  {
    id: 'deadline_progress',
    type: 'deadline_progress',
    key: 'tender_metadata.submission_deadline',
    label: 'Progress',
    width: 80,
    minWidth: 60,
    maxWidth: 120,
    visible: true,
    sortable: false, // Keep progress bar non-sortable as it's visual only
    resizable: true,
    order: 4,
  },
  {
    id: 'submission_deadline',
    type: 'submission_deadline',
    key: 'tender_metadata.submission_deadline',
    label: 'Submission Deadline',
    width: 120,
    minWidth: 100,
    maxWidth: 160,
    visible: true,
    sortable: true,
    resizable: true,
    order: 5,
  },
  {
    id: 'board_status',
    type: 'board_status',
    key: 'status',
    label: 'Board Status',
    width: 100,
    minWidth: 80,
    maxWidth: 140,
    visible: true,
    sortable: true, // Enable sorting for board status
    resizable: true,
    order: 6,
  },
  {
    id: 'score',
    type: 'score',
    key: 'tender_score',
    label: 'Relevance',
    width: 90,
    minWidth: 70,
    maxWidth: 120,
    visible: true,
    sortable: true,
    resizable: true,
    order: 7,
  },
  {
    id: 'actions',
    type: 'actions',
    key: 'actions',
    label: '',
    width: 40,
    minWidth: 30,
    maxWidth: 50,
    visible: true,
    sortable: false, // Actions column should not be sortable
    resizable: false,
    order: 8,
  },
];

// Responsive breakpoints for column visibility
export const RESPONSIVE_BREAKPOINTS = {
  mobile: 640,
  tablet: 768,
  desktop: 1024,
  wide: 1280,
} as const;

// Columns that should be hidden on smaller screens
export const MOBILE_HIDDEN_COLUMNS = [
  'organization',
  'publication_date', 
  'deadline_progress',
  'board_status'
];

export const TABLET_HIDDEN_COLUMNS = [
  'deadline_progress'
];

// Type guard functions
export const isCriteriaColumn = (column: ColumnConfig): column is CriteriaColumnConfig => {
  return column.type === 'criteria';
};

export const isStandardColumn = (column: ColumnConfig): column is StandardColumnConfig => {
  return column.type !== 'criteria';
};
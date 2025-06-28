export type FieldType = 
  | 'text' 
  | 'date' 
  | 'score' 
  | 'status' 
  | 'progress' 
  | 'actions' 
  | 'source' 
  | 'criteria'
  | 'organization'
  | 'deadline';

export type SortableField = 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date';

export interface TableColumn {
  id: string;
  field_name: string;
  display_name: string;
  field_type: FieldType;
  width: number;
  min_width: number;
  max_width?: number;
  sortable: boolean;
  visible: boolean;
  order: number;
  responsive_breakpoint?: 'sm' | 'md' | 'lg' | 'xl';
  criteria_name?: string; // For criteria columns
}

export interface TenderTableLayout {
  id: string;
  name: string;
  user_id: string;
  org_id?: string;
  is_default: boolean;
  columns: TableColumn[];
  created_at: string;
  updated_at: string;
}

// Default layout configuration
export const DEFAULT_TABLE_COLUMNS: Omit<TableColumn, 'id'>[] = [
  {
    field_name: 'source',
    display_name: '',
    field_type: 'source',
    width: 40,
    min_width: 40,
    max_width: 60,
    sortable: false,
    visible: true,
    order: 0,
  },
  {
    field_name: 'name',
    display_name: 'Order',
    field_type: 'text',
    width: 280,
    min_width: 200,
    max_width: 400,
    sortable: false,
    visible: true,
    order: 1,
  },
  {
    field_name: 'organization',
    display_name: 'Client',
    field_type: 'organization',
    width: 150,
    min_width: 120,
    max_width: 250,
    sortable: false,
    visible: true,
    order: 2,
    responsive_breakpoint: 'lg',
  },
  {
    field_name: 'initiation_date',
    display_name: 'Publication Date',
    field_type: 'date',
    width: 100,
    min_width: 80,
    max_width: 120,
    sortable: true,
    visible: true,
    order: 3,
  },
  {
    field_name: 'progress',
    display_name: '',
    field_type: 'progress',
    width: 80,
    min_width: 60,
    max_width: 100,
    sortable: false,
    visible: true,
    order: 4,
    responsive_breakpoint: 'lg',
  },
  {
    field_name: 'submission_deadline',
    display_name: 'Submission Deadline',
    field_type: 'deadline',
    width: 140,
    min_width: 120,
    max_width: 180,
    sortable: true,
    visible: true,
    order: 5,
  },
  {
    field_name: 'status',
    display_name: 'Board Status',
    field_type: 'status',
    width: 120,
    min_width: 100,
    max_width: 180,
    sortable: false,
    visible: true,
    order: 6,
    responsive_breakpoint: 'lg',
  },
  {
    field_name: 'tender_score',
    display_name: 'Relevance',
    field_type: 'score',
    width: 100,
    min_width: 80,
    max_width: 120,
    sortable: true,
    visible: true,
    order: 7,
  },
  {
    field_name: 'actions',
    display_name: '',
    field_type: 'actions',
    width: 40,
    min_width: 40,
    max_width: 60,
    sortable: false,
    visible: true,
    order: 8,
  },
];

export interface TableLayoutContextType {
  currentLayout: TenderTableLayout | null;
  layouts: TenderTableLayout[];
  updateColumnWidth: (columnId: string, width: number) => void;
  updateColumnVisibility: (columnId: string, visible: boolean) => void;
  updateColumnOrder: (columnId: string, newOrder: number) => void;
  addCriteriaColumn: (criteriaName: string) => void;
  removeCriteriaColumn: (criteriaName: string) => void;
  saveLayout: () => Promise<void>;
  loadLayouts: () => Promise<void>;
  createLayout: (name: string, basedOn?: TenderTableLayout) => Promise<void>;
  deleteLayout: (layoutId: string) => Promise<void>;
  setCurrentLayout: (layout: TenderTableLayout) => void;
}
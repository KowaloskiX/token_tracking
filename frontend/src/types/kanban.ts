export interface KanbanTenderItem {
  id: string;
  board_id: string;
  column_id: string;
  tender_analysis_result_id: string;
  name?: string;
  order: number;
  created_at?: string;
  updated_at?: string;
}

export interface KanbanColumn {
  id: string;
  name: string;
  order: number;
  color?: string;
  limit?: number;
  tenderItems: KanbanTenderItem[];
}

export interface KanbanBoard {
  id: string;
  user_id: string;
  org_id?: string | null;
  name: string;
  shared_with: string[];
  created_at?: string;
  updated_at?: string;
  columns: KanbanColumn[];
  assigned_users?: string[];    // ← add this
}

// Interface matching the backend MoveTenderRequest model for moving tenders between columns
export interface MoveTenderRequest {
  source_column_id: string;
  target_column_id: string;
}

export const COLUMN_COLORS = [
  "#F5EFE4", // --background / light cream
  "#E3D9C6", // soft sand beige
  "#B79C8A", // --primary-hover / dusty rose-brown
  "#8E6A47", // warm caramel brown
  "#D6C5B0", // muted vanilla
  "#C19A6A", // golden taupe
  "#A57D55", // deep honey brown
  "#6F4F1E", // rich coffee brown
  "#F4A261", // soft orange
  "#EAB308", // bright yellow
  "#81C784", // soft dark green
  "#388E3C", // rich forest green
  "#F29C11", // vibrant amber
  "#C8B8A5", // pale mushroom beige
  "#B37F4C", // warm ochre
] as const;

export const DEFAULT_COLUMN_COLOR = COLUMN_COLORS[0];

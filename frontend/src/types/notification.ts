export interface Notification {
  id: string;
  title: string;
  content: string; // HTML content
  type: 'info' | 'warning' | 'success' | 'error' | 'update' | 'results'; // Added new types
  is_read: boolean; // Match backend field name
  created_at: string; // Match backend field name
  user_id: string;
  org_id?: string; // Optional for organization-wide notifications
}
// hooks/table/useTableColumns.ts

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ColumnConfig,
  StandardColumnConfig,
  CriteriaColumnConfig,
  TableColumnState,
  ColumnManagerState,
  DEFAULT_COLUMNS,
  BackendColumnConfig,
  RESPONSIVE_BREAKPOINTS,
  MOBILE_HIDDEN_COLUMNS,
  TABLET_HIDDEN_COLUMNS,
  SortDirection,
  isCriteriaColumn
} from '@/types/tableColumns';

interface UseTableColumnsProps {
  selectedAnalysisId?: string;
  availableCriteria: Array<{
    id: string;
    name: string;
    description?: string;
  }>;
  tableWidth: number;
}

interface BackendColumnConfigRequest {
  column_id: string;
  column_type: string;
  column_key: string;
  label: string;
  width: number;
  visible: boolean;
  order: number;
  criteria_id?: string;
}

interface ColumnConfigurationResponse {
  columns: Array<{
    _id: string;
    user_id: string;
    analysis_id: string;
    column_id: string;
    column_type: string;
    column_key: string;
    label: string;
    width: number;
    visible: boolean;
    order: number;
    criteria_id?: string;
    created_at: string;
    updated_at: string;
  }>;
  total_count: number;
}

export const useTableColumns = ({
  selectedAnalysisId,
  availableCriteria,
  tableWidth
}: UseTableColumnsProps) => {
  // Column state
  const [columnState, setColumnState] = useState<TableColumnState>({
    columns: DEFAULT_COLUMNS,
    sortConfig: null
  });

  // Column manager state
  const [managerState, setManagerState] = useState<ColumnManagerState>({
    isOpen: false,
    draggedColumn: null,
    availableCriteria
  });

  // Track if columns were loaded from backend
  const [isLoadedFromBackend, setIsLoadedFromBackend] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [lastSavedColumns, setLastSavedColumns] = useState<string>('');

  // Update available criteria when they change
  useEffect(() => {
    setManagerState(prev => ({
      ...prev,
      availableCriteria
    }));
  }, [availableCriteria]);

  // Responsive column visibility based on actual container width
  const responsiveColumns = useMemo(() => {
    const availableWidth = tableWidth;
    let columnsToShow = [...columnState.columns];

    // Define priority order for hiding columns (least important first)
    const hidePriority = [
      'deadline_progress',
      'publication_date',
      'organization',
      'board_status',
    ];

    // Calculate total width of currently visible columns
    let totalWidth = columnsToShow
      .filter(col => col.visible)
      .reduce((sum, col) => sum + col.width, 0);

    // Add some padding for scroll bars and margins
    const padding = 150;

    // If table is too wide, start hiding columns by priority (but not criteria)
    if (totalWidth + padding > availableWidth && availableWidth > 0) {
      for (const columnId of hidePriority) {
        const columnIndex = columnsToShow.findIndex(col => col.id === columnId && col.visible);
        if (columnIndex !== -1 && totalWidth + padding > availableWidth) {
          columnsToShow = columnsToShow.map(col =>
            col.id === columnId ? { ...col, visible: false } : col
          );
          totalWidth -= columnsToShow[columnIndex].width;
        }
      }
    }

    // Apply mobile/tablet responsive rules
    const isMobile = tableWidth < RESPONSIVE_BREAKPOINTS.tablet;
    const isTablet = tableWidth >= RESPONSIVE_BREAKPOINTS.tablet && tableWidth < RESPONSIVE_BREAKPOINTS.desktop;

    return columnsToShow.map(column => {
      let visible = column.visible;

      // Only apply responsive hiding if the column wasn't already hidden by space constraints
      if (visible) {
        if (isMobile && MOBILE_HIDDEN_COLUMNS.includes(column.id)) {
          visible = false;
        } else if (isTablet && TABLET_HIDDEN_COLUMNS.includes(column.id)) {
          visible = false;
        }

        // Always show criteria columns on desktop and larger screens if user enabled them
        if (column.type === 'criteria' && tableWidth >= RESPONSIVE_BREAKPOINTS.desktop) {
          visible = column.visible; // Respect the original visibility setting
        }
      }

      return {
        ...column,
        visible
      };
    });
  }, [columnState.columns, tableWidth]);

  // Get visible columns sorted by order
  const visibleColumns = useMemo(() => {
    return responsiveColumns
      .filter(col => col.visible)
      .sort((a, b) => a.order - b.order);
  }, [responsiveColumns]);

  // Calculate total table width
  const totalTableWidth = useMemo(() => {
    return visibleColumns.reduce((total, col) => total + col.width, 0);
  }, [visibleColumns]);

  const loadColumnsFromBackend = useCallback(async () => {
    if (!selectedAnalysisId) return;

    setIsLoading(true);
    try {
      console.log(`Loading column config for analysis: ${selectedAnalysisId}`);
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/column-config`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data: ColumnConfigurationResponse = await response.json();
        console.log('Loaded column configuration:', data);

        if (data.columns && data.columns.length > 0) {
          const convertedColumns = convertBackendToColumns(data.columns);
          setColumnState(prev => ({
            ...prev,
            columns: convertedColumns
          }));
          
          // Initialize lastSavedColumns to prevent immediate auto-save
          const columnsString = JSON.stringify(
            convertedColumns.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(columnsString);
          
          console.log('Applied loaded columns:', convertedColumns);
        } else {
          console.log('No saved columns found, using defaults');
          // Initialize lastSavedColumns for defaults too
          const defaultColumnsString = JSON.stringify(
            DEFAULT_COLUMNS.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(defaultColumnsString);
        }
      } else if (response.status === 404) {
        console.log('No saved configuration found, using defaults');
      } else {
        console.error('Failed to load column configuration:', response.status, await response.text());
      }
    } catch (error) {
      console.error('Failed to load column configuration:', error);
    } finally {
      setIsLoadedFromBackend(true);
      setIsLoading(false);
    }
  }, [selectedAnalysisId]);

  const saveColumnsToBackend = useCallback(async (columnsToSave?: ColumnConfig[]) => {
    if (!selectedAnalysisId) {
      console.log('No selected analysis ID, skipping save');
      return false;
    }

    const columns = columnsToSave || columnState.columns;
    setIsLoading(true);

    try {
      console.log('Saving column configuration for analysis:', selectedAnalysisId);
      console.log('Columns to save:', columns);

      const backendColumns = convertColumnsToBackend(columns);
      console.log('Converted to backend format:', backendColumns);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/column-config`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ columns: backendColumns }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to save column configuration:', response.status, errorText);
        throw new Error(`Failed to save: ${response.status} ${errorText}`);
      } else {
        const result = await response.json();
        console.log('Column configuration saved successfully:', result);
        
        // Only update local state if we provided specific columns to save (from ColumnManager)
        if (columnsToSave) {
          setColumnState(prev => ({
            ...prev,
            columns: columnsToSave
          }));
          // Update the lastSavedColumns to prevent auto-save trigger
          const columnsString = JSON.stringify(
            columnsToSave.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(columnsString);
        }
        
        return true;
      }
    } catch (error) {
      console.error('Failed to save column configuration:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [selectedAnalysisId, columnState.columns]);

  // Convert backend format to our format
  const convertBackendToColumns = (backendColumns: ColumnConfigurationResponse['columns']): ColumnConfig[] => {
    return backendColumns.map(col => {
      if (col.criteria_id) {
        return {
          id: col.column_id,
          type: 'criteria' as const,
          key: col.column_key,
          label: col.label,
          width: col.width,
          minWidth: 100,
          maxWidth: 300,
          visible: col.visible,
          sortable: true,
          resizable: true,
          order: col.order,
          criteriaName: col.label,
          criteriaId: col.criteria_id,
        } as CriteriaColumnConfig;
      } else {
        // Find the default column to get proper min/max widths
        const defaultColumn = DEFAULT_COLUMNS.find(dc => dc.id === col.column_id);
        
        return {
          id: col.column_id,
          type: col.column_type as any,
          key: col.column_key,
          label: col.label,
          width: col.width,
          minWidth: defaultColumn?.minWidth || 50,
          maxWidth: defaultColumn?.maxWidth || 500,
          visible: col.visible,
          sortable: defaultColumn?.sortable ?? true,
          resizable: defaultColumn?.resizable ?? true,
          order: col.order,
        } as StandardColumnConfig;
      }
    });
  };

  const convertColumnsToBackend = (columns: ColumnConfig[]): BackendColumnConfigRequest[] => {
    return columns.map(col => ({
      column_id: col.id,
      column_type: col.type,
      column_key: col.key,
      label: col.label,
      width: col.width,
      visible: col.visible,
      order: col.order,
      criteria_id: col.type === 'criteria' ? (col as CriteriaColumnConfig).criteriaId : undefined,
    }));
  };

  const resetColumnsToDefaults = useCallback(async () => {
    if (!selectedAnalysisId) {
      throw new Error('No analysis selected');
    }

    setIsLoading(true);
    try {
      console.log('Resetting column configuration to defaults');
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/column-config`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        // Reset to default columns in state
        setColumnState({
          columns: DEFAULT_COLUMNS,
          sortConfig: null
        });
        console.log('Column configuration reset to defaults');
      } else {
        const errorText = await response.text();
        console.error('Failed to reset column configuration:', response.status, errorText);
        throw new Error(`Failed to reset: ${response.status} ${errorText}`);
      }
    } catch (error) {
      console.error('Failed to reset column configuration:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [selectedAnalysisId]);

  // Column manipulation functions
  const updateColumnWidth = useCallback((columnId: string, newWidth: number) => {
    setColumnState(prev => ({
      ...prev,
      columns: prev.columns.map(col =>
        col.id === columnId
          ? { ...col, width: Math.max(col.minWidth, Math.min(col.maxWidth, newWidth)) }
          : col
      )
    }));
  }, []);

  const toggleColumnVisibility = useCallback((columnId: string) => {
    setColumnState(prev => ({
      ...prev,
      columns: prev.columns.map(col =>
        col.id === columnId ? { ...col, visible: !col.visible } : col
      )
    }));
  }, []);

  const reorderColumns = useCallback((sourceIndex: number, destinationIndex: number) => {
    setColumnState(prev => {
      const columns = [...prev.columns];
      const [removed] = columns.splice(sourceIndex, 1);
      columns.splice(destinationIndex, 0, removed);

      // Update order values
      const reorderedColumns = columns.map((col, index) => ({
        ...col,
        order: index
      }));

      return {
        ...prev,
        columns: reorderedColumns
      };
    });
  }, []);

  const addCriteriaColumn = useCallback((criteriaId: string, criteriaName: string) => {
    setColumnState(prev => {
      // Use criteria name for ID generation to ensure uniqueness
      const columnId = `criteria-${criteriaName.replace(/[^a-zA-Z0-9]/g, '_')}`;
      
      // Check if this criteria column already exists by ID or criteriaName
      const existingColumn = prev.columns.find(col => 
        col.id === columnId ||
        (col.type === 'criteria' && 
         isCriteriaColumn(col) && 
         (col as CriteriaColumnConfig).criteriaName === criteriaName)
      );
      
      if (existingColumn) {
        console.log(`Criteria column for ${criteriaName} already exists, skipping`);
        return prev;
      }

      const newColumn: CriteriaColumnConfig = {
        id: columnId, // Use sanitized criteria name for ID
        type: 'criteria',
        key: `criteria_analysis.${criteriaName}`,
        label: criteriaName,
        width: 160,
        minWidth: 120,
        maxWidth: 400,
        visible: true,
        sortable: true,
        resizable: true,
        order: prev.columns.length,
        criteriaName: criteriaName,
        criteriaId: criteriaId,
      };

      console.log('Adding criteria column:', newColumn);
      
      return {
        ...prev,
        columns: [...prev.columns, newColumn]
      };
    });
  }, []);

  const removeCriteriaColumn = useCallback((criteriaId: string) => {
    setColumnState(prev => ({
      ...prev,
      columns: prev.columns.filter(col => {
        if (!isCriteriaColumn(col)) return true;
        const criteriaCol = col as CriteriaColumnConfig;
        return criteriaCol.criteriaId !== criteriaId;
      })
    }));
  }, []);

  const setSortConfig = useCallback((columnId: string, direction: SortDirection) => {
    setColumnState(prev => ({
      ...prev,
      sortConfig: direction ? { columnId, direction } : null
    }));
  }, []);

  const resetToDefaults = useCallback(async () => {
    await resetColumnsToDefaults();
  }, [resetColumnsToDefaults]);

  // Column manager controls
  const openColumnManager = useCallback(() => {
    setManagerState(prev => ({ ...prev, isOpen: true }));
  }, []);

  const closeColumnManager = useCallback(() => {
    setManagerState(prev => ({ ...prev, isOpen: false, draggedColumn: null }));
  }, []);

  // Load columns when analysis changes
  useEffect(() => {
    if (selectedAnalysisId) {
      setIsLoadedFromBackend(false);
      setColumnState({ columns: DEFAULT_COLUMNS, sortConfig: null });
      loadColumnsFromBackend();
    }
  }, [selectedAnalysisId, loadColumnsFromBackend]);

  // Auto-save columns when they change (with debounce) - only for width changes  
  useEffect(() => {
    if (!isLoadedFromBackend || isLoading) return;

    // Only auto-save for width changes to prevent infinite loops
    const currentColumnsString = JSON.stringify(
      columnState.columns.map(col => ({ id: col.id, width: col.width }))
    );
    
    if (currentColumnsString === lastSavedColumns) return;

    const timeoutId = setTimeout(() => {
      console.log('Auto-saving column width changes...');
      saveColumnsToBackend().then(() => {
        setLastSavedColumns(currentColumnsString);
      }).catch(error => {
        console.error('Auto-save failed:', error);
      });
    }, 1000);

    return () => clearTimeout(timeoutId);
  }, [columnState.columns, isLoadedFromBackend, isLoading, lastSavedColumns, saveColumnsToBackend]);

  return {
    // State
    columnState,
    managerState,
    visibleColumns,
    responsiveColumns,
    totalTableWidth,
    isLoadedFromBackend,
    isLoading,

    // Column manipulation
    updateColumnWidth,
    toggleColumnVisibility,
    reorderColumns,
    addCriteriaColumn,
    removeCriteriaColumn,
    setSortConfig,
    resetToDefaults,

    // Manager controls
    openColumnManager,
    closeColumnManager,

    // Backend integration
    loadColumnsFromBackend,
    saveColumnsToBackend,
  };
};
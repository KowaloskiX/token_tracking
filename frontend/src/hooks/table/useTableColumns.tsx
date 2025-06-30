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
      // Don't auto-hide criteria columns - let user control them
    ];

    // Calculate total width of currently visible columns
    let totalWidth = columnsToShow
      .filter(col => col.visible)
      .reduce((sum, col) => sum + col.width, 0);

    // Add some padding for scroll bars and margins
    const padding = 150; // Increased padding for criteria columns

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
    if (!selectedAnalysisId || isLoadedFromBackend) return;

    try {
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

        if (data.columns && data.columns.length > 0) {
          const convertedColumns = convertBackendToColumns(data.columns);
          setColumnState(prev => ({
            ...prev,
            columns: convertedColumns
          }));
        }
        // If no columns found, keep default columns

        setIsLoadedFromBackend(true);
      } else if (response.status === 404) {
        // No saved configuration found, use defaults
        setIsLoadedFromBackend(true);
      } else {
        console.error('Failed to load column configuration:', response.status);
        setIsLoadedFromBackend(true);
      }
    } catch (error) {
      console.error('Failed to load column configuration:', error);
      // Fallback to default columns
      setIsLoadedFromBackend(true);
    }
  }, [selectedAnalysisId, isLoadedFromBackend]);

  const saveColumnsToBackend = useCallback(async () => {
    if (!selectedAnalysisId) return;

    try {
      const backendColumns = convertColumnsToBackend(columnState.columns);

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
        console.error('Failed to save column configuration:', response.status);
      } else {
        console.log('Column configuration saved successfully');
      }
    } catch (error) {
      console.error('Failed to save column configuration:', error);
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
        return {
          id: col.column_id,
          type: col.column_type as any,
          key: col.column_key,
          label: col.label,
          width: col.width,
          minWidth: 50,
          maxWidth: 500,
          visible: col.visible,
          sortable: true,
          resizable: true,
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
    if (!selectedAnalysisId) return;

    try {
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
        console.error('Failed to reset column configuration:', response.status);
      }
    } catch (error) {
      console.error('Failed to reset column configuration:', error);
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
    const newColumn: CriteriaColumnConfig = {
      id: `criteria-${criteriaId}`, // Use criteria name as part of ID
      type: 'criteria',
      key: `criteria_analysis.${criteriaName}`,
      label: criteriaName,
      width: 160,
      minWidth: 120,
      maxWidth: 400,
      visible: true,
      sortable: true, // Enable sorting for criteria columns
      resizable: true,
      order: columnState.columns.length,
      criteriaName: criteriaName, // Store the actual criteria name
      criteriaId: criteriaId, // Store the ID for reference
    };

    setColumnState(prev => ({
      ...prev,
      columns: [...prev.columns, newColumn]
    }));
  }, [columnState.columns.length]);

  const removeCriteriaColumn = useCallback((criteriaId: string) => {
    setColumnState(prev => ({
      ...prev,
      columns: prev.columns.filter(col => {
        if (!isCriteriaColumn(col)) return true;
        const criteriaCol = col as CriteriaColumnConfig;
        return criteriaCol.criteriaId !== criteriaId; // Match by the criteriaId (criteria name)
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
    setIsLoadedFromBackend(false);
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
      loadColumnsFromBackend();
    }
  }, [selectedAnalysisId, loadColumnsFromBackend]);

  // Auto-save columns when they change (debounced)
  useEffect(() => {
    if (!isLoadedFromBackend) return;

    const timeoutId = setTimeout(() => {
      saveColumnsToBackend();
    }, 1000); // Debounce for 1 second

    return () => clearTimeout(timeoutId);
  }, [columnState.columns, isLoadedFromBackend, saveColumnsToBackend]);

  return {
    // State
    columnState,
    managerState,
    visibleColumns,
    responsiveColumns,
    totalTableWidth,
    isLoadedFromBackend,

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
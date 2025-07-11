import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ColumnConfig,
  StandardColumnConfig,
  CriteriaColumnConfig,
  TableColumnState,
  TableLayoutState,
  DEFAULT_COLUMNS,
  RESPONSIVE_BREAKPOINTS,
  MOBILE_HIDDEN_COLUMNS,
  TABLET_HIDDEN_COLUMNS,
  SortDirection,
  isCriteriaColumn,
  CriteriaDisplayMode
} from '@/types/tableColumns';
import { TenderAnalysisResult } from '@/types/tenders';

interface UseTableColumnsProps {
  selectedAnalysisId?: string;
  availableCriteria: Array<{
    id: string;
    name: string;
    description?: string;
  }>;
  tableWidth: number;
  selectedResult?: TenderAnalysisResult | null;
  isDrawerVisible?: boolean; // NEW: Add isDrawerVisible prop
}

// Simplified backend structure - only stores user preferences
interface SimplifiedColumnConfig {
  column_id: string;
  width: number;
  visible: boolean;
  order: number;
  criteria_id?: string;
  display_mode?: string; // NEW: Add display mode for criteria columns
}

interface TableLayoutResponse {
  columns: SimplifiedColumnConfig[];
  total_count: number;
}

export const useTableColumns = ({
  selectedAnalysisId,
  availableCriteria,
  tableWidth,
  selectedResult,
  isDrawerVisible = false // NEW: Add with default value
}: UseTableColumnsProps) => {
  // Column state
  const [columnState, setColumnState] = useState<TableColumnState>({
    columns: DEFAULT_COLUMNS,
    sortConfig: null
  });

  // Column manager state
  const [managerState, setManagerState] = useState<TableLayoutState>({
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

  // Keep original column widths regardless of drawer visibility so that expanding/collapsing
  // the sidebar does not alter user-configured table layout.
  const adjustedColumns = useMemo(() => {
    return columnState.columns;
  }, [columnState.columns]);

  const responsiveColumns = useMemo(() => {
    const columnsToShow = [...adjustedColumns];

    // Only apply responsive breakpoints based on viewport width, not container width,
    // so opening the sidebar (which shrinks the table container) does not incorrectly
    // trigger mobile/tablet hiding logic.

    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : tableWidth;

    const isMobile = viewportWidth < RESPONSIVE_BREAKPOINTS.tablet;
    const isTablet = viewportWidth >= RESPONSIVE_BREAKPOINTS.tablet && viewportWidth < RESPONSIVE_BREAKPOINTS.desktop;

    return columnsToShow.map(column => {
      let visible = column.visible;

      if (visible) {
        // Apply mobile/tablet responsive hiding
        if (isMobile && MOBILE_HIDDEN_COLUMNS.includes(column.id)) {
          visible = false;
        } else if (isTablet && TABLET_HIDDEN_COLUMNS.includes(column.id)) {
          visible = false;
        }

        // Keep criteria columns visible on desktop regardless of sidebar state
        if (column.type === 'criteria' && viewportWidth >= RESPONSIVE_BREAKPOINTS.desktop) {
          visible = column.visible;
        }
      }

      return { ...column, visible };
    });
  }, [adjustedColumns, tableWidth, isDrawerVisible]); // Updated dependency

  const visibleColumns = useMemo(() => {
    return responsiveColumns
      .filter(col => col.visible)
      .sort((a, b) => a.order - b.order);
  }, [responsiveColumns]);

  const totalTableWidth = useMemo(() => {
    return visibleColumns.reduce((total, col) => total + col.width, 0) + 60;
  }, [visibleColumns]);

  // Reconstruct full columns from simplified backend data + defaults + criteria
  const reconstructColumns = useCallback((simplifiedColumns: SimplifiedColumnConfig[]): ColumnConfig[] => {
    const reconstructed: ColumnConfig[] = [];

    // First, add all columns from simplified data
    for (const simpleCol of simplifiedColumns) {
      if (simpleCol.criteria_id) {
        // This is a criteria column
        const criteria = availableCriteria.find(c => c.id === simpleCol.criteria_id);
        if (criteria) {
          const criteriaColumn: CriteriaColumnConfig = {
            id: simpleCol.column_id,
            type: 'criteria',
            key: `criteria_analysis.${criteria.name}`,
            label: criteria.name,
            width: simpleCol.width,
            minWidth: 60,
            maxWidth: 400,
            visible: simpleCol.visible,
            sortable: true,
            resizable: true,
            order: simpleCol.order,
            criteriaName: criteria.name,
            criteriaId: simpleCol.criteria_id,
            displayMode: (simpleCol.display_mode as CriteriaDisplayMode) || 'text', // NEW: Handle display mode
          };
          reconstructed.push(criteriaColumn);
        }
      } else {
        // This is a standard column - get defaults and merge with user prefs
        const defaultCol = DEFAULT_COLUMNS.find(dc => dc.id === simpleCol.column_id);
        if (defaultCol) {
          const standardColumn: StandardColumnConfig = {
            ...defaultCol,
            width: simpleCol.width,
            visible: simpleCol.visible,
            order: simpleCol.order,
          };
          reconstructed.push(standardColumn);
        }
      }
    }

    // Add any missing default columns that weren't in the simplified data
    for (const defaultCol of DEFAULT_COLUMNS) {
      const exists = reconstructed.find(rc => rc.id === defaultCol.id);
      if (!exists) {
        reconstructed.push({ ...defaultCol });
      }
    }

    return reconstructed.sort((a, b) => a.order - b.order);
  }, [availableCriteria]);

  const loadColumnsFromBackend = useCallback(async () => {
    if (!selectedAnalysisId) return;

    setIsLoading(true);
    try {
      console.log(`Loading simplified table layout for analysis: ${selectedAnalysisId}`);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/table-layout`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data: TableLayoutResponse = await response.json();
        console.log('Loaded simplified table layout:', data);

        if (data.columns && data.columns.length > 0) {
          const reconstructedColumns = reconstructColumns(data.columns);
          setColumnState(prev => ({
            ...prev,
            columns: reconstructedColumns
          }));

          const columnsString = JSON.stringify(
            reconstructedColumns.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(columnsString);

          console.log('Applied reconstructed columns:', reconstructedColumns);
        } else {
          console.log('No saved table layout found, using defaults');
          const defaultColumnsString = JSON.stringify(
            DEFAULT_COLUMNS.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(defaultColumnsString);
        }
      } else if (response.status === 404) {
        console.log('No saved table layout found, using defaults');
      } else {
        console.error('Failed to load table layout:', response.status, await response.text());
      }
    } catch (error) {
      console.error('Failed to load table layout:', error);
    } finally {
      setIsLoadedFromBackend(true);
      setIsLoading(false);
    }
  }, [selectedAnalysisId, reconstructColumns]);

  // Convert full columns to simplified format for backend
  const convertToSimplified = useCallback((columns: ColumnConfig[]): SimplifiedColumnConfig[] => {
    return columns.map(col => ({
      column_id: col.id,
      width: col.width,
      visible: col.visible,
      order: col.order,
      criteria_id: col.type === 'criteria' ? (col as CriteriaColumnConfig).criteriaId : undefined,
      display_mode: col.type === 'criteria' ? (col as CriteriaColumnConfig).displayMode : undefined, // NEW: Include display mode
    }));
  }, []);

  const saveColumnsToBackend = useCallback(async (columnsToSave?: ColumnConfig[]): Promise<void> => {
    if (!selectedAnalysisId) {
      console.log('No selected analysis ID, skipping save');
      return;
    }

    const columns = columnsToSave || columnState.columns;
    setIsLoading(true);

    try {
      console.log('Saving simplified table layout for analysis:', selectedAnalysisId);

      const simplifiedColumns = convertToSimplified(columns);
      console.log('Converted to simplified format:', simplifiedColumns);

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/table-layout`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ columns: simplifiedColumns }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to save table layout:', response.status, errorText);
        throw new Error(`Failed to save: ${response.status} ${errorText}`);
      } else {
        const result = await response.json();
        console.log('Simplified table layout saved successfully:', result);

        if (columnsToSave) {
          setColumnState(prev => ({
            ...prev,
            columns: columnsToSave
          }));
          const columnsString = JSON.stringify(
            columnsToSave.map(col => ({ id: col.id, width: col.width }))
          );
          setLastSavedColumns(columnsString);
        }
      }
    } catch (error) {
      console.error('Failed to save table layout:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [selectedAnalysisId, columnState.columns, convertToSimplified]);

  const resetColumnsToDefaults = useCallback(async () => {
    if (!selectedAnalysisId) {
      throw new Error('No analysis selected');
    }

    setIsLoading(true);
    try {
      console.log('Resetting table layout to defaults');

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysisId}/table-layout`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        setColumnState({
          columns: DEFAULT_COLUMNS,
          sortConfig: null
        });
        console.log('Table layout reset to defaults');
      } else {
        const errorText = await response.text();
        console.error('Failed to reset table layout:', response.status, errorText);
        throw new Error(`Failed to reset: ${response.status} ${errorText}`);
      }
    } catch (error) {
      console.error('Failed to reset table layout:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [selectedAnalysisId]);

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

  // NEW: Function to update criteria display mode
  const updateCriteriaDisplayMode = useCallback((columnId: string, displayMode: CriteriaDisplayMode) => {
    setColumnState(prev => ({
      ...prev,
      columns: prev.columns.map(col => {
        if (col.id === columnId && isCriteriaColumn(col)) {
          return { ...col, displayMode };
        }
        return col;
      })
    }));
  }, []);

  const reorderColumns = useCallback((sourceIndex: number, destinationIndex: number) => {
    setColumnState(prev => {
      const columns = [...prev.columns];
      const [removed] = columns.splice(sourceIndex, 1);
      columns.splice(destinationIndex, 0, removed);

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
      const columnId = `criteria-${criteriaName.replace(/[^a-zA-Z0-9]/g, '_')}`;

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
        id: columnId,
        type: 'criteria',
        key: `criteria_analysis.${criteriaName}`,
        label: criteriaName,
        width: 160,
        minWidth: 60,
        maxWidth: 400,
        visible: true,
        sortable: true,
        resizable: true,
        order: prev.columns.length,
        criteriaName: criteriaName,
        criteriaId: criteriaId,
        displayMode: 'text', // NEW: Default to text mode
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

  const setSortConfig = useCallback((columnIdOrCriteriaName: string, direction: SortDirection) => {
    setColumnState(prev => ({
      ...prev,
      sortConfig: direction ? { columnId: columnIdOrCriteriaName, direction } : null
    }));
  }, []);

  const resetToDefaults = useCallback(async () => {
    await resetColumnsToDefaults();
  }, [resetColumnsToDefaults]);

  const openTableLayout = useCallback(() => {
    setManagerState(prev => ({ ...prev, isOpen: true }));
  }, []);

  const closeTableLayout = useCallback(() => {
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

  // Auto-save logic
  useEffect(() => {
    if (!isLoadedFromBackend || isLoading) return;

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
    updateCriteriaDisplayMode, // NEW: Export the new function
    reorderColumns,
    addCriteriaColumn,
    removeCriteriaColumn,
    setSortConfig,
    resetToDefaults,

    // Manager controls
    openTableLayout,
    closeTableLayout,

    // Backend integration
    loadColumnsFromBackend,
    saveColumnsToBackend,
  };
};
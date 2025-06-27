// src/hooks/table/useTableLayout.tsx

import { useState, useCallback, useEffect, useMemo } from 'react';
import { TenderTableLayout, TableColumn, DEFAULT_TABLE_COLUMNS, TableLayoutContextType } from '@/types/table';
import { TenderAnalysis } from '@/types/tenders';

interface UseTableLayoutProps {
  selectedAnalysis?: TenderAnalysis | null;
}

export const useTableLayout = ({ selectedAnalysis }: UseTableLayoutProps) => {
  const [currentLayout, setCurrentLayout] = useState<TenderTableLayout | null>(null);
  const [layouts, setLayouts] = useState<TenderTableLayout[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Generate default layout with criteria columns
  const generateDefaultLayout = useCallback((): TenderTableLayout => {
    let columns: TableColumn[] = DEFAULT_TABLE_COLUMNS.map((col, index) => ({
      ...col,
      id: `col_${index}_${col.field_name}`,
    }));

    // Add criteria columns if available
    if (selectedAnalysis?.criteria) {
      const criteriaColumns: TableColumn[] = selectedAnalysis.criteria.map((criteria, index) => ({
        id: `criteria_${criteria.name.replace(/\s+/g, '_').toLowerCase()}`,
        field_name: 'criteria',
        display_name: criteria.name,
        field_type: 'criteria' as const,
        width: 120,
        min_width: 100,
        max_width: 200,
        sortable: true,
        visible: true,
        order: 100 + index, // Place after default columns
        criteria_name: criteria.name,
      }));
      
      // Insert criteria columns before actions column
      const actionsIndex = columns.findIndex(col => col.field_type === 'actions');
      if (actionsIndex !== -1) {
        columns.splice(actionsIndex, 0, ...criteriaColumns);
        // Update order for actions column
        columns[columns.length - 1].order = 200;
      } else {
        columns.push(...criteriaColumns);
      }
    }

    return {
      id: 'default',
      name: 'Default Layout',
      user_id: '',
      is_default: true,
      columns: columns.sort((a, b) => a.order - b.order),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }, [selectedAnalysis?.criteria]);

  // Load layouts from localStorage (in a real app, this would be an API call)
  const loadLayouts = useCallback(async () => {
    setIsLoading(true);
    try {
      const stored = localStorage.getItem('tender_table_layouts');
      const storedLayouts = stored ? JSON.parse(stored) : [];
      
      const defaultLayout = generateDefaultLayout();
      const allLayouts = [defaultLayout, ...storedLayouts.filter((l: TenderTableLayout) => !l.is_default)];
      
      setLayouts(allLayouts);
      
      if (!currentLayout) {
        setCurrentLayout(defaultLayout);
      } else {
        // Update current layout with new criteria if analysis changed
        const updatedLayout = {
          ...defaultLayout,
          id: currentLayout.id,
          name: currentLayout.name,
          is_default: currentLayout.is_default,
          // Merge existing column widths with new layout
          columns: defaultLayout.columns.map(newCol => {
            const existingCol = currentLayout.columns.find(c => 
              c.field_name === newCol.field_name && 
              c.criteria_name === newCol.criteria_name
            );
            return existingCol ? { ...newCol, width: existingCol.width, visible: existingCol.visible } : newCol;
          })
        };
        setCurrentLayout(updatedLayout);
      }
    } catch (error) {
      console.error('Error loading table layouts:', error);
      const defaultLayout = generateDefaultLayout();
      setLayouts([defaultLayout]);
      setCurrentLayout(defaultLayout);
    } finally {
      setIsLoading(false);
    }
  }, [generateDefaultLayout, currentLayout]);

  // Save layouts to localStorage (in a real app, this would be an API call)
  const saveLayouts = useCallback(async (updatedLayouts: TenderTableLayout[]) => {
    try {
      const nonDefaultLayouts = updatedLayouts.filter(l => !l.is_default);
      localStorage.setItem('tender_table_layouts', JSON.stringify(nonDefaultLayouts));
    } catch (error) {
      console.error('Error saving table layouts:', error);
    }
  }, []);

  const updateColumnWidth = useCallback((columnId: string, width: number) => {
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      columns: currentLayout.columns.map(col =>
        col.id === columnId
          ? { ...col, width: Math.max(col.min_width, Math.min(col.max_width || 500, width)) }
          : col
      ),
      updated_at: new Date().toISOString(),
    };

    setCurrentLayout(updatedLayout);
    
    // Update layouts array
    setLayouts(prev => prev.map(layout =>
      layout.id === currentLayout.id ? updatedLayout : layout
    ));

    // Auto-save after a brief delay
    setTimeout(() => {
      if (!updatedLayout.is_default) {
        saveLayouts([updatedLayout, ...layouts.filter(l => l.id !== updatedLayout.id)]);
      }
    }, 100);
  }, [currentLayout, layouts, saveLayouts]);

  const updateColumnVisibility = useCallback((columnId: string, visible: boolean) => {
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      columns: currentLayout.columns.map(col =>
        col.id === columnId ? { ...col, visible } : col
      ),
      updated_at: new Date().toISOString(),
    };

    setCurrentLayout(updatedLayout);
    setLayouts(prev => prev.map(layout =>
      layout.id === currentLayout.id ? updatedLayout : layout
    ));
  }, [currentLayout]);

  const updateColumnOrder = useCallback((columnId: string, newOrder: number) => {
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      columns: currentLayout.columns.map(col =>
        col.id === columnId ? { ...col, order: newOrder } : col
      ).sort((a, b) => a.order - b.order),
      updated_at: new Date().toISOString(),
    };

    setCurrentLayout(updatedLayout);
    setLayouts(prev => prev.map(layout =>
      layout.id === currentLayout.id ? updatedLayout : layout
    ));
  }, [currentLayout]);

  const addCriteriaColumn = useCallback((criteriaName: string) => {
    if (!currentLayout) return;

    const existingColumn = currentLayout.columns.find(col => 
      col.field_type === 'criteria' && col.criteria_name === criteriaName
    );

    if (existingColumn) {
      // If column exists, just make it visible
      updateColumnVisibility(existingColumn.id, true);
      return;
    }

    const maxOrder = Math.max(...currentLayout.columns.map(col => col.order));
    const newColumn: TableColumn = {
      id: `criteria_${criteriaName.replace(/\s+/g, '_').toLowerCase()}`,
      field_name: 'criteria',
      display_name: criteriaName,
      field_type: 'criteria',
      width: 120,
      min_width: 100,
      max_width: 200,
      sortable: true,
      visible: true,
      order: maxOrder + 1,
      criteria_name: criteriaName,
    };

    const updatedLayout = {
      ...currentLayout,
      columns: [...currentLayout.columns, newColumn].sort((a, b) => a.order - b.order),
      updated_at: new Date().toISOString(),
    };

    setCurrentLayout(updatedLayout);
    setLayouts(prev => prev.map(layout =>
      layout.id === currentLayout.id ? updatedLayout : layout
    ));
  }, [currentLayout, updateColumnVisibility]);

  const removeCriteriaColumn = useCallback((criteriaName: string) => {
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      columns: currentLayout.columns.filter(col => 
        !(col.field_type === 'criteria' && col.criteria_name === criteriaName)
      ),
      updated_at: new Date().toISOString(),
    };

    setCurrentLayout(updatedLayout);
    setLayouts(prev => prev.map(layout =>
      layout.id === currentLayout.id ? updatedLayout : layout
    ));
  }, [currentLayout]);

  const saveLayout = useCallback(async () => {
    if (!currentLayout || currentLayout.is_default) return;
    
    await saveLayouts(layouts);
  }, [currentLayout, layouts, saveLayouts]);

  const createLayout = useCallback(async (name: string, basedOn?: TenderTableLayout) => {
    const baseLayout = basedOn || currentLayout || generateDefaultLayout();
    const newLayout: TenderTableLayout = {
      ...baseLayout,
      id: `layout_${Date.now()}`,
      name,
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const updatedLayouts = [...layouts, newLayout];
    setLayouts(updatedLayouts);
    setCurrentLayout(newLayout);
    await saveLayouts(updatedLayouts);
  }, [currentLayout, layouts, generateDefaultLayout, saveLayouts]);

  const deleteLayout = useCallback(async (layoutId: string) => {
    if (layoutId === 'default') return; // Can't delete default layout

    const updatedLayouts = layouts.filter(layout => layout.id !== layoutId);
    setLayouts(updatedLayouts);
    
    if (currentLayout?.id === layoutId) {
      const defaultLayout = updatedLayouts.find(l => l.is_default) || generateDefaultLayout();
      setCurrentLayout(defaultLayout);
    }
    
    await saveLayouts(updatedLayouts);
  }, [layouts, currentLayout, generateDefaultLayout, saveLayouts]);

  // Computed values
  const visibleColumns = useMemo(() => {
    if (!currentLayout) return [];
    return currentLayout.columns
      .filter(col => col.visible)
      .sort((a, b) => a.order - b.order);
  }, [currentLayout]);

  const totalWidth = useMemo(() => {
    return visibleColumns.reduce((sum, col) => sum + col.width, 0);
  }, [visibleColumns]);

  // Load layouts on mount and when selected analysis changes
  useEffect(() => {
    loadLayouts();
  }, [selectedAnalysis?.criteria]);

  return {
    currentLayout,
    layouts,
    visibleColumns,
    totalWidth,
    isLoading,
    updateColumnWidth,
    updateColumnVisibility,
    updateColumnOrder,
    addCriteriaColumn,
    removeCriteriaColumn,
    saveLayout,
    loadLayouts,
    createLayout,
    deleteLayout,
    setCurrentLayout,
  };
};
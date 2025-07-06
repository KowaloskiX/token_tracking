import React, { useEffect, useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
    Loader2, 
    AlertCircle, 
    CheckCircle2, 
    Eye, 
    Type, 
    Table, 
    Filter, 
    Clock,
    Database,
    Globe
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
    ColumnConfig,
    CriteriaColumnConfig,
    isCriteriaColumn,
    CriteriaDisplayMode,
    StandardColumnConfig,
} from '@/types/tableColumns';
import { useTendersTranslations, useTranslations } from '@/hooks/useTranslations';
import { cn } from '@/lib/utils';

interface TableLayoutProps {
    isOpen: boolean;
    onClose: () => void;
    
    // Column management
    columns: ColumnConfig[];
    availableCriteria: Array<{
        id: string;
        name: string;
        description?: string;
    }>;
    onToggleVisibility: (columnId: string) => void;
    onReorderColumns: (sourceIndex: number, destinationIndex: number) => void;
    onAddCriteriaColumn: (criteriaId: string, criteriaName: string) => void;
    onRemoveCriteriaColumn: (criteriaId: string) => void;
    onResetToDefaults: () => Promise<void>;
    onUpdateColumnWidth: (columnId: string, width: number) => void;
    onUpdateCriteriaDisplayMode: (columnId: string, displayMode: CriteriaDisplayMode) => void;
    onSaveConfiguration: (columns: ColumnConfig[]) => Promise<void>;
    
    // Data filters
    includeHistorical: boolean;
    onToggleHistorical: (value: boolean) => void;
    includeFiltered: boolean;
    onToggleFiltered: (value: boolean) => void;
    includeExternal: boolean;
    onToggleExternal: (value: boolean) => void;
    showIncludeExternal: boolean;
}

type SidebarSection = 'columns' | 'dataFilters';

interface SidebarItem {
    id: SidebarSection;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    description: string;
}

export const TableLayout: React.FC<TableLayoutProps> = ({
    isOpen,
    onClose,
    columns,
    availableCriteria,
    onToggleVisibility,
    onReorderColumns,
    onAddCriteriaColumn,
    onRemoveCriteriaColumn,
    onResetToDefaults,
    onUpdateColumnWidth,
    onUpdateCriteriaDisplayMode,
    onSaveConfiguration,
    includeHistorical,
    onToggleHistorical,
    includeFiltered,
    onToggleFiltered,
    includeExternal,
    onToggleExternal,
    showIncludeExternal,
}) => {
    const t = useTranslations();

    const MIN_VISIBLE = 3;

    const [activeSection, setActiveSection] = useState<SidebarSection>('columns');
    const [draftColumns, setDraftColumns] = useState<ColumnConfig[]>([]);
    const [searchCriteria, setSearchCriteria] = useState('');
    const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
    const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [isResetting, setIsResetting] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);

    // Sidebar items with translations
    const SIDEBAR_ITEMS: SidebarItem[] = [
        {
            id: 'columns',
            label: t('tenders.columns.manageColumns'),
            icon: Table,
            description: t('tenders.columns.tableLayoutDescription')
        },
        {
            id: 'dataFilters',
            label: t('tenders.columns.dataFilters'),
            icon: Filter,
            description: t('tenders.columns.dataFiltersDescription')
        }
    ];

    // Function to get translated column label
    const getTranslatedColumnLabel = (column: ColumnConfig): string => {
        if (isCriteriaColumn(column)) {
            const criteriaColumn = column as CriteriaColumnConfig;
            return criteriaColumn.criteriaName;
        }

        const standardColumn = column as StandardColumnConfig;
        
        switch (standardColumn.type) {
            case 'source':
                return t('tenders.columns.columnTypes.source');
            case 'name':
                return t('tenders.columns.columnTypes.name');
            case 'organization':
                return t('tenders.columns.columnTypes.organization');
            case 'publication_date':
                return t('tenders.columns.columnTypes.publication_date');
            case 'deadline_progress':
                return t('tenders.columns.columnTypes.deadline_progress');
            case 'submission_deadline':
                return t('tenders.columns.columnTypes.submission_deadline');
            case 'board_status':
                return t('tenders.columns.columnTypes.board_status');
            case 'score':
                return t('tenders.columns.columnTypes.score');
            case 'actions':
                return t('tenders.columns.columnTypes.actions');
            default:
                return standardColumn.label || standardColumn.id;
        }
    };

    useEffect(() => {
        if (isOpen) {
            setDraftColumns(columns.map(c => ({ ...c })));
            setSearchCriteria('');
            setSaveError(null);
            setSaveSuccess(false);
        }
    }, [isOpen, columns]);

    const visibleDraftCount = draftColumns.filter(c => c.visible).length;
    const addedCriteriaIds = draftColumns
        .filter(isCriteriaColumn)
        .map(col => (col as CriteriaColumnConfig).criteriaId);

    const filteredAvailableCriteria = availableCriteria
        .filter(c => !addedCriteriaIds.includes(c.id))
        .filter(c =>
            !searchCriteria ||
            c.name.toLowerCase().includes(searchCriteria.toLowerCase()) ||
            c.description?.toLowerCase().includes(searchCriteria.toLowerCase())
        );

    const sortedDraft = [...draftColumns].sort((a, b) => a.order - b.order);

    // Column management functions
    const toggleDraftVisibility = (id: string) => {
        setDraftColumns(prev => {
            const next = prev.map(c =>
                c.id === id ? { ...c, visible: !c.visible } : c
            );
            const nextVisibleCount = next.filter(c => c.visible).length;

            if (nextVisibleCount < MIN_VISIBLE) {
                return prev;
            }

            return next;
        });
    };

    const updateDraftDisplayMode = (columnId: string, displayMode: CriteriaDisplayMode) => {
        setDraftColumns(prev =>
            prev.map(col => {
                if (col.id === columnId && isCriteriaColumn(col)) {
                    return { ...col, displayMode };
                }
                return col;
            })
        );
    };

    const reorderDraft = (from: number, to: number) => {
        setDraftColumns(prev => {
            const arr = [...prev];
            const [moved] = arr.splice(from, 1);
            arr.splice(to, 0, moved);
            return arr.map((c, idx) => ({ ...c, order: idx }));
        });
    };

    const updateDraftWidth = (id: string, width: number) => {
        setDraftColumns(prev =>
            prev.map(c => {
                if (c.id !== id) return c;
                const clamped = Math.max(c.minWidth, Math.min(c.maxWidth, width));
                return { ...c, width: clamped };
            })
        );
    };

    const addDraftCriteria = (criteriaId: string, name: string) => {
        setDraftColumns(prev => {
            const existingColumn = prev.find(col =>
                col.type === 'criteria' &&
                isCriteriaColumn(col) &&
                (col as CriteriaColumnConfig).criteriaId === criteriaId
            );

            if (existingColumn) {
                return prev;
            }

            const newCol: CriteriaColumnConfig = {
                id: `criteria-${criteriaId}`,
                type: 'criteria',
                key: `criteria_analysis.${name}`,
                label: name,
                order: prev.length,
                visible: true,
                width: 160,
                minWidth: 120,
                maxWidth: 400,
                sortable: true,
                resizable: true,
                criteriaName: name,
                criteriaId: criteriaId,
                displayMode: 'text',
            } as CriteriaColumnConfig;
            return [...prev, newCol];
        });
    };

    const removeDraftCriteria = (criteriaId: string) => {
        setDraftColumns(prev => prev.filter(c => {
            if (!isCriteriaColumn(c)) return true;
            return (c as CriteriaColumnConfig).criteriaId !== criteriaId;
        }));
    };

    // Drag and drop handlers
    const handleDragStart = (e: React.DragEvent, idx: number) => {
        const target = e.target as HTMLElement;
        if (target.closest('input, button, label, select')) {
            e.preventDefault();
            return;
        }
        setDraggedIndex(idx);
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDragOver = (e: React.DragEvent, idx: number) => {
        e.preventDefault();
        setDragOverIndex(idx);
    };

    const finishDrag = () => {
        if (
            draggedIndex !== null &&
            dragOverIndex !== null &&
            draggedIndex !== dragOverIndex
        ) {
            reorderDraft(draggedIndex, dragOverIndex);
        }
        setDraggedIndex(null);
        setDragOverIndex(null);
    };

    // Save and reset functions
    const commitChanges = async () => {
        setIsSaving(true);
        setSaveError(null);
        setSaveSuccess(false);

        try {
            await onSaveConfiguration(draftColumns);
            setSaveSuccess(true);
            setTimeout(() => {
                onClose();
            }, 1000);
        } catch (error) {
            setSaveError(error instanceof Error ? error.message : t('tenders.columns.messages.saveFailed'));
        } finally {
            setIsSaving(false);
        }
    };

    const handleReset = async () => {
        setIsResetting(true);
        setSaveError(null);
        setSaveSuccess(false);

        try {
            await onResetToDefaults();
            onClose();
        } catch (error) {
            setSaveError(error instanceof Error ? error.message : t('tenders.columns.messages.resetFailed'));
        } finally {
            setIsResetting(false);
        }
    };

    const getDisplayModeIcon = (mode: CriteriaDisplayMode) => {
        switch (mode) {
            case 'text':
                return <Type className="h-3 w-3" />;
            case 'indicator':
                return <Eye className="h-3 w-3" />;
            default:
                return <Type className="h-3 w-3" />;
        }
    };

    // Render sidebar
    const renderSidebar = () => (
        <div className="w-64 border-r bg-gradient-to-b from-secondary/30 to-secondary/50 flex flex-col flex-shrink-0">
            <div className="p-4 border-b bg-gradient-to-r from-primary/5 to-primary/10 flex-shrink-0">
                <h3 className="font-medium text-sm text-primary uppercase tracking-wide">
                    {t('tenders.columns.tableSettings')}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                    {t('tenders.columns.personalizeView')}
                </p>
            </div>
            <nav className="flex-1 p-3 space-y-1 overflow-y-auto min-h-0">
                {SIDEBAR_ITEMS.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeSection === item.id;
                    
                    return (
                        <button
                            key={item.id}
                            onClick={() => setActiveSection(item.id)}
                            className={cn(
                                "w-full flex items-center gap-3 px-3 py-3 text-left rounded-xl transition-all duration-200 text-sm group",
                                isActive
                                    ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20"
                                    : "hover:bg-secondary-hover text-muted-foreground hover:text-foreground hover:shadow-sm"
                            )}
                        >
                            <div className={cn(
                                "p-2 rounded-lg transition-all duration-200",
                                isActive 
                                    ? "bg-primary-foreground/20 text-primary-foreground" 
                                    : "bg-primary/10 text-primary group-hover:bg-primary/20"
                            )}>
                                <Icon className="h-4 w-4 flex-shrink-0" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className={cn(
                                    "font-medium transition-colors",
                                    isActive ? "text-primary-foreground" : "text-foreground"
                                )}>
                                    {item.label}
                                </div>
                                <div className={cn(
                                    "text-xs opacity-80 truncate transition-colors",
                                    isActive ? "text-primary-foreground/80" : "text-muted-foreground"
                                )}>
                                    {item.description}
                                </div>
                            </div>
                        </button>
                    );
                })}
            </nav>
        </div>
    );

    // Render columns content
    const renderColumnsContent = () => (
        <div className="flex-1 flex flex-col min-h-0 h-full">
            {/* Header */}
            <div className="p-6 pb-4 border-b bg-gradient-to-r from-secondary/50 to-secondary/30 flex-shrink-0">
                <div className="flex items-center gap-3 mb-3">
                    <div className="p-2.5 bg-primary/10 text-primary rounded-xl shadow-sm">
                        <Table className="h-5 w-5" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-foreground">
                            {t('tenders.columns.manageColumns')}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            {t('tenders.columns.columnVisibilityDescription')}
                        </p>
                    </div>
                </div>
                
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">{t('tenders.columns.visible')}:</span>
                        <span className="font-medium text-foreground">
                            {visibleDraftCount}/{draftColumns.length}
                        </span>
                    </div>
                    
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                                setDraftColumns(prev =>
                                    prev.map(c => ({ ...c, visible: true }))
                                )
                            }
                            disabled={isSaving || isResetting}
                            className="h-8 text-xs"
                        >
                            {t('tenders.columns.showAll')}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                                setDraftColumns(prev => {
                                    const visibleCols = prev.filter(c => c.visible);
                                    const mustKeep = visibleCols.slice(0, MIN_VISIBLE);
                                    return prev.map(c =>
                                        mustKeep.includes(c)
                                            ? c
                                            : { ...c, visible: false }
                                    );
                                })
                            }
                            disabled={isSaving || isResetting}
                            className="h-8 text-xs"
                        >
                            {t('tenders.columns.hideAll')}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 flex gap-6 min-h-0">
                {/* Current Columns */}
                <div className="flex-1 flex flex-col min-h-0 p-6">
                    <h4 className="font-medium text-foreground mb-3 flex items-center gap-2">
                        <div className="w-2 h-2 bg-primary rounded-full"></div>
                        {t('tenders.columns.currentColumns')}
                    </h4>
                    
                    <ScrollArea className="flex-1 border rounded-xl bg-card/50 scrollbar-brown-thin">
                        <div className="p-4 space-y-3">
                            {sortedDraft.map((col, idx) => (
                                <div
                                    key={`column-${col.id}`}
                                    draggable={!isSaving && !isResetting}
                                    onDragStart={e => handleDragStart(e, idx)}
                                    onDragOver={e => handleDragOver(e, idx)}
                                    onDragEnd={finishDrag}
                                    onDrop={finishDrag}
                                    className={cn(
                                        'group flex items-center gap-4 p-4 border rounded-xl bg-card transition-all duration-200',
                                        col.visible ? 'opacity-100 shadow-sm' : 'opacity-60',
                                        dragOverIndex === idx && 'ring-2 ring-primary/30 scale-[1.02]',
                                        draggedIndex === idx && 'opacity-40 scale-95',
                                        (isSaving || isResetting) && 'cursor-not-allowed',
                                        !isSaving && !isResetting && 'hover:shadow-md cursor-grab active:cursor-grabbing'
                                    )}
                                >
                                    <div className="flex items-center gap-3 flex-1 min-w-0">
                                        <span className="text-muted-foreground group-hover:text-primary transition-colors">
                                            ≡
                                        </span>
                                        
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-medium text-sm truncate text-foreground">
                                                    {getTranslatedColumnLabel(col)}
                                                </span>
                                                {isCriteriaColumn(col) && (
                                                    <Badge variant="outline" className="text-xs bg-primary/10 text-primary border-primary/20">
                                                        {t('tenders.columns.criteria')}
                                                    </Badge>
                                                )}
                                            </div>
                                            
                                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                <span>{t('tenders.columns.order')}: {col.order + 1}</span>
                                                <span>{t('tenders.columns.width')}: {col.width}px</span>
                                            </div>

                                            {isCriteriaColumn(col) && (
                                                <button
                                                    type="button"
                                                    className={cn(
                                                        "mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200",
                                                        "border bg-gradient-to-r from-secondary/50 to-secondary/30 text-foreground",
                                                        "hover:from-primary/10 hover:to-primary/5 hover:border-primary/30 hover:shadow-sm"
                                                    )}
                                                    onClick={() => {
                                                        const currentMode = (col as CriteriaColumnConfig).displayMode;
                                                        const newMode = currentMode === 'text' ? 'indicator' : 'text';
                                                        updateDraftDisplayMode(col.id, newMode);
                                                    }}
                                                    disabled={isSaving || isResetting}
                                                >
                                                    {getDisplayModeIcon((col as CriteriaColumnConfig).displayMode)}
                                                    <span>
                                                        {(col as CriteriaColumnConfig).displayMode === 'text'
                                                            ? t('tenders.columns.displayMode.text')
                                                            : t('tenders.columns.displayMode.indicator')}
                                                    </span>
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <div className="flex items-center gap-2">
                                            <Label className="text-xs text-muted-foreground">{t('tenders.columns.widthShort')}:</Label>
                                            <Input
                                                type="number"
                                                value={col.width}
                                                min={col.minWidth}
                                                max={col.maxWidth}
                                                onChange={e => updateDraftWidth(col.id, parseInt(e.target.value, 10))}
                                                className="w-16 h-7 text-xs border-border/50"
                                                disabled={isSaving || isResetting}
                                            />
                                        </div>

                                        <Switch
                                            checked={col.visible}
                                            onCheckedChange={() => toggleDraftVisibility(col.id)}
                                            disabled={isSaving || isResetting}
                                        />

                                        {isCriteriaColumn(col) && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-destructive hover:text-destructive hover:bg-destructive/10 h-7 w-7 p-0"
                                                onClick={() => removeDraftCriteria((col as CriteriaColumnConfig).criteriaId)}
                                                disabled={isSaving || isResetting}
                                            >
                                                ×
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </div>

                {/* Add Criteria Section */}
                <div className="w-80 flex flex-col min-h-0 p-6 border-l">
                    <h4 className="font-medium text-foreground mb-3 flex items-center gap-2">
                        <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                        {t('tenders.columns.addCriteria')}
                    </h4>
                    
                    {availableCriteria.length > 3 && (
                        <Input
                            placeholder={t('tenders.columns.searchCriteria')}
                            value={searchCriteria}
                            onChange={e => setSearchCriteria(e.target.value)}
                            className="mb-4"
                            disabled={isSaving || isResetting}
                        />
                    )}

                    <ScrollArea className="flex-1 border rounded-xl bg-card/50 scrollbar-brown-thin">
                        <div className="p-4">
                            {filteredAvailableCriteria.length ? (
                                <div className="space-y-3">
                                    {filteredAvailableCriteria.map(c => (
                                        <div
                                            key={`criteria-${c.id}`}
                                            className="group flex items-center justify-between p-3 border rounded-lg bg-card hover:bg-secondary/50 hover:border-primary/20 transition-all duration-200"
                                        >
                                            <div className="flex-1 min-w-0 pr-3">
                                                <p className="font-medium text-sm text-foreground truncate">
                                                    {c.name}
                                                </p>
                                                {c.description && (
                                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                        {c.description}
                                                    </p>
                                                )}
                                            </div>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => addDraftCriteria(c.id, c.name)}
                                                disabled={isSaving || isResetting}
                                                className="h-8 text-xs bg-primary/5 hover:bg-primary/10 border-primary/20 text-primary hover:text-primary"
                                            >
                                                {t('tenders.columns.add')}
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center text-muted-foreground py-12 text-sm">
                                    <div className="p-4 bg-secondary/30 rounded-lg">
                                        {availableCriteria.length === 0 
                                            ? t('tenders.columns.noCriteriaAvailable')
                                            : t('tenders.columns.allCriteriaAdded')}
                                    </div>
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </div>
            </div>
        </div>
    );

    // Render data filters content
    const renderDataFiltersContent = () => (
        <div className="flex-1 flex flex-col min-h-0 h-full">
            {/* Header Section */}
            <div className="p-6 pb-4 border-b bg-gradient-to-r from-secondary/50 to-secondary/30 flex-shrink-0">
                <div className="flex items-center gap-3 mb-3">
                    <div className="p-2.5 bg-primary/10 text-primary rounded-xl shadow-sm">
                        <Filter className="h-5 w-5" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-foreground">{t('tenders.columns.dataFilters')}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            {t('tenders.columns.dataFiltersControlDescription')}
                        </p>
                    </div>
                </div>
                
                {/* Active filters summary */}
                <div className="flex items-center gap-2 mt-4">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {t('tenders.columns.activeFilters')}:
                    </span>
                    <div className="flex gap-2">
                        {includeHistorical && (
                            <div className="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-bold rounded-full text-xs font-medium">
                                <Clock className="h-3 w-3" />
                                {t('tenders.columns.historical')}
                            </div>
                        )}
                        {includeFiltered && (
                            <div className="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-bold rounded-full text-xs font-medium">
                                <Database className="h-3 w-3" />
                                {t('tenders.columns.filtered')}
                            </div>
                        )}
                        {includeExternal && (
                            <div className="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary rounded-full text-xs font-medium">
                                <Globe className="h-3 w-3" />
                                {t('tenders.columns.external')}
                            </div>
                        )}
                        {!includeHistorical && !includeFiltered && !includeExternal && (
                            <span className="text-xs text-muted-foreground italic">{t('tenders.columns.standardDataOnly')}</span>
                        )}
                    </div>
                </div>
            </div>

            {/* Scrollable Content - Takes remaining height */}
            <div className="flex-1 overflow-hidden min-h-0">
                <ScrollArea className="h-full scrollbar-brown-thin">
                    <div className="p-6 space-y-5">
                        {/* Historical Tenders */}
                        <div className={cn(
                            "group relative overflow-hidden transition-all duration-300 ease-out",
                            "border-2 rounded-xl shadow-sm hover:shadow-lg",
                            includeHistorical 
                                ? "border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100/50 shadow-blue-100/50" 
                                : "border-border bg-card hover:border-blue-200/60 hover:bg-blue-50/30"
                        )}>
                            <div className="p-5">
                                <div className="flex items-start gap-4">
                                    <div className={cn(
                                        "flex-shrink-0 p-3 rounded-xl transition-all duration-300",
                                        includeHistorical 
                                            ? "bg-blue-500 text-white shadow-lg shadow-blue-500/25" 
                                            : "bg-blue-100 text-blue-600 group-hover:bg-blue-200 group-hover:scale-105"
                                    )}>
                                        <Clock className="h-6 w-6" />
                                    </div>
                                    
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-base font-semibold text-foreground">
                                                {t('tenders.columns.historicalTenders')}
                                            </h4>
                                            <Switch
                                                checked={includeHistorical}
                                                onCheckedChange={onToggleHistorical}
                                                className="data-[state=checked]:bg-blue-500"
                                            />
                                        </div>
                                        
                                        <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                                            {t('tenders.columns.historicalDescription')}
                                        </p>
                                        
                                        {includeHistorical && (
                                            <div className="mt-4 p-3 bg-white/60 backdrop-blur-sm rounded-lg border border-blue-200/50">
                                                <div className="flex items-start gap-2">
                                                    <div className="w-1.5 h-1.5 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                                                    <p className="text-xs text-blue-700 leading-relaxed">
                                                        {t('tenders.columns.historicalNote')}
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                            
                            {/* Subtle gradient overlay for visual depth */}
                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-transparent to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-xl"></div>
                        </div>

                        {/* Filtered Tenders */}
                        <div className={cn(
                            "group relative overflow-hidden transition-all duration-300 ease-out",
                            "border-2 rounded-xl shadow-sm hover:shadow-lg",
                            includeFiltered 
                                ? "border-amber-200 bg-gradient-to-br from-amber-50 to-amber-100/50 shadow-amber-100/50" 
                                : "border-border bg-card hover:border-amber-200/60 hover:bg-amber-50/30"
                        )}>
                            <div className="p-5">
                                <div className="flex items-start gap-4">
                                    <div className={cn(
                                        "flex-shrink-0 p-3 rounded-xl transition-all duration-300",
                                        includeFiltered 
                                            ? "bg-amber-500 text-white shadow-lg shadow-amber-500/25" 
                                            : "bg-amber-100 text-amber-600 group-hover:bg-amber-200 group-hover:scale-105"
                                    )}>
                                        <Database className="h-6 w-6" />
                                    </div>
                                    
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-base font-semibold text-foreground">
                                                {t('tenders.columns.filteredTenders')}
                                            </h4>
                                            <Switch
                                                checked={includeFiltered}
                                                onCheckedChange={onToggleFiltered}
                                                className="data-[state=checked]:bg-amber-500"
                                            />
                                        </div>
                                        
                                        <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                                            {t('tenders.columns.filteredDescription')}
                                        </p>
                                        
                                        {includeFiltered && (
                                            <div className="mt-4 p-3 bg-white/60 backdrop-blur-sm rounded-lg border border-amber-200/50">
                                                <div className="flex items-start gap-2">
                                                    <div className="w-1.5 h-1.5 bg-amber-500 rounded-full mt-2 flex-shrink-0"></div>
                                                    <p className="text-xs text-amber-700 leading-relaxed">
                                                        {t('tenders.columns.filteredNote')}
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                            
                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-transparent to-amber-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-xl"></div>
                        </div>

                        {/* External Sources */}
                        {showIncludeExternal && (
                            <div className={cn(
                                "group relative overflow-hidden transition-all duration-300 ease-out",
                                "border-2 rounded-xl shadow-sm hover:shadow-lg",
                                includeExternal 
                                    ? "border-purple-200 bg-gradient-to-br from-purple-50 to-purple-100/50 shadow-purple-100/50" 
                                    : "border-border bg-card hover:border-purple-200/60 hover:bg-purple-50/30"
                            )}>
                                <div className="p-5">
                                    <div className="flex items-start gap-4">
                                        <div className={cn(
                                            "flex-shrink-0 p-3 rounded-xl transition-all duration-300",
                                            includeExternal 
                                                ? "bg-purple-500 text-white shadow-lg shadow-purple-500/25" 
                                                : "bg-purple-100 text-purple-600 group-hover:bg-purple-200 group-hover:scale-105"
                                        )}>
                                            <Globe className="h-6 w-6" />
                                        </div>
                                        
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-2">
                                                <h4 className="text-base font-semibold text-foreground">
                                                    {t('tenders.columns.externalSources')}
                                                </h4>
                                                <Switch
                                                    checked={includeExternal}
                                                    onCheckedChange={onToggleExternal}
                                                    className="data-[state=checked]:bg-purple-500"
                                                />
                                            </div>
                                            
                                            <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                                                {t('tenders.columns.externalDescription')}
                                            </p>
                                            
                                            {includeExternal && (
                                                <div className="mt-4 p-3 bg-white/60 backdrop-blur-sm rounded-lg border border-purple-200/50">
                                                    <div className="flex items-start gap-2">
                                                        <div className="w-1.5 h-1.5 bg-purple-500 rounded-full mt-2 flex-shrink-0"></div>
                                                        <p className="text-xs text-purple-700 leading-relaxed">
                                                            {t('tenders.columns.externalNote')}
                                                        </p>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                
                                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-transparent to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-xl"></div>
                            </div>
                        )}
                    </div>

                    {/* Footer info */}
                    <div className="px-6 pb-6">
                        <div className="p-4 bg-gradient-to-r from-primary/5 to-primary/10 rounded-xl border border-primary/20">
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-primary/10 text-primary rounded-lg flex-shrink-0">
                                    <AlertCircle className="h-4 w-4" />
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-foreground mb-1">
                                        {t('tenders.columns.autoRefresh')}
                                    </p>
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                        {t('tenders.columns.autoRefreshDescription')}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </ScrollArea>
            </div>
        </div>
    );

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-6xl h-[85vh] p-0 gap-0 flex flex-col overflow-hidden">
                <DialogHeader className="p-6 pb-4 border-b bg-gradient-to-r from-secondary/30 to-secondary/20 flex-shrink-0">
                    <DialogTitle className="text-lg font-semibold text-foreground">
                        {t('tenders.columns.tableSettings')}
                    </DialogTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                        {t('tenders.columns.customizeDescription')}
                    </p>
                </DialogHeader>

                {/* Error/Success Messages */}
                {(saveError || saveSuccess) && (
                    <div className="px-6 py-4 border-b flex-shrink-0">
                        {saveError && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{saveError}</AlertDescription>
                            </Alert>
                        )}
                        {saveSuccess && (
                            <Alert className="border-green-200 bg-green-50">
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                                <AlertDescription className="text-green-800">
                                    {t('tenders.columns.tableLayoutSaved')}
                                </AlertDescription>
                            </Alert>
                        )}
                    </div>
                )}

                <div className="flex flex-1 min-h-0 overflow-hidden">
                    {/* Sidebar */}
                    {renderSidebar()}

                    {/* Main Content - Fixed height container */}
                    <div className="flex-1 flex flex-col min-h-0 h-full">
                        {activeSection === 'columns' && renderColumnsContent()}
                        {activeSection === 'dataFilters' && renderDataFiltersContent()}
                    </div>
                </div>

                {/* Footer */}
                <Separator className="flex-shrink-0" />
                <div className="flex justify-between items-center p-6 bg-gradient-to-r from-secondary/30 to-secondary/20 flex-shrink-0">
                    <Button
                        variant="destructive"
                        onClick={handleReset}
                        disabled={isResetting || isSaving}
                    >
                        {isResetting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                {t('tenders.columns.resetting')}
                            </>
                        ) : (
                            t('tenders.columns.resetDefaults')
                        )}
                    </Button>

                    <div className="flex items-center gap-3">
                        {activeSection === 'columns' && visibleDraftCount < MIN_VISIBLE && (
                            <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 px-3 py-2 rounded-lg">
                                <AlertCircle className="h-4 w-4" />
                                <span>{t('tenders.columns.selectMinColumns', { min: MIN_VISIBLE })}</span>
                            </div>
                        )}
                        <Button
                            variant="outline"
                            onClick={onClose}
                            disabled={isSaving || isResetting}
                        >
                            {t('common.cancel')}
                        </Button>
                        {activeSection === 'columns' && (
                            <Button
                                onClick={commitChanges}
                                disabled={visibleDraftCount < MIN_VISIBLE || isSaving || isResetting}
                                className="bg-primary hover:bg-primary-hover"
                            >
                                {isSaving ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        {t('tenders.columns.saving')}
                                    </>
                                ) : (
                                    t('tenders.columns.saveChanges')
                                )}
                            </Button>
                        )}
                        {activeSection === 'dataFilters' && (
                            <Button 
                                onClick={onClose}
                                className="bg-primary hover:bg-primary-hover"
                            >
                                {t('tenders.columns.done')}
                            </Button>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};
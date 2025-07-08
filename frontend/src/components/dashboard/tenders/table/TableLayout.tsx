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
        },
        {
            id: 'dataFilters',
            label: t('tenders.columns.dataFilters'),
            icon: Filter,
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


    // Alternative even more minimalistic version (Tab-like approach):
    const renderSidebar = () => (
        <div className="w-56 border-r bg-sidebar flex flex-col flex-shrink-0">
            <div className="p-3">
                {/* Tab-style navigation */}
                <div className="bg-sidebar-accent/30 rounded-lg p-1">
                    {SIDEBAR_ITEMS.map((item) => {
                        const Icon = item.icon;
                        const isActive = activeSection === item.id;

                        return (
                            <button
                                key={item.id}
                                onClick={() => setActiveSection(item.id)}
                                className={cn(
                                    "w-full flex items-center gap-2 px-3 py-2.5 text-left rounded-md transition-all duration-200 text-sm",
                                    isActive
                                        ? "bg-background text-foreground shadow-sm"
                                        : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                                )}
                            >
                                <Icon className="size-4 flex-shrink-0" />
                                <span className="font-medium truncate">
                                    {item.label}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );

    // Update the renderColumnsContent function in your TableLayout.tsx
    // Replace the existing column rendering section with this:

    // Note: This uses Tailwind's line-clamp utilities for controlled text truncation

    const renderColumnsContent = () => (
        <div className="flex-1 flex flex-col min-h-0 h-full">
            {/* Header */}
            <div className="p-6 pb-4 border-b border-sidebar-border bg-sidebar/30 flex-shrink-0">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-secondary text-muted-foreground rounded-md shadow-sm">
                        <Table className="h-4 w-4" />
                    </div>
                    <div>
                        <h3 className="text-md font-semibold text-foreground">
                            {t('tenders.columns.manageColumns')}
                        </h3>
                        <p className="text-sm text-muted-foreground">
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
                    <h4 className="font-medium text-foreground text-bold flex items-center gap-2">
                        {t('tenders.columns.currentColumns')}
                    </h4>

                    <ScrollArea className="flex-1 border rounded-md bg-card/50 scrollbar-brown-thin">
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
                                        'group flex items-center gap-4 p-4 border rounded-md bg-card transition-all duration-200',
                                        col.visible ? 'opacity-100 shadow-sm' : 'opacity-60',
                                        dragOverIndex === idx && 'ring-2 ring-primary/30 scale-[1.02]',
                                        draggedIndex === idx && 'opacity-40 scale-95',
                                        (isSaving || isResetting) && 'cursor-not-allowed',
                                        !isSaving && !isResetting && 'hover:shadow-md cursor-grab active:cursor-grabbing'
                                    )}
                                >
                                    {/* Left side: Drag handle + content */}
                                    <div className="flex items-center gap-3 flex-1 items-center">
                                        <span className="text-muted-foreground group-hover:text-muted-foreground transition-colors flex-shrink-0">
                                            ≡
                                        </span>

                                        <div className="flex-1 items-center">
                                            <div className="flex items-start gap-2 mb-1">
                                                <div className="flex-1 items-center">
                                                    <span className={cn(
                                                        "font-medium text-sm text-foreground leading-relaxed",
                                                        // Show up to 2 lines for criteria columns, then truncate with ellipsis
                                                        isCriteriaColumn(col)
                                                            ? "line-clamp-2 break-words"
                                                            : "truncate"
                                                    )}>
                                                        {getTranslatedColumnLabel(col)}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                <span>{t('tenders.columns.order')}: {col.order + 1}</span>
                                                <span>{t('tenders.columns.width')}: {col.width}px</span>
                                            </div>

                                            {isCriteriaColumn(col) && (
                                                <div className="flex items-center gap-2 mt-2">
                                                    <Badge variant="outline" className="text-xs bg-secondary-hover/10 text-muted-foreground border-primary/20">
                                                        {t('tenders.columns.criteria')}
                                                    </Badge>
                                                    <button
                                                        type="button"
                                                        className={cn(
                                                            "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200",
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
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Right side: Controls - properly centered */}
                                    <div className="flex items-center gap-3 flex-shrink-0">
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

                {/* Add Criteria Section - Also with text wrapping */}
                <div className="w-80 flex flex-col min-h-0 p-6 border-l">
                    <h4 className="font-medium text-foreground text-bold flex items-center gap-2">
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

                    <ScrollArea className="flex-1 border rounded-md bg-card/50 scrollbar-brown-thin">
                        <div className="p-4">
                            {filteredAvailableCriteria.length ? (
                                <div className="space-y-3">
                                    {filteredAvailableCriteria.map(c => (
                                        <div
                                            key={`criteria-${c.id}`}
                                            className="group flex items-center justify-between p-3 border rounded-lg bg-card hover:bg-secondary/50 hover:border-primary/20 transition-all duration-200"
                                        >
                                            <div className="flex-1 items-center pr-3">
                                                <p className="font-medium text-sm text-foreground leading-relaxed line-clamp-2 break-words">
                                                    {c.name}
                                                </p>
                                            </div>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => addDraftCriteria(c.id, c.name)}
                                                disabled={isSaving || isResetting}
                                                className="h-8 text-xs bg-secondary-hover/5 hover:bg-secondary-hover/10 border-primary/20 text-muted-foreground hover:text-muted-foreground flex-shrink-0"
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
    // Render data filters content with beige/brown color scheme
    // Replace the renderDataFiltersContent function in TableLayout.tsx with this:

    const renderDataFiltersContent = () => (
        <div className="flex-1 flex flex-col min-h-0 h-full">
            {/* Header Section */}
            <div className="p-6 pb-4 border-b border-sidebar-border bg-sidebar/30 flex-shrink-0">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-secondary text-muted-foreground rounded-md shadow-sm">
                        <Filter className="h-4 w-4" />
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
                            <div className="flex items-center gap-1 px-2 py-1 bg-secondary text-muted-foreground rounded-full text-xs font-medium border border-primary/20">
                                <Clock className="h-3 w-3" />
                                {t('tenders.columns.historicalTenders')}
                            </div>
                        )}
                        {includeFiltered && (
                            <div className="flex items-center gap-1 px-2 py-1 bg-secondary text-muted-foreground rounded-full text-xs font-medium border border-primary/20">
                                <Database className="h-3 w-3" />
                                {t('tenders.columns.filteredTenders')}
                            </div>
                        )}
                        {includeExternal && (
                            <div className="flex items-center gap-1 px-2 py-1 bg-secondary text-muted-foreground rounded-full text-xs font-medium border border-primary/20">
                                <Globe className="h-3 w-3" />
                                {t('tenders.columns.externalSources')}
                            </div>
                        )}
                        {!includeHistorical && !includeFiltered && !includeExternal && (
                            <span className="text-xs text-muted-foreground italic">{t('tenders.columns.standardDataOnly')}</span>
                        )}
                    </div>
                </div>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-hidden min-h-0">
                <ScrollArea className="h-full scrollbar-brown-thin">
                    <div className="p-6 space-y-4">
                        {/* Historical Tenders */}
                        <div className={cn(
                            "group flex items-start gap-4 p-4 border rounded-md bg-card transition-all shadow-sm duration-200",
                            includeHistorical ? 'opacity-100 shadow-sm' : 'opacity-100',
                            'hover:shadow-md'
                        )}>
                            <div className={cn(
                                "flex-shrink-0 p-3 rounded-md transition-all duration-200",
                                includeHistorical
                                    ? "bg-foreground text-secondary-hover shadow-sm"
                                    : "bg-secondary text-muted-foreground group-hover:bg-secondary-hover"
                            )}>
                                <Clock className="h-4 w-4" />
                            </div>

                            <div className="flex-1 items-center">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-base font-semibold text-foreground">
                                        {t('tenders.columns.historicalTenders')}
                                    </h4>
                                    <Switch
                                        checked={includeHistorical}
                                        onCheckedChange={onToggleHistorical}
                                        className="data-[state=checked]:bg-primary"
                                    />
                                </div>

                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {t('tenders.columns.historicalDescription')}
                                </p>

                                {includeHistorical && (
                                    <div className="mt-4 p-3 bg-secondary/50 rounded-lg border">
                                        <div className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 bg-secondary-hover rounded-full mt-2 flex-shrink-0"></div>
                                            <p className="text-xs text-muted-foreground leading-relaxed">
                                                {t('tenders.columns.historicalNote')}
                                            </p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Filtered Tenders */}
                        <div className={cn(
                            "group flex items-start gap-4 p-4 border rounded-md bg-card transition-all shadow-sm duration-200",
                            includeFiltered ? 'opacity-100 shadow-sm' : 'opacity-100',
                            'hover:shadow-md'
                        )}>
                            <div className={cn(
                                "flex-shrink-0 p-3 rounded-md transition-all duration-200",
                                includeFiltered
                                    ? "bg-foreground text-secondary-hover shadow-sm"
                                    : "bg-secondary text-muted-foreground group-hover:bg-secondary-hover"
                            )}>
                                <Database className="h-4 w-4" />
                            </div>

                            <div className="flex-1 items-center">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-base font-semibold text-foreground">
                                        {t('tenders.columns.filteredTenders')}
                                    </h4>
                                    <Switch
                                        checked={includeFiltered}
                                        onCheckedChange={onToggleFiltered}
                                        className="data-[state=checked]:bg-primary"
                                    />
                                </div>

                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {t('tenders.columns.filteredDescription')}
                                </p>

                                {includeFiltered && (
                                    <div className="mt-4 p-3 bg-secondary/50 rounded-lg border">
                                        <div className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 bg-secondary-hover rounded-full mt-2 flex-shrink-0"></div>
                                            <p className="text-xs text-muted-foreground leading-relaxed">
                                                {t('tenders.columns.filteredNote')}
                                            </p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* External Sources */}
                        {showIncludeExternal && (
                            <div className={cn(
                                "group flex items-start gap-4 p-4 border rounded-md bg-card shadow-sm transition-all duration-200",
                                includeExternal ? 'opacity-100 shadow-sm' : 'opacity-100',
                                'hover:shadow-md'
                            )}>
                                <div className={cn(
                                    "flex-shrink-0 p-3 rounded-md transition-all duration-200",
                                    includeExternal
                                        ? "bg-foreground text-secondary-hover shadow-sm"
                                        : "bg-secondary text-muted-foreground group-hover:bg-secondary-hover"
                                )}>
                                    <Globe className="h-4 w-4" />
                                </div>

                                <div className="flex-1 items-center">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-base font-semibold text-foreground">
                                            {t('tenders.columns.externalSources')}
                                        </h4>
                                        <Switch
                                            checked={includeExternal}
                                            onCheckedChange={onToggleExternal}
                                            className="data-[state=checked]:bg-primary"
                                        />
                                    </div>

                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {t('tenders.columns.externalDescription')}
                                    </p>

                                    {includeExternal && (
                                        <div className="mt-4 p-3 bg-secondary/50 rounded-lg border">
                                            <div className="flex items-start gap-2">
                                                <div className="w-1.5 h-1.5 bg-secondary-hover rounded-full mt-2 flex-shrink-0"></div>
                                                <p className="text-xs text-muted-foreground leading-relaxed">
                                                    {t('tenders.columns.externalNote')}
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Footer info */}
                    <div className="px-6 pb-6">
                        <div className="p-4 bg-card rounded-md border shadow-sm">
                            <div className="flex items-start gap-3">
                                <div className="p-2 bg-secondary-hover/10 text-muted-foreground rounded-lg flex-shrink-0">
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
            <DialogContent className="max-w-6xl h-[85vh] p-0 gap-0 flex flex-col overflow-hidden bg-background">
                <DialogHeader className="p-6 pb-4 border-b border-sidebar-border bg-sidebar/50 flex-shrink-0">
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

                <div className="flex flex-1 min-h-0 overflow-hidden bg-background">
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
                <div className="flex justify-between items-center p-6 bg-sidebar/30 border-t border-sidebar-border flex-shrink-0">
                    <Button
                        variant="outline"
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
                                className="bg-primary hover:bg-foreground"
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
                                className="bg-primary hover:bg-foreground"
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
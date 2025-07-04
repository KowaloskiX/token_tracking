import React, { useEffect, useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
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
import { Loader2, AlertCircle, CheckCircle2, Eye, Type } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
    ColumnConfig,
    CriteriaColumnConfig,
    isCriteriaColumn,
    CriteriaDisplayMode,
} from '@/types/tableColumns';
import { useTendersTranslations, useTranslations } from '@/hooks/useTranslations';
import { cn } from '@/lib/utils';

interface TableLayoutProps {
    isOpen: boolean;
    onClose: () => void;
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
    onUpdateCriteriaDisplayMode: (columnId: string, displayMode: CriteriaDisplayMode) => void; // NEW: Add this prop
    onSaveConfiguration: (columns: ColumnConfig[]) => Promise<void>;
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
    onUpdateCriteriaDisplayMode, // NEW: Accept this prop
    onSaveConfiguration,
}) => {
    const t = useTranslations();
    const tTenders = useTendersTranslations();

    const MIN_VISIBLE = 3;
    const MAX_VISIBLE = 10;

    const [draftColumns, setDraftColumns] = useState<ColumnConfig[]>([]);
    const [searchCriteria, setSearchCriteria] = useState('');
    const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
    const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [isResetting, setIsResetting] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);

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

    const toggleDraftVisibility = (id: string) => {
        setDraftColumns(prev => {
            const next = prev.map(c =>
                c.id === id ? { ...c, visible: !c.visible } : c
            );
            const nextVisibleCount = next.filter(c => c.visible).length;

            // Prevent going below minimum or above maximum visible columns
            if (nextVisibleCount < MIN_VISIBLE || nextVisibleCount > MAX_VISIBLE) {
                return prev;
            }

            return next;
        });
    };

    // NEW: Function to update display mode in draft
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
                // clamp to [minWidth, maxWidth]
                const clamped = Math.max(c.minWidth, Math.min(c.maxWidth, width));
                return { ...c, width: clamped };
            })
        );
    };

    const addDraftCriteria = (criteriaId: string, name: string) => {
        setDraftColumns(prev => {
            // Check if this criteria column already exists
            const existingColumn = prev.find(col =>
                col.type === 'criteria' &&
                isCriteriaColumn(col) &&
                (col as CriteriaColumnConfig).criteriaId === criteriaId
            );

            if (existingColumn) {
                console.log(`Draft criteria column for ${name} already exists, skipping`);
                return prev;
            }

            // Check if adding this column would exceed the maximum visible limit
            const currentVisibleCount = prev.filter(c => c.visible).length;
            if (currentVisibleCount >= MAX_VISIBLE) {
                console.log(`Cannot add criteria column: maximum visible columns (${MAX_VISIBLE}) reached`);
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
                displayMode: 'text', // NEW: Default to text mode
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

    const commitChanges = async () => {
        setIsSaving(true);
        setSaveError(null);
        setSaveSuccess(false);

        try {
            console.log('Saving table layout configuration...');

            // First, save the configuration to backend
            await onSaveConfiguration(draftColumns);

            console.log('Table layout saved successfully');
            setSaveSuccess(true);

            // Close the dialog after a brief success message
            setTimeout(() => {
                onClose();
            }, 1000);
        } catch (error) {
            console.error('Failed to save table layout:', error);
            setSaveError(error instanceof Error ? error.message : 'Failed to save table layout');
        } finally {
            setIsSaving(false);
        }
    };

    const handleReset = async () => {
        setIsResetting(true);
        setSaveError(null);
        setSaveSuccess(false);

        try {
            console.log('Resetting table layout to defaults...');
            await onResetToDefaults();
            console.log('Table layout reset successfully');
            onClose();
        } catch (error) {
            console.error('Failed to reset table layout:', error);
            setSaveError(error instanceof Error ? error.message : 'Failed to reset table layout');
        } finally {
            setIsResetting(false);
        }
    };
    // NEW: Helper function to get display mode icon
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

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-7xl max-h-[90vh] flex flex-col">
                <DialogHeader className="pb-4 border-b">
                    <DialogTitle className="text-lg font-semibold">
                        {tTenders('columns.manageColumns')}
                        <span className="ml-2 text-sm font-normal text-muted-foreground">
                            ({visibleDraftCount}/{draftColumns.length} {tTenders('columns.visible')}, max {MAX_VISIBLE})
                        </span>
                    </DialogTitle>
                </DialogHeader>

                {/* Error/Success Messages */}
                {(saveError || saveSuccess) && (
                    <div className="px-1">
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

                <div className="flex-1 grid grid-cols-1 lg:grid-cols-5 gap-6 min-h-0">
                    {/* Current Columns - Takes up 3/5 of the width */}
                    <div className="lg:col-span-3 flex flex-col min-h-0">
                        <Card className="flex-1 flex flex-col overflow-hidden border">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base font-medium">
                                    {tTenders('columns.currentColumns')}
                                </CardTitle>
                                <div className="mt-2 flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                            setDraftColumns(prev => {
                                                // Get columns sorted by importance (order)
                                                const sortedCols = [...prev].sort((a, b) => a.order - b.order);

                                                // Show first MAX_VISIBLE columns, hide the rest
                                                return prev.map(c => {
                                                    const index = sortedCols.findIndex(sc => sc.id === c.id);
                                                    return { ...c, visible: index < MAX_VISIBLE };
                                                });
                                            })
                                        }
                                        disabled={isSaving || isResetting}
                                    >
                                        {tTenders('columns.showAll')} (max {MAX_VISIBLE})
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
                                    >
                                        {tTenders('columns.hideAll')}
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="flex-1 overflow-hidden">
                                <ScrollArea className="h-full pr-3">
                                    <ul className="space-y-2 pb-2">
                                        {sortedDraft.map((col, idx) => (
                                            <li
                                                key={`column-${col.id}`}
                                                draggable={!isSaving && !isResetting}
                                                onDragStart={e => handleDragStart(e, idx)}
                                                onDragOver={e => handleDragOver(e, idx)}
                                                onDragEnd={finishDrag}
                                                onDrop={finishDrag}
                                                className={cn(
                                                    'relative flex items-center gap-4 rounded-lg border px-3 py-2 bg-card transition-colors',
                                                    col.visible ? 'opacity-100' : 'opacity-60',
                                                    dragOverIndex === idx && 'ring-2 ring-primary/30',
                                                    draggedIndex === idx && 'opacity-40',
                                                    (isSaving || isResetting) && 'cursor-not-allowed'
                                                )}
                                            >
                                                <span className="select-none cursor-grab text-muted-foreground">≡</span>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <span
                                                            className="font-medium text-sm truncate max-w-[160px]"
                                                            title={col.label || col.id}
                                                        >
                                                            {col.label || col.id}
                                                        </span>
                                                        {isCriteriaColumn(col) && (
                                                            <Badge variant="outline" className="text-xs">
                                                                {tTenders('columns.criteria')}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <div className="mt-1 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                                                        <span>
                                                            {tTenders('columns.order')}: {col.order + 1}
                                                        </span>
                                                        <span>
                                                            {tTenders('columns.width')}: {col.width}px
                                                        </span>
                                                        {/* NEW: Clickable display mode badge for criteria columns */}
                                                        {isCriteriaColumn(col) && (
                                                            <button
                                                                type="button"
                                                                className={cn(
                                                                    "inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-all duration-200",
                                                                    "border border-secondary-border bg-secondary/50 text-secondary-foreground",
                                                                    "hover:bg-secondary hover:border-primary/20 hover:shadow-sm",
                                                                    "active:scale-95 active:bg-secondary-hover",
                                                                    "disabled:opacity-50 disabled:cursor-not-allowed",
                                                                    (col as CriteriaColumnConfig).displayMode === 'text'
                                                                        ? "ring-1 ring-primary/10"
                                                                        : ""
                                                                )}
                                                                onClick={() => {
                                                                    const currentMode = (col as CriteriaColumnConfig).displayMode;
                                                                    const newMode = currentMode === 'text' ? 'indicator' : 'text';
                                                                    updateDraftDisplayMode(col.id, newMode);
                                                                }}
                                                                disabled={isSaving || isResetting}
                                                                title={`Current: ${(col as CriteriaColumnConfig).displayMode === 'text' ? 'Text summary' : 'Met/Not met indicators'}. Click to switch.`}
                                                            >
                                                                <span className="text-primary/70">
                                                                    {getDisplayModeIcon((col as CriteriaColumnConfig).displayMode)}
                                                                </span>
                                                                <span className="text-foreground font-semibold">
                                                                    {
                                                                        (col as CriteriaColumnConfig).displayMode === 'text'
                                                                            ? tTenders('columns.displayMode.text')
                                                                            : tTenders('columns.displayMode.indicator')
                                                                    }
                                                                </span>
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Column configuration controls */}
                                                <div className="flex items-center gap-2">
                                                    {/* Width input */}
                                                    <div className="flex items-center gap-1">
                                                        <Label htmlFor={`w-${col.id}`} className="text-xs whitespace-nowrap">
                                                            {tTenders('columns.widthShort')}:
                                                        </Label>
                                                        <Input
                                                            id={`w-${col.id}`}
                                                            type="number"
                                                            value={col.width}
                                                            min={col.minWidth}
                                                            max={col.maxWidth}
                                                            onChange={e => updateDraftWidth(col.id, parseInt(e.target.value, 10))}
                                                            className="w-16 h-7 text-xs"
                                                            disabled={isSaving || isResetting}
                                                        />
                                                    </div>

                                                    {/* Visibility toggle */}
                                                    <Switch
                                                        checked={col.visible}
                                                        onCheckedChange={() => toggleDraftVisibility(col.id)}
                                                        disabled={
                                                            isSaving ||
                                                            isResetting ||
                                                            (!col.visible && visibleDraftCount >= MAX_VISIBLE)
                                                        }
                                                    />

                                                    {/* Remove button for criteria columns */}
                                                    {isCriteriaColumn(col) && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="text-destructive hover:text-destructive"
                                                            onClick={() => removeDraftCriteria((col as CriteriaColumnConfig).criteriaId)}
                                                            disabled={isSaving || isResetting}
                                                        >
                                                            {tTenders('columns.remove')}
                                                        </Button>
                                                    )}
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Add Criteria Section - Takes up 2/5 of the width */}
                    <div className="lg:col-span-2 flex flex-col min-h-0">
                        <Card className="flex-1 flex flex-col overflow-hidden border">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base font-medium">
                                    {tTenders('columns.addCriteria')}
                                </CardTitle>
                                {availableCriteria.length > 3 && (
                                    <Input
                                        placeholder={tTenders('columns.searchCriteria')}
                                        value={searchCriteria}
                                        onChange={e => setSearchCriteria(e.target.value)}
                                        className="mt-2 h-8"
                                        disabled={isSaving || isResetting}
                                    />
                                )}
                            </CardHeader>
                            <CardContent className="flex-1 overflow-hidden">
                                <ScrollArea className="h-full pr-3">
                                    {filteredAvailableCriteria.length ? (
                                        <ul className="space-y-3 pb-2">
                                            {filteredAvailableCriteria.map(c => (
                                                <li
                                                    key={`criteria-${c.id}`}
                                                    className="border rounded-lg p-4 hover:bg-muted/50 flex flex-col gap-3"
                                                >
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="flex-1 min-w-0">
                                                            <p className="font-medium text-sm leading-snug">
                                                                {c.name}
                                                            </p>
                                                        </div>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => addDraftCriteria(c.id, c.name)}
                                                            className="shrink-0"
                                                            disabled={
                                                                isSaving ||
                                                                isResetting ||
                                                                visibleDraftCount >= MAX_VISIBLE
                                                            }
                                                            title={
                                                                visibleDraftCount >= MAX_VISIBLE
                                                                    ? `Maximum ${MAX_VISIBLE} columns allowed`
                                                                    : undefined
                                                            }
                                                        >
                                                            {tTenders('columns.add')}
                                                        </Button>
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : availableCriteria.length === 0 ? (
                                        <div className="text-center text-muted-foreground py-12 text-sm">
                                            {tTenders('columns.noCriteriaAvailable')}
                                        </div>
                                    ) : (
                                        <div className="text-center text-muted-foreground py-12 text-sm">
                                            {tTenders('columns.allCriteriaAdded')}
                                        </div>
                                    )}
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </div>
                </div>
                <Separator className="my-4" />
                <DialogFooter className="flex flex-col lg:flex-row justify-between items-center gap-2">
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
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                        {visibleDraftCount < MIN_VISIBLE && (
                            <span className="text-destructive text-sm">
                                {t('tenders.columns.selectMinColumns', { min: MIN_VISIBLE })}
                            </span>
                        )}
                        {visibleDraftCount > MAX_VISIBLE && (
                            <span className="text-destructive text-sm">
                                {t('tenders.columns.maxColumnsReached', { max: MAX_VISIBLE })}
                            </span>
                        )}
                        {visibleDraftCount === MAX_VISIBLE && (
                            <span className="text-amber-600 text-sm">
                                {t('tenders.columns.maxColumnsReachedStatus', { current: MAX_VISIBLE, max: MAX_VISIBLE })}
                            </span>
                        )}
                        <Button
                            variant="outline"
                            onClick={onClose}
                            disabled={isSaving || isResetting}
                        >
                            {t('common.cancel')}
                        </Button>
                        <Button
                            onClick={commitChanges}
                            className="bg-primary hover:bg-primary/90"
                            disabled={
                                visibleDraftCount < MIN_VISIBLE ||
                                visibleDraftCount > MAX_VISIBLE ||
                                isSaving ||
                                isResetting
                            }
                        >
                            {isSaving ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t('tenders.columns.saving')}
                                </>
                            ) : (
                                t('common.save')
                            )}
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
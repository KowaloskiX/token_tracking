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
import {
    ColumnConfig,
    CriteriaColumnConfig,
    isCriteriaColumn,
} from '@/types/tableColumns';
import { useTendersTranslations, useTranslations } from '@/hooks/useTranslations';
import { cn } from '@/lib/utils';

interface ColumnManagerProps {
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
    onResetToDefaults: () => void;
    onUpdateColumnWidth: (columnId: string, width: number) => void;
}

export const ColumnManager: React.FC<ColumnManagerProps> = ({
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
}) => {
    const t = useTranslations();
    const tTenders = useTendersTranslations();

    const MIN_VISIBLE = 3;

    const [draftColumns, setDraftColumns] = useState<ColumnConfig[]>([]);
    const [searchCriteria, setSearchCriteria] = useState('');
    const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
    const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

    useEffect(() => {
        if (isOpen) {
            setDraftColumns(columns.map(c => ({ ...c })));
            setSearchCriteria('');
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
            if (next.filter(c => c.visible).length < MIN_VISIBLE) return prev;
            return next;
        });
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
            prev.map(c => (c.id === id ? { ...c, width } : c))
        );
    };

    const addDraftCriteria = (criteriaId: string, name: string) => {
        setDraftColumns(prev => {
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
        if (target.closest('input, button, label')) {
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

    const commitChanges = () => {
        draftColumns.forEach((draft, newIdx) => {
            const original = columns.find(c => c.id === draft.id);
            if (!original) {
                if (isCriteriaColumn(draft)) {
                    onAddCriteriaColumn(draft.criteriaId, draft.criteriaName);
                }
                return;
            }
            if (draft.visible !== original.visible) onToggleVisibility(draft.id);
            if (draft.width !== original.width) onUpdateColumnWidth(draft.id, draft.width);
            const oldIdx = columns.findIndex(c => c.id === draft.id);
            if (oldIdx !== newIdx) onReorderColumns(oldIdx, newIdx);
        });
        columns
            .filter(isCriteriaColumn)
            .forEach(col => {
                if (!draftColumns.find(c => c.id === col.id)) {
                    onRemoveCriteriaColumn((col as CriteriaColumnConfig).criteriaId);
                }
            });
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-7xl max-h-[90vh] flex flex-col">
                <DialogHeader className="pb-4 border-b">
                    <DialogTitle className="text-lg font-semibold">
                        {tTenders('columns.manageColumns')}
                        <span className="ml-2 text-sm font-normal text-muted-foreground">
                            ({visibleDraftCount}/{draftColumns.length} {tTenders('columns.visible')})
                        </span>
                    </DialogTitle>
                </DialogHeader>
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
                                            setDraftColumns(prev =>
                                                prev.map(c => ({ ...c, visible: true }))
                                            )
                                        }
                                    >
                                        {tTenders('columns.showAll')}
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
                                                draggable
                                                onDragStart={e => handleDragStart(e, idx)}
                                                onDragOver={e => handleDragOver(e, idx)}
                                                onDragEnd={finishDrag}
                                                onDrop={finishDrag}
                                                className={cn(
                                                    'relative flex items-center gap-4 rounded-lg border px-3 py-2 bg-card transition-colors',
                                                    col.visible ? 'opacity-100' : 'opacity-60',
                                                    dragOverIndex === idx && 'ring-2 ring-primary/30',
                                                    draggedIndex === idx && 'opacity-40'
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
                                                        {isCriteriaColumn(col) && (
                                                            <span className="text-primary">
                                                                ✓ Criteria Column
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
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
                                                    />
                                                </div>
                                                <Switch
                                                    checked={col.visible}
                                                    onCheckedChange={() => toggleDraftVisibility(col.id)}
                                                />
                                                {isCriteriaColumn(col) && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="text-destructive hover:text-destructive"
                                                        onClick={() => removeDraftCriteria((col as CriteriaColumnConfig).criteriaId)}
                                                    >
                                                        {tTenders('columns.remove')}
                                                    </Button>
                                                )}
                                            </li>
                                        ))}
                                    </ul>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </div>
                    
                    {/* Add Criteria Section - Takes up 2/5 of the width (much wider) */}
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
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="flex-1 min-w-0">
                                                            <p className="font-medium text-sm leading-snug">
                                                                {c.name}
                                                            </p>
                                                            {c.description && (
                                                                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                                                                    {c.description}
                                                                </p>
                                                            )}
                                                        </div>
                                                        <Button 
                                                            variant="outline" 
                                                            size="sm" 
                                                            onClick={() => addDraftCriteria(c.id, c.name)}
                                                            className="shrink-0"
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
                    <Button variant="outline" onClick={onResetToDefaults}>
                        {tTenders('columns.resetDefaults')}
                    </Button>
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                        {visibleDraftCount < MIN_VISIBLE && (
                            <span className="text-destructive text-sm">Select at least {MIN_VISIBLE} columns</span>
                        )}
                        <Button variant="outline" onClick={onClose}>{t('common.cancel')}</Button>
                        <Button onClick={commitChanges} className="bg-primary hover:bg-primary/90" disabled={visibleDraftCount < MIN_VISIBLE}>
                            {t('common.save')}
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

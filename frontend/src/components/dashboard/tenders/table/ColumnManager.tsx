// components/dashboard/tenders/table/ColumnManager.tsx

import React, { useState } from 'react';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  GripVertical,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  RotateCcw,
  Settings,
  ChevronDown,
} from 'lucide-react';
import { ColumnConfig, CriteriaColumnConfig, isCriteriaColumn } from '@/types/tableColumns';
import { useTendersTranslations } from '@/hooks/useTranslations';

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
  const t = useTendersTranslations();
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Get criteria columns that are already added
  const addedCriteriaIds = columns
    .filter(col => isCriteriaColumn(col))
    .map(col => (col as CriteriaColumnConfig).criteriaId);

  // Get available criteria that haven't been added yet
  const availableToAdd = availableCriteria.filter(
    criteria => !addedCriteriaIds.includes(criteria.id)
  );

  const sortedColumns = [...columns].sort((a, b) => a.order - b.order);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDragEnd = () => {
    if (draggedIndex !== null && dragOverIndex !== null && draggedIndex !== dragOverIndex) {
      onReorderColumns(draggedIndex, dragOverIndex);
    }
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleWidthChange = (columnId: string, value: string) => {
    const width = parseInt(value, 10);
    if (!isNaN(width) && width > 0) {
      onUpdateColumnWidth(columnId, width);
    }
  };

  const getColumnIcon = (column: ColumnConfig) => {
    switch (column.type) {
      case 'source':
        return '🔗';
      case 'name':
        return '📋';
      case 'organization':
        return '🏢';
      case 'publication_date':
        return '📅';
      case 'submission_deadline':
        return '⏰';
      case 'board_status':
        return '📊';
      case 'score':
        return '⭐';
      case 'criteria':
        return '✅';
      case 'actions':
        return '⚡';
      default:
        return '📄';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            {t('tenders.columns.manageColumns')}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
          {/* Current Columns */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  {t('tenders.columns.currentColumns')}
                  <Badge variant="secondary">
                    {columns.filter(col => col.visible).length} / {columns.length}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-2">
                    {sortedColumns.map((column, index) => (
                      <div
                        key={column.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, index)}
                        onDragOver={(e) => handleDragOver(e, index)}
                        onDragEnd={handleDragEnd}
                        className={`
                          p-3 border rounded-lg transition-all duration-200 cursor-move
                          ${dragOverIndex === index ? 'border-primary bg-primary/5' : 'border-border'}
                          ${draggedIndex === index ? 'opacity-50' : 'opacity-100'}
                          ${column.visible ? 'bg-background' : 'bg-muted/50'}
                        `}
                      >
                        <div className="flex items-center gap-3">
                          <GripVertical className="h-4 w-4 text-muted-foreground" />
                          
                          <span className="text-lg">{getColumnIcon(column)}</span>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-sm truncate">
                                {column.label}
                              </span>
                              {isCriteriaColumn(column) && (
                                <Badge variant="outline" className="text-xs">
                                  {t('tenders.columns.criteria')}
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                              <span>{t('tenders.columns.width')}: {column.width}px</span>
                              <span>{t('tenders.columns.order')}: {column.order + 1}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1">
                              <Label htmlFor={`width-${column.id}`} className="text-xs">
                                W:
                              </Label>
                              <Input
                                id={`width-${column.id}`}
                                type="number"
                                value={column.width}
                                onChange={(e) => handleWidthChange(column.id, e.target.value)}
                                className="w-16 h-6 text-xs"
                                min={column.minWidth}
                                max={column.maxWidth}
                              />
                            </div>

                            <Switch
                              checked={column.visible}
                              onCheckedChange={() => onToggleVisibility(column.id)}
                              className="data-[state=checked]:bg-primary"
                            />

                            {isCriteriaColumn(column) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => onRemoveCriteriaColumn((column as CriteriaColumnConfig).criteriaId)}
                                className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            )}

                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onToggleVisibility(column.id)}
                              className="h-6 w-6 p-0"
                            >
                              {column.visible ? (
                                <Eye className="h-3 w-3" />
                              ) : (
                                <EyeOff className="h-3 w-3" />
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          {/* Add Criteria */}
          <div>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  {t('tenders.columns.addCriteria')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  {availableToAdd.length > 0 ? (
                    <div className="space-y-2">
                      {availableToAdd.map((criteria) => (
                        <div
                          key={criteria.id}
                          className="p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-sm truncate">
                                {criteria.name}
                              </div>
                              {criteria.description && (
                                <div className="text-xs text-muted-foreground mt-1">
                                  {criteria.description}
                                </div>
                              )}
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => onAddCriteriaColumn(criteria.id, criteria.name)}
                              className="h-6 text-xs"
                            >
                              <Plus className="h-3 w-3 mr-1" />
                              {t('tenders.columns.add')}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-muted-foreground py-8">
                      <Plus className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">
                        {t('tenders.columns.allCriteriaAdded')}
                      </p>
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>

        <Separator />

        <DialogFooter className="flex justify-between">
          <Button
            variant="outline"
            onClick={onResetToDefaults}
            className="flex items-center gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            {t('tenders.columns.resetDefaults')}
          </Button>

          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button onClick={onClose}>
              {t('common.save')}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
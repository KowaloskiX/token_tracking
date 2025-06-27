// src/components/dashboard/tenders/table/ColumnManagement.tsx

import React, { useState } from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Settings, Eye, EyeOff, Plus, Minus } from 'lucide-react';
import { TableColumn } from '@/types/table';
import { TenderAnalysis } from '@/types/tenders';
import { useTendersTranslations } from "@/hooks/useTranslations";

interface ColumnManagementProps {
  columns: TableColumn[];
  availableCriteria: string[];
  selectedAnalysis?: TenderAnalysis | null;
  onColumnVisibilityChange: (columnId: string, visible: boolean) => void;
  onAddCriteriaColumn: (criteriaName: string) => void;
  onRemoveCriteriaColumn: (criteriaName: string) => void;
}

export const ColumnManagement: React.FC<ColumnManagementProps> = ({
  columns,
  availableCriteria,
  selectedAnalysis,
  onColumnVisibilityChange,
  onAddCriteriaColumn,
  onRemoveCriteriaColumn,
}) => {
  const t = useTendersTranslations();
  const [showCriteria, setShowCriteria] = useState(false);

  const defaultColumns = columns.filter(col => col.field_type !== 'criteria');
  const criteriaColumns = columns.filter(col => col.field_type === 'criteria');
  
  const getColumnDisplayName = (column: TableColumn) => {
    switch (column.field_name) {
      case 'name':
        return t('tenders.list.order');
      case 'organization':
        return t('tenders.details.client');
      case 'initiation_date':
        return t('tenders.details.publicationDate');
      case 'submission_deadline':
        return t('tenders.details.submissionDeadline');
      case 'status':
        return t('tenders.list.boardStatus');
      case 'tender_score':
        return t('tenders.list.relevance');
      default:
        return column.display_name;
    }
  };

  const visibleColumnsCount = columns.filter(col => col.visible).length;
  const criteriaColumnsCount = criteriaColumns.filter(col => col.visible).length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="bg-white/20 shadow">
          <Settings className="mr-2 h-4 w-4" />
          {t('tenders.table.columns')}
          <Badge variant="secondary" className="ml-2 text-xs">
            {visibleColumnsCount}
          </Badge>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
          {t('tenders.table.defaultColumns')}
        </DropdownMenuLabel>
        
        {defaultColumns.map((column) => (
          <DropdownMenuCheckboxItem
            key={column.id}
            checked={column.visible}
            onCheckedChange={(checked) => onColumnVisibilityChange(column.id, checked)}
            className="flex items-center justify-between"
            disabled={column.field_type === 'source' || column.field_type === 'actions'} // Always keep source and actions visible
          >
            <span className="truncate">{getColumnDisplayName(column)}</span>
            {column.visible ? (
              <Eye className="h-3 w-3 text-muted-foreground ml-2" />
            ) : (
              <EyeOff className="h-3 w-3 text-muted-foreground ml-2" />
            )}
          </DropdownMenuCheckboxItem>
        ))}

        {availableCriteria.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setShowCriteria(!showCriteria);
              }}
              className="flex justify-between items-center cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {t('tenders.table.criteriaColumns')}
                </span>
                <Badge variant="outline" className="text-xs">
                  {criteriaColumnsCount}/{availableCriteria.length}
                </Badge>
              </div>
              <div className="flex items-center gap-1">
                {criteriaColumnsCount > 0 && (
                  <Badge variant="secondary" className="text-xs px-1">
                    {criteriaColumnsCount}
                  </Badge>
                )}
                <Eye className={`h-3 w-3 transition-transform ${showCriteria ? 'rotate-180' : ''}`} />
              </div>
            </DropdownMenuItem>

            {showCriteria && (
              <div className="max-h-[200px] overflow-y-auto border-t border-t-muted/20 pt-1">
                {availableCriteria.map((criteriaName) => {
                  const existingColumn = criteriaColumns.find(col => col.criteria_name === criteriaName);
                  const isVisible = existingColumn?.visible || false;
                  
                  return (
                    <DropdownMenuItem
                      key={criteriaName}
                      onSelect={(e) => {
                        e.preventDefault();
                        if (existingColumn) {
                          if (isVisible) {
                            onRemoveCriteriaColumn(criteriaName);
                          } else {
                            onColumnVisibilityChange(existingColumn.id, true);
                          }
                        } else {
                          onAddCriteriaColumn(criteriaName);
                        }
                      }}
                      className="flex items-center justify-between cursor-pointer px-4"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="truncate text-sm" title={criteriaName}>
                          {criteriaName}
                        </div>
                        {selectedAnalysis?.criteria?.find(c => c.name === criteriaName)?.weight && (
                          <div className="text-xs text-muted-foreground">
                            Weight: {selectedAnalysis.criteria.find(c => c.name === criteriaName)?.weight}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        {isVisible ? (
                          <>
                            <Eye className="h-3 w-3 text-green-600" />
                            <Minus className="h-3 w-3 text-muted-foreground" />
                          </>
                        ) : existingColumn ? (
                          <>
                            <EyeOff className="h-3 w-3 text-muted-foreground" />
                            <Plus className="h-3 w-3 text-green-600" />
                          </>
                        ) : (
                          <Plus className="h-3 w-3 text-green-600" />
                        )}
                      </div>
                    </DropdownMenuItem>
                  );
                })}
              </div>
            )}
          </>
        )}

        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-xs text-muted-foreground">
          {t('tenders.table.columnHint')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
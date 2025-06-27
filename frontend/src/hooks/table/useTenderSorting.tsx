import { useMemo, useState, useCallback } from 'react';
import { TenderAnalysisResult } from "@/types/tenders";
import { SortableField } from '@/types/table';

interface SortConfig {
  field: 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date';
  direction: 'asc' | 'desc';
}

interface UseTenderSortingProps {
  filteredResults: TenderAnalysisResult[];
  calculateDaysRemaining: (deadlineStr: string) => number;
  selectedDate: Date | undefined;
}

export const useTenderSorting = ({ 
  filteredResults, 
  calculateDaysRemaining,
  selectedDate 
}: UseTenderSortingProps) => {
  const [sortConfig, setSortConfig] = useState<SortConfig | null>(null);

  const handleSort = useCallback((field: SortableField) => {
    setSortConfig(current => {
      if (current?.field === field) {
        return { field, direction: current.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { field, direction: field === 'tender_score' ? 'desc' : 'asc' };
    });
  }, []);

  const sortByTimeIfDateFiltered = useCallback((results: TenderAnalysisResult[]) => {
    if (!selectedDate) return results;

    return [...results].sort((a, b) => {
      const aDateStr = a.tender_metadata.initiation_date;
      const bDateStr = b.tender_metadata.initiation_date;

      if (!aDateStr || !bDateStr) return 0;

      let aTime: number, bTime: number;

      if (aDateStr.includes('-')) {
        const isoStr = aDateStr.includes(' ') ? aDateStr.replace(' ', 'T') : aDateStr;
        aTime = new Date(isoStr).getTime();
      } else if (aDateStr.includes('.')) {
        const [day, month, year] = aDateStr.split('.').map(Number);
        aTime = new Date(year, month - 1, day).getTime();
      } else {
        return 0;
      }

      if (bDateStr.includes('-')) {
        const isoStr = bDateStr.includes(' ') ? bDateStr.replace(' ', 'T') : bDateStr;
        bTime = new Date(isoStr).getTime();
      } else if (bDateStr.includes('.')) {
        const [day, month, year] = bDateStr.split('.').map(Number);
        bTime = new Date(year, month - 1, day).getTime();
      } else {
        return 0;
      }

      return sortConfig?.direction === 'asc' ? aTime - bTime : bTime - aTime;
    });
  }, [selectedDate, sortConfig?.direction]);

  const sortedResults = useMemo(() => {
    let results = filteredResults;
    
    if (sortConfig) {
      results = [...filteredResults].sort((a, b) => {
        if (sortConfig.field === 'tender_score') {
          const cmp = sortConfig.direction === 'asc'
            ? a.tender_score - b.tender_score
            : b.tender_score - a.tender_score;
          if (cmp !== 0) return cmp;
          const aUpdated = new Date(a.updated_at || '').getTime();
          const bUpdated = new Date(b.updated_at || '').getTime();
          return bUpdated - aUpdated;
        } else if (sortConfig.field === 'updated_at') {
          const aDate = new Date(a.updated_at || '').getTime();
          const bDate = new Date(b.updated_at || '').getTime();
          const cmp = sortConfig.direction === 'asc' ? aDate - bDate : bDate - aDate;
          if (cmp !== 0) return cmp;
          return b.tender_score - a.tender_score;
        } else if (sortConfig.field === 'submission_deadline') {
          const getDeadlineStatus = (deadlineStr: string): { status: 'future' | 'past' | 'invalid', days: number } => {
            if (!deadlineStr || deadlineStr.includes('NaN')) {
              return { status: 'invalid', days: Infinity };
            }

            const days = calculateDaysRemaining(deadlineStr);

            if (isNaN(days)) {
              return { status: 'invalid', days: Infinity };
            } else if (days < 0) {
              return { status: 'past', days: days };
            } else {
              return { status: 'future', days: days };
            }
          };

          const aStatus = getDeadlineStatus(a.tender_metadata.submission_deadline);
          const bStatus = getDeadlineStatus(b.tender_metadata.submission_deadline);

          const statusOrder = { future: 0, past: 1, invalid: 2 };

          const aOrder = statusOrder[aStatus.status];
          const bOrder = statusOrder[bStatus.status];

          let cmp = aOrder - bOrder;

          if (cmp === 0) {
            if (aStatus.status === 'future') {
              cmp = sortConfig.direction === 'asc'
                ? aStatus.days - bStatus.days
                : bStatus.days - aStatus.days;
            } else if (aStatus.status === 'past') {
              cmp = sortConfig.direction === 'asc'
                ? bStatus.days - aStatus.days
                : aStatus.days - bStatus.days;
            }
          }

          if (cmp === 0) {
            const aUpdated = new Date(a.updated_at || '').getTime();
            const bUpdated = new Date(b.updated_at || '').getTime();
            cmp = bUpdated - aUpdated;
          }

          return cmp;
        } else if (sortConfig.field === 'created_at') {
          const aTime = new Date(a.created_at).getTime();
          const bTime = new Date(b.created_at).getTime();
          return sortConfig.direction === 'asc' ? aTime - bTime : bTime - aTime;
        } else if (sortConfig.field === 'initiation_date') {
          const aDateStr = a.tender_metadata.initiation_date;
          const bDateStr = b.tender_metadata.initiation_date;
          let aDate: number, bDate: number;

          if (aDateStr && !aDateStr.includes('NaN')) {
            if (aDateStr.includes('-')) {
              const isoStr = aDateStr.includes(' ') ? aDateStr.replace(' ', 'T') : aDateStr;
              aDate = new Date(isoStr).getTime();
            } else if (aDateStr.includes('.')) {
              const [day, month, year] = aDateStr.split('.').map(Number);
              aDate = new Date(year, month - 1, day).getTime();
            } else {
              aDate = 0;
            }
          } else {
            aDate = 0;
          }

          if (bDateStr && !bDateStr.includes('NaN')) {
            if (bDateStr.includes('-')) {
              const isoStr = bDateStr.includes(' ') ? bDateStr.replace(' ', 'T') : bDateStr;
              bDate = new Date(isoStr).getTime();
            } else if (bDateStr.includes('.')) {
              const [day, month, year] = bDateStr.split('.').map(Number);
              bDate = new Date(year, month - 1, day).getTime();
            } else {
              bDate = 0;
            }
          } else {
            bDate = 0;
          }

          const cmp = sortConfig.direction === 'asc' ? aDate - bDate : bDate - aDate;
          if (cmp !== 0) return cmp;
          const aUpdated = new Date(a.updated_at || '').getTime();
          const bUpdated = new Date(b.updated_at || '').getTime();
          return bUpdated - aUpdated;
        }
        return 0;
      });
    }

    if (selectedDate) {
      results = sortByTimeIfDateFiltered(results);
    }

    return results;
  }, [filteredResults, sortConfig, calculateDaysRemaining, selectedDate, sortByTimeIfDateFiltered]);

  return {
    sortConfig,
    sortedResults,
    handleSort
  };
};
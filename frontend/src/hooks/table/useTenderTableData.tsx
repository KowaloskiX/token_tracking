import { useState, useEffect, useMemo, useRef } from 'react';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTender } from '@/context/TenderContext';
import { useRouter } from 'next/navigation';

interface Filters {
  onlyQualified: boolean;
  status: { inactive: boolean; active: boolean; archived: boolean; inBoard: boolean };
  voivodeship: Record<string, boolean>;
  source: Record<string, boolean>;
  criteria: Record<string, boolean>;
}

interface UseTenderTableDataProps {
  selectedAnalysis: any;
  includeHistorical: boolean;
  allResults: TenderAnalysisResult[];
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  filters: Filters;
  searchQuery: string;
  selectedDate: Date | undefined;
  dateFilterType: 'initiation_date' | 'submission_deadline';
  sortConfig: any;
  getTenderBoards: (tenderId: string) => string[];
}

export const useTenderTableData = ({
  selectedAnalysis,
  includeHistorical,
  allResults,
  setAllResults,
  filters,
  searchQuery,
  selectedDate,
  dateFilterType,
  sortConfig,
  getTenderBoards
}: UseTenderTableDataProps) => {
  const { results } = useTender();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [totalFetched, setTotalFetched] = useState(0);
  const [totalTendersCount, setTotalTendersCount] = useState<number | null>(null);

  // Fetch all data
  useEffect(() => {
    if (!selectedAnalysis?._id) {
      setAllResults([]);
      setIsLoading(false);
      setTotalTendersCount(null);
      setTotalFetched(0);
      return;
    }

    let isCancelled = false;
    const fetchPage = async (page: number, limit: number) => {
      const token = localStorage.getItem("token") || "";
      const historicalParam = includeHistorical ? "&include_historical=true" : "";
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysis._id}/results?page=${page}&limit=${limit}${historicalParam}&include_criteria_for_filtering=true`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (!resp.ok) {
        throw new Error("Failed to fetch page " + page);
      }
      return resp.json() as Promise<{
        results: TenderAnalysisResult[];
        total: number;
      }>;
    };

    const loadAllPages = async () => {
      try {
        setIsLoading(true);
        setAllResults([]);
        setTotalTendersCount(null);
        setTotalFetched(0);

        let page = 1;
        const limit = 200;
        let combined: TenderAnalysisResult[] = [];
        let currentTotal = 0;
        let lastBatchSize = 0;

        const firstResp = await fetchPage(page, limit);
        if (isCancelled) return;

        combined = firstResp.results;
        currentTotal = firstResp.total;
        lastBatchSize = firstResp.results.length;
        setTotalTendersCount(currentTotal);
        setTotalFetched(combined.length);

        while (lastBatchSize === limit && !isCancelled) {
          page += 1;
          const nextResp = await fetchPage(page, limit);
          if (isCancelled) break;

          combined = [...combined, ...nextResp.results];
          lastBatchSize = nextResp.results.length;
          setTotalFetched(combined.length);

          if (nextResp.total !== currentTotal) {
            setTotalTendersCount(nextResp.total);
            currentTotal = nextResp.total;
          }
        }

        if (!isCancelled) {
          setAllResults(combined);
        }
      } catch (err) {
        console.error("Error loading all pages:", err);
        if (!isCancelled) {
          setAllResults([]);
          router.replace("/dashboard/tenders/");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    loadAllPages();

    return () => {
      isCancelled = true;
      setIsLoading(false);
    };
  }, [selectedAnalysis?._id, setAllResults, includeHistorical]);

  // Merge data with context updates
  const mergedData = useMemo(() => {
    return allResults ? allResults.map((localTender) => {
      const updatedTender = results.find((r) => r._id === localTender._id);
      if (updatedTender) {
        return {
          ...localTender,
          status: updatedTender.status,
          opened_at: updatedTender.opened_at !== undefined ? updatedTender.opened_at : localTender.opened_at,
        };
      }
      return localTender;
    }) : [];
  }, [allResults, results]);

  // Calculate days remaining helper
  const calculateDaysRemaining = (deadlineStr: string): number => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let deadline: Date;
    if (!deadlineStr || typeof deadlineStr !== 'string' || deadlineStr.toLowerCase().includes('nan')) {
      return NaN;
    }

    if (deadlineStr.includes('-')) {
      const isoStr = deadlineStr.includes(' ') ? deadlineStr.replace(' ', 'T') : deadlineStr;
      deadline = new Date(isoStr);
    } else if (deadlineStr.includes('.')) {
      const parts = deadlineStr.split('.');
      if (parts.length !== 3 || parts.some(p => isNaN(parseInt(p)))) {
        return NaN;
      }
      const year = parseInt(parts[2]);
      const month = parseInt(parts[1]);
      const day = parseInt(parts[0]);
      if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return NaN;
      deadline = new Date(year, month - 1, day);
    } else if (deadlineStr.includes('/')) {
      const cleanDeadlineStr = deadlineStr.replace(/\([^)]*\)/g, '').trim();
      deadline = new Date(cleanDeadlineStr);

      if (isNaN(deadline.getTime())) {
        const parts = cleanDeadlineStr.split('/');
        if (parts.length === 3) {
          let day, month, year;
          if (parseInt(parts[0]) > 12) {
            day = parseInt(parts[0]);
            month = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]);
          } else {
            month = parseInt(parts[0]);
            day = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]);
          }

          if (!isNaN(day) && !isNaN(month) && !isNaN(year) && year > 1900) {
            deadline = new Date(year, month - 1, day);
          } else {
            return NaN;
          }
        } else {
          return NaN;
        }
      }
    } else {
      return NaN;
    }

    if (isNaN(deadline.getTime())) {
      return NaN;
    }

    deadline.setHours(0, 0, 0, 0);
    const diffTime = deadline.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
  };

  // Filter data
  const filteredResults = useMemo(() => {
    type VoivodeshipKey = keyof typeof filters.voivodeship;
    
    return mergedData.filter((result) => {
      if (filters.onlyQualified && result.tender_score < 0.7) return false;

      const status = result.status || "inactive";
      const tenderBoards = getTenderBoards(result._id!);
      const isInBoard = tenderBoards.length > 0;

      const statusMatches =
        (filters.status.inactive && status === 'inactive') ||
        (filters.status.active && status === 'active') ||
        (filters.status.archived && status === 'archived') ||
        (filters.status.inBoard && isInBoard);

      const anyStatusFilterSelected = filters.status.inactive || filters.status.active || filters.status.archived || filters.status.inBoard;

      if (anyStatusFilterSelected && !statusMatches) {
        return false;
      }

      if (result.location?.voivodeship && result.location.voivodeship !== "UNKNOWN") {
        let voivodeshipFormatted = result.location.voivodeship;

        if (voivodeshipFormatted === voivodeshipFormatted.toLowerCase()) {
          voivodeshipFormatted =
            voivodeshipFormatted.charAt(0).toUpperCase() +
            voivodeshipFormatted.slice(1).toLowerCase();
        }

        if (!filters.voivodeship[voivodeshipFormatted as VoivodeshipKey]) {
          return false;
        }
      }

      const searchLower = searchQuery.toLowerCase();
      if (searchQuery) {
        const nameMatch = result.tender_metadata.name.toLowerCase().includes(searchLower);
        const organizationMatch = result.tender_metadata.organization.toLowerCase().includes(searchLower);

        let locationMatch = false;
        if (result.location != null) {
          const fullLocation =
            "#" + result?.order_number +
            result.location.country +
            result.location.voivodeship +
            result.location.city;
          locationMatch = fullLocation.toLowerCase().includes(searchLower);
        }

        if (!nameMatch && !organizationMatch && !locationMatch) {
          return false;
        }
      }

      if (selectedDate) {
        const dateField = dateFilterType === 'initiation_date'
          ? result.tender_metadata.initiation_date
          : result.tender_metadata.submission_deadline;

        if (!dateField || dateField.includes('NaN')) return false;

        let fieldDate: Date;
        if (dateField.includes('-')) {
          const isoStr = dateField.includes(' ') ? dateField.replace(' ', 'T') : dateField;
          fieldDate = new Date(isoStr);
        } else if (dateField.includes('.')) {
          const [day, month, year] = dateField.split('.').map(Number);
          fieldDate = new Date(year, month - 1, day);
        } else {
          return false;
        }

        if (isNaN(fieldDate.getTime())) return false;

        const selectedDateOnly = new Date(
          selectedDate.getFullYear(),
          selectedDate.getMonth(),
          selectedDate.getDate()
        );

        const fieldDateOnly = new Date(
          fieldDate.getFullYear(),
          fieldDate.getMonth(),
          fieldDate.getDate()
        );

        if (selectedDateOnly.getTime() !== fieldDateOnly.getTime()) {
          return false;
        }
      }

      if (result.source && filters.source && !filters.source[result.source]) {
        return false;
      }

      if (filters.criteria && Object.keys(filters.criteria).length > 0) {
        const selectedCriteria = Object.entries(filters.criteria).filter(([_, isSelected]) => isSelected);
        
        if (selectedCriteria.length > 0) {
          const hasFailingCriteria = selectedCriteria.some(([criteriaName, isSelected]) => {
            const criteriaResult = result.criteria_analysis?.find(ca => ca.criteria === criteriaName);
            
            if (!criteriaResult) {
              return true;
            }
            
            const isMet = criteriaResult.analysis?.criteria_met === true;
            return !isMet;
          });
          
          if (hasFailingCriteria) {
            return false;
          }
        }
      }

      return true;
    });
  }, [mergedData, filters, searchQuery, selectedDate, dateFilterType, getTenderBoards]);

  // Sort data
  const sortedResults = useMemo(() => {
    let sorted = [...filteredResults];

    if (sortConfig) {
      sorted = sorted.sort((a, b) => {
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
        }
        // Add other sorting logic as needed
        return 0;
      });
    }

    return sorted;
  }, [filteredResults, sortConfig, calculateDaysRemaining]);

  const availableSources = useMemo(() => {
    const sources = new Set<string>();
    allResults.forEach(result => {
      if (result.source) {
        sources.add(result.source);
      }
    });
    return Array.from(sources);
  }, [allResults]);

  const availableCriteria = useMemo(() => {
    if (!selectedAnalysis?.criteria || selectedAnalysis.criteria.length === 0) {
      return [];
    }
    return selectedAnalysis.criteria.map((c: any) => c.name);
  }, [selectedAnalysis?.criteria]);

  return {
    isLoading,
    totalFetched,
    totalTendersCount,
    mergedData,
    filteredResults,
    sortedResults,
    availableSources,
    availableCriteria,
    calculateDaysRemaining
  };
};
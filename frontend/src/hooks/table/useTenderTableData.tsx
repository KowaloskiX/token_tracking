import { useState, useEffect, useMemo, useRef } from 'react';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTender } from '@/context/TenderContext';
import { useRouter } from 'next/navigation';

interface Filters {
  onlyQualified: boolean;
  status: { inactive: boolean; active: boolean; archived: boolean; inBoard: boolean, filtered: boolean; external: boolean };
  voivodeship: Record<string, boolean>;
  source: Record<string, boolean>;
  criteria: Record<string, boolean>;
}

interface UseTenderTableDataProps {
  selectedAnalysis: any;
  includeHistorical: boolean;
  includeFiltered: boolean; // NEW: Include filtered results
  showIncludeExternal: boolean;
  includeExternal: boolean; // NEW: Include external results
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
  includeFiltered,
  showIncludeExternal,
  includeExternal,
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
      const criteriaParam = "&include_criteria_for_filtering=true"; // This triggers the new projection
      // NEW: includeFiltered param
      const filteredParam = includeFiltered ? "&include_filtered=true" : "";
      // NEW: includeExternal param (only if showIncludeExternal)
      const externalParam = showIncludeExternal && includeExternal ? "&include_external=true" : "";
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysis._id}/results?page=${page}&limit=${limit}${historicalParam}${filteredParam}${externalParam}${criteriaParam}&include_criteria_for_filtering=true`,
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
  }, [selectedAnalysis?._id, setAllResults, includeHistorical, includeFiltered, includeExternal]);

  const mergedData = useMemo(() => {
    return allResults ? allResults.map((localTender) => {
      const updatedTender = results.find((r) => r._id === localTender._id);
      if (updatedTender) {
        return {
          ...localTender,
          status: updatedTender.status,
          // IMPROVED: Don't override optimistic opened_at updates
          opened_at: (localTender._optimisticOpened && localTender.opened_at)
            ? localTender.opened_at // Keep optimistic value
            : (updatedTender.opened_at !== undefined
              ? updatedTender.opened_at
              : localTender.opened_at),
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

  // Available criteria - moved before sortedResults to fix dependency order
  const availableCriteria = useMemo(() => {
    if (!selectedAnalysis?.criteria || selectedAnalysis.criteria.length === 0) {
      return [];
    }

    return selectedAnalysis.criteria.map((criteria: any, index: number) => ({
      id: criteria.name,
      name: criteria.name,
      description: criteria.description || criteria.instruction || `Weight: ${criteria.weight || 'N/A'}`,
    }));
  }, [selectedAnalysis?.criteria]);

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
        (filters.status.filtered && status === 'filtered') ||
        (filters.status.external && status === 'external') || // NEW: Check for external status
        (filters.status.inBoard && isInBoard);

      const anyStatusFilterSelected = filters.status.inactive || filters.status.active || filters.status.archived || filters.status.inBoard || filters.status.filtered || filters.status.external;

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

  const sortedResults = useMemo(() => {
    let sorted = [...filteredResults];

    if (sortConfig) {
      sorted = sorted.sort((a, b) => {
        // Helper function to safely get nested property value
        const getNestedValue = (obj: any, path: string): any => {
          return path.split('.').reduce((current, key) => current?.[key], obj);
        };

        // Helper function to compare strings with locale awareness
        const compareStrings = (a: string, b: string, direction: 'asc' | 'desc') => {
          const result = a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
          return direction === 'asc' ? result : -result;
        };

        // Helper function to compare numbers
        const compareNumbers = (a: number, b: number, direction: 'asc' | 'desc') => {
          const result = a - b;
          return direction === 'asc' ? result : -result;
        };

        // Helper function to compare dates
        const compareDates = (a: string, b: string, direction: 'asc' | 'desc') => {
          const dateA = new Date(a).getTime();
          const dateB = new Date(b).getTime();
          const result = dateA - dateB;
          return direction === 'asc' ? result : -result;
        };

        // Check if this is a criteria column by checking if the field matches any criteria name
        const isCriteriaSort = availableCriteria.some((c: { id: string; name: string; description?: string }) => c.name === sortConfig.field);

        if (isCriteriaSort) {
          // This is a criteria column - sort by criteria
          const criteriaName = sortConfig.field;
          const criteriaA = a.criteria_analysis?.find(ca => ca.criteria === criteriaName);
          const criteriaB = b.criteria_analysis?.find(cb => cb.criteria === criteriaName);

          // Sort by criteria met status first, then by confidence
          const metA = criteriaA?.analysis?.criteria_met;
          const metB = criteriaB?.analysis?.criteria_met;

          // Priority order: true > false > null (met > not met > no data)
          const getMetPriority = (met: boolean | null | undefined): number => {
            if (met === true) return 2;
            if (met === false) return 1;
            return 0; // null or undefined
          };

          const priorityA = getMetPriority(metA);
          const priorityB = getMetPriority(metB);

          if (priorityA !== priorityB) {
            // For criteria sorting, we want "met" criteria to come first by default
            // So in 'asc' mode: met > not met > no data
            // In 'desc' mode: no data > not met > met
            const result = priorityB - priorityA; // Higher priority first
            return sortConfig.direction === 'asc' ? result : -result;
          }

          // If criteria met status is the same, sort by confidence level
          const confidenceA = criteriaA?.analysis?.confidence_level || 0;
          const confidenceB = criteriaB?.analysis?.confidence_level || 0;
          const confidenceResult = compareNumbers(confidenceA, confidenceB, sortConfig.direction);

          if (confidenceResult !== 0) return confidenceResult;

          // Fallback to tender score
          return compareNumbers(a.tender_score, b.tender_score, 'desc');
        }

        // Handle standard columns
        switch (sortConfig.field) {
          case 'tender_score': {
            const cmp = compareNumbers(a.tender_score, b.tender_score, sortConfig.direction);
            if (cmp !== 0) return cmp;
            // Fallback to updated_at for consistency
            return compareDates(a.updated_at || '', b.updated_at || '', 'desc');
          }

          case 'updated_at': {
            const cmp = compareDates(a.updated_at || '', b.updated_at || '', sortConfig.direction);
            if (cmp !== 0) return cmp;
            // Fallback to tender score
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'created_at': {
            const cmp = compareDates(a.created_at || '', b.created_at || '', sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'initiation_date': {
            const dateA = a.tender_metadata.initiation_date || a.tender_metadata.submission_deadline || '';
            const dateB = b.tender_metadata.initiation_date || b.tender_metadata.submission_deadline || '';
            const cmp = compareDates(dateA, dateB, sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'submission_deadline': {
            // Complex deadline sorting logic (keeping your existing logic)
            const getDeadlineStatus = (deadlineStr: string): { status: 'future' | 'past' | 'invalid', days: number } => {
              if (!deadlineStr || typeof deadlineStr !== 'string' || deadlineStr.includes('NaN')) {
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

            const aStatus = getDeadlineStatus(a.tender_metadata.submission_deadline || '');
            const bStatus = getDeadlineStatus(b.tender_metadata.submission_deadline || '');

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

          case 'tender_metadata.name': {
            const nameA = a.tender_metadata.name || '';
            const nameB = b.tender_metadata.name || '';
            const cmp = compareStrings(nameA, nameB, sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'tender_metadata.organization': {
            const orgA = a.tender_metadata.organization || '';
            const orgB = b.tender_metadata.organization || '';
            const cmp = compareStrings(orgA, orgB, sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'source': {
            const sourceA = a.source || '';
            const sourceB = b.source || '';
            const cmp = compareStrings(sourceA, sourceB, sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          case 'status': {
            // Sort by board status (if in board) or regular status
            const getBoardStatus = (result: TenderAnalysisResult) => {
              const boards = getTenderBoards(result._id!);
              if (boards.length > 0) {
                return boards[0]; // Use first board name for sorting
              }
              return result.status || 'inactive';
            };

            const statusA = getBoardStatus(a);
            const statusB = getBoardStatus(b);
            const cmp = compareStrings(statusA, statusB, sortConfig.direction);
            if (cmp !== 0) return cmp;
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }

          default: {
            // Fallback for any unmapped fields - try to get the value using the field path
            const valueA = getNestedValue(a, sortConfig.field);
            const valueB = getNestedValue(b, sortConfig.field);

            if (typeof valueA === 'string' && typeof valueB === 'string') {
              return compareStrings(valueA, valueB, sortConfig.direction);
            } else if (typeof valueA === 'number' && typeof valueB === 'number') {
              return compareNumbers(valueA, valueB, sortConfig.direction);
            }

            // Default fallback to tender score
            return compareNumbers(a.tender_score, b.tender_score, 'desc');
          }
        }
      });
    }

    return sorted;
  }, [filteredResults, sortConfig, calculateDaysRemaining, getTenderBoards, availableCriteria]);

  const availableSources = useMemo(() => {
    const sources = new Set<string>();
    allResults.forEach(result => {
      if (result.source) {
        sources.add(result.source);
      }
    });
    return Array.from(sources);
  }, [allResults]);

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
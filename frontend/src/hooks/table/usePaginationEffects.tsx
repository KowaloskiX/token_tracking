import { useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from "next/navigation";
import { Filters } from '@/components/dashboard/tenders/TenderFilters';

interface UsePaginationEffectsProps {
  currentPage: number;
  setCurrentPage: (page: number) => void;
  updateCurrentPage: (page: number, isUserTriggered?: boolean) => void;
  filteredResults: any[];
  searchQuery: string;
  filters: Filters;
  selectedDate: Date | undefined;
  dateFilterType: 'initiation_date' | 'submission_deadline';
  isLoading: boolean;
  initialPageAppliedRef: React.MutableRefObject<boolean>;
  LOCAL_ITEMS_PER_PAGE: number;
}

export const usePaginationEffects = ({
  currentPage,
  setCurrentPage,
  updateCurrentPage,
  filteredResults,
  searchQuery,
  filters,
  selectedDate,
  dateFilterType,
  isLoading,
  initialPageAppliedRef,
  LOCAL_ITEMS_PER_PAGE
}: UsePaginationEffectsProps) => {
  const searchParams = useSearchParams();

  const prevSearchQuery = useRef(searchQuery);
  const prevFilters = useRef(filters);
  const prevSelectedDate = useRef(selectedDate);
  const prevDateFilterType = useRef(dateFilterType);

  const pageBeforeSearch = useRef(currentPage);

  const getPageFromUrl = useCallback(() => {
    const pageParam = searchParams.get('page');
    const parsedPage = pageParam ? parseInt(pageParam, 10) : 1;
    return isNaN(parsedPage) || parsedPage < 1 ? 1 : parsedPage;
  }, [searchParams]);

  useEffect(() => {
    if (!initialPageAppliedRef.current || isLoading) {
      prevSearchQuery.current = searchQuery;
      prevFilters.current = filters;
      prevSelectedDate.current = selectedDate;
      prevDateFilterType.current = dateFilterType;
      return;
    }

    const searchChanged = prevSearchQuery.current !== searchQuery;
    const filtersChanged = JSON.stringify(prevFilters.current) !== JSON.stringify(filters);
    const dateChanged = prevSelectedDate.current !== selectedDate;
    const dateTypeChanged = prevDateFilterType.current !== dateFilterType;

    if (searchChanged || filtersChanged || dateChanged || dateTypeChanged) {
      if (searchChanged) {
        const wasEmpty = prevSearchQuery.current.trim() === '';
        const isNowEmpty = searchQuery.trim() === '';

        if (!wasEmpty && isNowEmpty) {
          const totalFilteredPages = Math.max(1, Math.ceil(filteredResults.length / LOCAL_ITEMS_PER_PAGE));
          const targetPage = Math.min(pageBeforeSearch.current, totalFilteredPages);
          updateCurrentPage(targetPage, false);
        } else if (wasEmpty && !isNowEmpty) {
          pageBeforeSearch.current = currentPage;
          updateCurrentPage(1, false);
        } else if (!wasEmpty && !isNowEmpty) {
          updateCurrentPage(1, false);
        }
      } else {
        const totalFilteredPages = Math.max(1, Math.ceil(filteredResults.length / LOCAL_ITEMS_PER_PAGE));

        if (currentPage > totalFilteredPages) {
          updateCurrentPage(totalFilteredPages, false);
        }
      }
    }

    prevSearchQuery.current = searchQuery;
    prevFilters.current = filters;
    prevSelectedDate.current = selectedDate;
    prevDateFilterType.current = dateFilterType;

  }, [
    searchQuery,
    filters,
    selectedDate,
    dateFilterType,
    currentPage,
    filteredResults.length,
    isLoading,
    updateCurrentPage,
    LOCAL_ITEMS_PER_PAGE
  ]);

  useEffect(() => {
    const handleRouteChange = () => {
      const newPageFromUrl = getPageFromUrl();
      if (newPageFromUrl !== currentPage) {
        setCurrentPage(newPageFromUrl);
      }
    };

    window.addEventListener('popstate', handleRouteChange);

    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  }, [getPageFromUrl, currentPage, setCurrentPage]);

  return {
    getPageFromUrl
  };
};
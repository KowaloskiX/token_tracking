import { useState, useEffect, useRef, useCallback, startTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

interface UseTenderTablePaginationProps {
  totalItems: number;
  itemsPerPage: number;
  isLoading: boolean;
  initialLoadComplete: boolean;
  searchQuery: string;
  filters: any;
  selectedDate: Date | undefined;
  dateFilterType: string;
}

export const useTenderTablePagination = ({
  totalItems,
  itemsPerPage,
  isLoading,
  initialLoadComplete,
  searchQuery,
  filters,
  selectedDate,
  dateFilterType,
}: UseTenderTablePaginationProps) => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedPage = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  
  const initialPageRef = useRef<number>(requestedPage);
  const initialPageAppliedRef = useRef<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [lastKnownPage, setLastKnownPage] = useState(1);
  
  // Track previous values to detect what changed
  const prevSearchQuery = useRef(searchQuery);
  const prevFilters = useRef(filters);
  const prevSelectedDate = useRef(selectedDate);
  const prevDateFilterType = useRef(dateFilterType);
  const pageBeforeSearch = useRef(currentPage);

  const totalPages = Math.ceil(totalItems / itemsPerPage);

  // Function to safely get page number from URL
  const getPageFromUrl = useCallback(() => {
    const pageParam = searchParams.get('page');
    const parsedPage = pageParam ? parseInt(pageParam, 10) : 1;
    return isNaN(parsedPage) || parsedPage < 1 ? 1 : parsedPage;
  }, [searchParams]);

  const updateCurrentPage = useCallback((newPage: number, isUserTriggered = false) => {
    setCurrentPage(newPage);

    if (isUserTriggered) {
      startTransition(() => {
        setTimeout(() => {
          const params = new URLSearchParams(window.location.search);
          params.set('page', newPage.toString());
          router.replace(`?${params.toString()}`, { scroll: false });
        }, 0);
      });
    } else {
      const params = new URLSearchParams(window.location.search);
      params.set('page', newPage.toString());
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }, [router]);

  // Set the page only after data is loaded and validated
  useEffect(() => {
    if (!isLoading && !initialPageAppliedRef.current) {
      const pages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
      const toUse = Math.min(initialPageRef.current, pages);
      setCurrentPage(toUse);
      initialPageAppliedRef.current = true;
    }
  }, [isLoading, totalItems, itemsPerPage]);

  // Handle filter changes
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
          const totalFilteredPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
          const targetPage = Math.min(pageBeforeSearch.current, totalFilteredPages);
          updateCurrentPage(targetPage, false);
        } else if (wasEmpty && !isNowEmpty) {
          pageBeforeSearch.current = currentPage;
          updateCurrentPage(1, false);
        } else if (!wasEmpty && !isNowEmpty) {
          updateCurrentPage(1, false);
        }
      } else {
        const totalFilteredPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
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
    totalItems,
    isLoading,
    updateCurrentPage,
    itemsPerPage
  ]);

  // Listen for URL changes (browser back/forward)
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
  }, [getPageFromUrl, currentPage]);

  // Reset the page when filters change, but not on initial load
  useEffect(() => {
    if (initialLoadComplete) {
      if (currentPage > 1) {
        setLastKnownPage(currentPage);
      }
      updateCurrentPage(1);
    }
  }, [filters, searchQuery, selectedDate, dateFilterType, initialLoadComplete]);

  return {
    currentPage,
    totalPages,
    lastKnownPage,
    setLastKnownPage,
    updateCurrentPage,
    getPageFromUrl
  };
};
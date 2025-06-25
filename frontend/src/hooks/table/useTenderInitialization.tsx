import { useEffect, useRef } from 'react';
import { TenderAnalysisResult } from "@/types/tenders";

interface UseTenderInitializationProps {
  isLoading: boolean;
  requestedTenderId: string | null;
  selectedResult: TenderAnalysisResult | null;
  allResults: TenderAnalysisResult[];
  sortedResults: TenderAnalysisResult[];
  currentResults: TenderAnalysisResult[];
  currentPage: number;
  updateCurrentPage: (page: number, isUserTriggered?: boolean) => void;
  handleRowClick: (result: TenderAnalysisResult) => Promise<void>;
  fetchTenderResultById: (resultId: string) => Promise<TenderAnalysisResult | null>;
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  LOCAL_ITEMS_PER_PAGE: number;
  requestedPage: number;
  initialPageAppliedRef: React.MutableRefObject<boolean>;
  filteredResults: TenderAnalysisResult[];
  setCurrentPage: (page: number) => void;
}

export const useTenderInitialization = ({
  isLoading,
  requestedTenderId,
  selectedResult,
  allResults,
  sortedResults,
  currentResults,
  currentPage,
  updateCurrentPage,
  handleRowClick,
  fetchTenderResultById,
  setAllResults,
  LOCAL_ITEMS_PER_PAGE,
  requestedPage,
  initialPageAppliedRef,
  filteredResults,
  setCurrentPage
}: UseTenderInitializationProps) => {
  const hasAutoOpenedRef = useRef(false);
  const initialPageRef = useRef<number>(requestedPage);

  useEffect(() => {
    if (!isLoading && !initialPageAppliedRef.current) {
      const total = filteredResults.length;
      const pages = Math.max(1, Math.ceil(total / LOCAL_ITEMS_PER_PAGE));

      const toUse = Math.min(initialPageRef.current, pages);

      setCurrentPage(toUse);
      initialPageAppliedRef.current = true;
    }
  }, [isLoading, filteredResults.length, LOCAL_ITEMS_PER_PAGE, setCurrentPage]);

  useEffect(() => {
    if (!isLoading && requestedTenderId && !selectedResult) {
      const match = allResults.find(r => r._id === requestedTenderId);
      if (match) {
        handleRowClick(match);
      } else {
        fetchTenderResultById(requestedTenderId)
          .then(full => {
            if (full) {
              setAllResults(prev => [...prev, full]);
              handleRowClick(full);
            }
          })
          .catch(console.error);
      }
    }
  }, [isLoading, requestedTenderId, allResults, selectedResult, handleRowClick, fetchTenderResultById, setAllResults]);

  useEffect(() => {
    if (hasAutoOpenedRef.current) return;
    if (isLoading || !requestedTenderId) return;
    const idx = sortedResults.findIndex(r => r._id === requestedTenderId);
    if (idx === -1) return;
    const pageOfTender = Math.floor(idx / LOCAL_ITEMS_PER_PAGE) + 1;
    if (currentPage !== pageOfTender) {
      updateCurrentPage(pageOfTender);
      return;
    }
    const match = currentResults.find(r => r._id === requestedTenderId);
    if (!match) return;
    hasAutoOpenedRef.current = true;
    handleRowClick(match);
  }, [
    isLoading,
    requestedTenderId,
    sortedResults,
    currentPage,
    currentResults,
    updateCurrentPage,
    handleRowClick,
    LOCAL_ITEMS_PER_PAGE,
  ]);

  return {
    hasAutoOpenedRef
  };
};
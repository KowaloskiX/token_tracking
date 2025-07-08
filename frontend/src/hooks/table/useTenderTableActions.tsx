import { useRef, useCallback, startTransition, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTender } from '@/context/TenderContext';

interface UseTenderTableActionsProps {
  allResults: TenderAnalysisResult[];
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  selectedAnalysis: any;
  selectedResult: TenderAnalysisResult | null;
  setSelectedResult: (result: TenderAnalysisResult | null) => void;
  setCurrentTenderBoardStatus: React.Dispatch<React.SetStateAction<string | null>>;
  drawerRef: React.RefObject<{ setVisibility: (value: boolean) => void }>;
  currentPage: number;
  getTenderBoards: (tenderId: string) => string[];
  setLastKnownPage: (page: number) => void;
}

export const useTenderTableActions = ({
  allResults,
  setAllResults,
  selectedAnalysis,
  selectedResult,
  setSelectedResult,
  setCurrentTenderBoardStatus,
  drawerRef,
  currentPage,
  getTenderBoards,
  setLastKnownPage
}: UseTenderTableActionsProps) => {
  const router = useRouter();
  const {
    deleteTenderResult,
    markAsOpened,
    markAsUnopened,
    updateTenderStatus,
    fetchTenderResultById,
  } = useTender();

  const justMarkedAsUnreadRef = useRef<string | null>(null);
  const operationInProgressRef = useRef<Set<string>>(new Set());
  const lastClickTimeRef = useRef<number>(0);
  const [sidebarVisible, setSidebarVisible] = useState(false);

  const isUpdatedAfterOpened = useCallback((result: TenderAnalysisResult) => {
    if (!result.updated_at || !result.opened_at) return false;
    const updatedTime = new Date(result.updated_at).getTime();
    const openedTime = new Date(result.opened_at).getTime();
    return updatedTime > openedTime;
  }, []);

  const handleRowClick = useCallback(async (result: TenderAnalysisResult, event?: React.MouseEvent) => {
    const now = Date.now();
    const timeSinceLastClick = now - lastClickTimeRef.current;
    
    if (timeSinceLastClick < 300) {
      return;
    }
    lastClickTimeRef.current = now;

    if (operationInProgressRef.current.has(result._id!)) {
      return;
    }

    if (event?.ctrlKey || event?.metaKey) {
      // NEW: Open the individual tender page instead of the analysis page
      const url = `${window.location.origin}/dashboard/tender/${result._id}`;
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }

    operationInProgressRef.current.add(result._id!);

    try {
      // REMOVED: No longer save page when opening sidebar
      // The user should stay on current page when they close the sidebar
      
      const tenderBoards = getTenderBoards(result._id!);
      const boardStatus = tenderBoards.length
        ? tenderBoards.length === 1
          ? tenderBoards[0]
          : `${tenderBoards[0].length > 10
            ? tenderBoards[0].slice(0, 10) + '…'
            : tenderBoards[0]}+${tenderBoards.length - 1}`
        : null;

      setCurrentTenderBoardStatus(boardStatus);
      setSelectedResult(result);
      setSidebarVisible(true);
      drawerRef.current?.setVisibility(true);

      startTransition(() => {
        setTimeout(() => {
          const params = new URLSearchParams(window.location.search);
          params.set("page", currentPage.toString());
          params.set("tenderId", result._id!);
          router.replace(`?${params.toString()}`, { scroll: false });
        }, 0);
      });

      const promises: Promise<any>[] = [];
      const hasUpdate = isUpdatedAfterOpened(result);

      if ((!result.opened_at || hasUpdate) && justMarkedAsUnreadRef.current !== result._id) {
        const openedAt = new Date().toISOString();
        setAllResults(prev =>
          prev.map(item =>
            item._id === result._id
              ? { ...item, opened_at: openedAt }
              : item
          )
        );
        
        markAsOpened(result._id!).catch(err => {
          console.error('[TendersList] Failed to mark as opened:', err);
        });
      }

      if (!result.criteria_analysis || !Array.isArray(result.criteria_analysis) || result.criteria_analysis.length === 0) {
        promises.push(
          fetchTenderResultById(result._id!).then(fullResult => {
            if (fullResult) {
              setAllResults(prev =>
                prev.map(item =>
                  item._id === result._id
                    ? { 
                        ...item, 
                        ...fullResult,
                        opened_at: item.opened_at && item.opened_at !== fullResult.opened_at 
                          ? item.opened_at 
                          : fullResult.opened_at
                      }
                    : item
                )
              );
              const updatedFullResult = {
                ...fullResult,
                opened_at: fullResult.opened_at || result.opened_at
              };
              setSelectedResult(updatedFullResult);
            }
          }).catch(err => {
            console.error("[TendersList] Error fetching data in background:", err);
          })
        );
      }

      if (promises.length > 0) {
        await Promise.allSettled(promises);
      }

    } finally {
      operationInProgressRef.current.delete(result._id!);
    }
  }, [
    currentPage,
    selectedAnalysis?._id,
    getTenderBoards,
    setCurrentTenderBoardStatus,
    setSelectedResult,
    drawerRef,
    router,
    fetchTenderResultById,
    setAllResults,
    markAsOpened,
    isUpdatedAfterOpened,
  ]);

  const handleUnopened = async (result: TenderAnalysisResult) => {
    if (operationInProgressRef.current.has(result._id!)) {
      return;
    }

    if (result.opened_at && result.opened_at !== "") {
      operationInProgressRef.current.add(result._id!);
      
      try {
        justMarkedAsUnreadRef.current = result._id!;
        setSidebarVisible(false);
        setSelectedResult(null);
        drawerRef.current?.setVisibility(false);
        
        const params = new URLSearchParams(window.location.search);
        params.delete("tenderId");
        router.replace(`?${params.toString()}`, { scroll: false });

        setAllResults(prev =>
          prev.map(item =>
            item._id === result._id
              ? { ...item, opened_at: "" }
              : item
          )
        );

        markAsUnopened(result._id!).catch(err => {
          console.error('Failed to mark as unopened:', err);
        });

        setTimeout(() => {
          justMarkedAsUnreadRef.current = null;
        }, 1000);

      } catch (err) {
        console.error('Failed to mark as unopened:', err);
      } finally {
        operationInProgressRef.current.delete(result._id!);
      }
    } else {
      closeDrawer();
    }
  };

  const handleDelete = async (event: React.MouseEvent, resultId: any) => {
    event.stopPropagation();
    if (!resultId) return;
    try {
      drawerRef.current?.setVisibility(false);

      setAllResults(prev =>
        prev.filter((tender) => tender._id !== resultId)
      );
      if (selectedResult?._id === resultId) {
        closeDrawer();
      }
      await deleteTenderResult(resultId);
    } catch (error) {
      console.error('Error deleting result:', error);
    }
  };

  const handleStatusChange = async (resultId: string, newStatus: 'inactive' | 'active' | 'archived' | 'filtered') => {
    try {
      await updateTenderStatus(resultId, newStatus);
      setAllResults((prevResults) =>
        prevResults.map((tender) =>
          tender._id === resultId
            ? { ...tender, status: newStatus }
            : tender
        )
      );
    } catch (error) {
      console.error("Failed to update status:", error);
    }
  };

  const closeDrawer = () => {
    // MODIFIED: Don't save current page when closing drawer
    // User should stay on the current page, not revert to previous page
    setSidebarVisible(false);
    setSelectedResult(null);
    drawerRef.current?.setVisibility(false);

    startTransition(() => {
      setTimeout(() => {
        const params = new URLSearchParams(window.location.search);
        params.delete("tenderId");
        router.replace(`?${params.toString()}`, { scroll: false });
      }, 0);
    });
  };

  return {
    handleRowClick,
    handleUnopened,
    handleDelete,
    handleStatusChange,
    closeDrawer,
    isUpdatedAfterOpened
  };
};
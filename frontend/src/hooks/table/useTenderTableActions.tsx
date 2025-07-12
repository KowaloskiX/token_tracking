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
    // Handle Ctrl+Click for new tab
    if (event?.ctrlKey || event?.metaKey) {
      const url = `${window.location.origin}/dashboard/tender/${result._id}`;
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }

    // STEP 1: ALWAYS mark as read instantly (no conditions, no exceptions)
    const openedAt = new Date().toISOString();

    // INSTANT UI UPDATE - always do this, no matter what
    setAllResults(prev =>
      prev.map(item =>
        item._id === result._id
          ? { ...item, opened_at: openedAt }
          : item
      )
    );

    // Background API call (fire and forget)
    markAsOpened(result._id!).catch(err => {
      console.error('[TendersList] Background API call failed:', err);
    });

    // STEP 2: Handle sidebar and selection (with minimal debouncing only for sidebar)
    const now = Date.now();
    const timeSinceLastClick = now - lastClickTimeRef.current;

    // Only debounce sidebar opening, not read status
    if (timeSinceLastClick < 100) {
      return; // Already marked as read above, just skip sidebar update
    }
    lastClickTimeRef.current = now;

    // STEP 3: Update sidebar and selection
    try {
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

      // Update URL
      startTransition(() => {
        setTimeout(() => {
          const params = new URLSearchParams(window.location.search);
          params.set("page", currentPage.toString());
          params.set("tenderId", result._id!);
          router.replace(`?${params.toString()}`, { scroll: false });
        }, 0);
      });

      // STEP 4: Background fetch for detailed data (if needed)
      if (!result.criteria_analysis || !Array.isArray(result.criteria_analysis) || result.criteria_analysis.length === 0) {
        fetchTenderResultById(result._id!)
          .then(fullResult => {
            if (fullResult) {
              setAllResults(prev =>
                prev.map(item =>
                  item._id === result._id
                    ? {
                      ...item,
                      ...fullResult,
                      // Preserve the opened_at we set above (never overwrite with older data)
                      opened_at: item.opened_at || fullResult.opened_at
                    }
                    : item
                )
              );

              // Update selected result with fresh data
              const updatedFullResult = {
                ...fullResult,
                opened_at: result.opened_at || fullResult.opened_at
              };
              setSelectedResult(updatedFullResult);
            }
          })
          .catch(err => {
            console.error("[TendersList] Background fetch failed:", err);
          });
      }

    } catch (err) {
      console.error('[TendersList] Error in sidebar handling:', err);
    }
  }, [
    currentPage,
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
    if (!result.opened_at || result.opened_at === "") {
      // Already unread, just close drawer
      closeDrawer();
      return;
    }

    // STEP 1: INSTANTLY mark as unread
    setAllResults(prev =>
      prev.map(item =>
        item._id === result._id
          ? { ...item, opened_at: "" }
          : item
      )
    );

    // STEP 2: Close drawer and clear selection
    setSidebarVisible(false);
    setSelectedResult(null);
    drawerRef.current?.setVisibility(false);

    const params = new URLSearchParams(window.location.search);
    params.delete("tenderId");
    router.replace(`?${params.toString()}`, { scroll: false });

    // STEP 3: Background API call (fire and forget)
    markAsUnopened(result._id!)
      .catch(err => {
        console.error('Background API call failed for mark as unread:', err);
      });
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
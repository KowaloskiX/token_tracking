"use client";

import { useEffect, useState, useRef, useMemo, useCallback, startTransition } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { useTender } from "@/context/TenderContext";
import { TenderAnalysisResult } from "@/types/tenders";
import { AddToKanbanDialog } from "./AddToKanbanDialog";
import { useRouter, useSearchParams } from "next/navigation";
import { TenderFilters, Filters } from "./TenderFilters";
import { TenderTable } from "./table/TenderTable";
import { TendersPagination } from "./table/TendersPagination";
import { useTenderUtils } from "@/hooks/table/useTenderUtils";
import { useKanbanBoards } from "@/hooks/table/useKanbabBoards";
import { useTenderActions } from "@/hooks/table/useTenderActions";
import { useTenderSorting } from "@/hooks/table/useTenderSorting";
import { usePaginationEffects } from "@/hooks/table/usePaginationEffects";
import { useTenderInitialization } from "@/hooks/table/useTenderInitialization";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";
import { useTableLayout } from "@/hooks/table/useTableLayout";
import { SortableField } from "@/types/table";

const LOCAL_ITEMS_PER_PAGE = 10;

interface TendersListProps {
  drawerRef: React.RefObject<{ setVisibility: (value: boolean) => void }>;
  allResults: TenderAnalysisResult[];
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  setCurrentTenderBoardStatus: React.Dispatch<React.SetStateAction<string | null>>;
}

const TendersList: React.FC<TendersListProps> = ({ 
  drawerRef, 
  allResults, 
  setAllResults, 
  setCurrentTenderBoardStatus 
}) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  const {
    selectedAnalysis,
    selectedResult,
    setSelectedResult,
    fetchTenderResultById,
  } = useTender();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedPage = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  const requestedTenderId = searchParams.get("tenderId") || null;
  const hasAutoOpenedRef = useRef(false);

  const initialPageRef = useRef<number>(requestedPage);
  const initialPageAppliedRef = useRef<boolean>(false);

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [totalFetched, setTotalFetched] = useState(0);
  const [totalTendersCount, setTotalTendersCount] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [dateFilterType, setDateFilterType] = useState<'initiation_date' | 'submission_deadline'>('initiation_date');
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupMessage, setPopupMessage] = useState("");
  const [addToKanbanSuccess, setAddToKanbanSuccess] = useState<boolean | null>(null);
  const [showKanbanDialog, setShowKanbanDialog] = useState(false);
  const [tableWidth, setTableWidth] = useState(0);
  const [includeHistorical, setIncludeHistorical] = useState(false);

  const tableContainerRef = useRef<HTMLDivElement>(null);

  type VoivodeshipKey = keyof typeof filters.voivodeship;

  const [filters, setFilters] = useState<Filters>({
    onlyQualified: false,
    status: { inactive: true, active: true, archived: false, inBoard: true },
    voivodeship: {
      "Dolnośląskie": true,
      "Kujawsko-pomorskie": true,
      "Lubelskie": true,
      "Lubuskie": true,
      "Łódzkie": true,
      "Małopolskie": true,
      "Mazowieckie": true,
      "Opolskie": true,
      "Podkarpackie": true,
      "Podlaskie": true,
      "Pomorskie": true,
      "Śląskie": true,
      "Świętokrzyskie": true,
      "Warmińsko-mazurskie": true,
      "Wielkopolskie": true,
      "Zachodniopomorskie": true
    },
    source: {},
    criteria: {},
  });

  const {
    truncateText,
    calculateDaysRemaining,
    formatDate,
    extractHour,
    formatDateTime,
    calculateProgressPercentage,
    isUpdatedAfterOpened
  } = useTenderUtils();

  const {
    kanbanBoards,
    boardsLoading,
    fetchKanbanBoards,
    getTenderBoards
  } = useKanbanBoards();

  const {
    currentLayout,
    visibleColumns,
    updateColumnWidth,
    updateColumnVisibility,
    addCriteriaColumn,
    removeCriteriaColumn,
  } = useTableLayout({ selectedAnalysis });

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

  const {
    handleRowClick,
    handleUnopened,
    handleDelete,
    handleStatusChange,
    closeDrawer
  } = useTenderActions({
    drawerRef,
    selectedAnalysis,
    currentPage,
    setSelectedResult,
    setAllResults,
    setCurrentTenderBoardStatus,
    getTenderBoards,
    fetchTenderResultById,
    isUpdatedAfterOpened
  });

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

  useEffect(() => {
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setTableWidth(entry.contentRect.width);
      }
    });
    if (tableContainerRef.current) {
      resizeObserver.observe(tableContainerRef.current);
    }
    return () => resizeObserver.disconnect();
  }, []);

  const filteredResults = useMemo(() => {
    return allResults.filter((result) => {
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
  }, [allResults, filters, getTenderBoards, searchQuery, selectedDate, dateFilterType]);

  const { sortConfig, sortedResults, handleSort } = useTenderSorting({ 
    filteredResults, 
    calculateDaysRemaining,
    selectedDate 
  });

  usePaginationEffects({
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
  });

  useTenderInitialization({
    isLoading,
    requestedTenderId,
    selectedResult,
    allResults,
    sortedResults,
    currentResults: sortedResults.slice(
      (currentPage - 1) * LOCAL_ITEMS_PER_PAGE,
      currentPage * LOCAL_ITEMS_PER_PAGE
    ),
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
  });

  const totalPages = Math.ceil(sortedResults.length / LOCAL_ITEMS_PER_PAGE);
  const currentResults = sortedResults.slice(
    (currentPage - 1) * LOCAL_ITEMS_PER_PAGE,
    currentPage * LOCAL_ITEMS_PER_PAGE
  );

  const handlePopupClose = () => {
    setPopupOpen(false);
    setAddToKanbanSuccess(null);
    router.push("/dashboard/tenders/management");
  };

  const handleAddToKanban = useCallback((result: TenderAnalysisResult) => {
    setSelectedResult(result);
    setShowKanbanDialog(true);
  }, [setSelectedResult]);

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
    return selectedAnalysis.criteria.map(c => c.name);
  }, [selectedAnalysis?.criteria]);

  return (
    <div className="sm:px-8 py-2">
      <Card className="rounded-none sm:rounded-lg shadow">
        <CardHeader>
          <div className="flex justify-between flex-wrap sm:flex-nowrap gap-4">
            <div className="w-full sm:w-auto">
              <div className="flex items-center gap-2">
                <CardTitle className="text-xl sm:text-2xl leading-tight">{selectedAnalysis?.name}</CardTitle>
                {selectedAnalysis && (
                  <Badge
                    variant={(selectedAnalysis.assigned_users?.length ?? 0) > 1 ? "default" : "secondary"}
                    className="text-xs font-medium ml-2"
                  >
                    {(selectedAnalysis.assigned_users?.length ?? 0) > 1
                      ? t('tenders.edit.share.sharedBadge')
                      : t('tenders.edit.share.privateBadge')}                  
                    </Badge>
                )}
              </div>
              <CardDescription className="mt-1">
                {isLoading
                  ? t('tenders.list.loading', {
                    fetched: totalFetched,
                    total: totalTendersCount !== null ? ` / ${totalTendersCount}` : ''
                  })
                  : t('tenders.list.loaded', {
                    count: allResults?.length || 0,
                    historical: includeHistorical ? ` ${t('tenders.list.historical')}` : ''
                  })
                }
              </CardDescription>
            </div>

            <div className="flex gap-2">
              <Button
                variant={includeHistorical ? "default" : "outline"}
                size="sm"
                onClick={() => setIncludeHistorical(!includeHistorical)}
                disabled={isLoading}
                className="whitespace-nowrap"
              >
                <Clock className="h-4 w-4 mr-2" />
                {includeHistorical
                  ? t('tenders.list.hideHistorical')
                  : t('tenders.list.loadHistorical')}
              </Button>
            </div>
          </div>

          <TenderFilters
            filters={filters}
            setFilters={setFilters}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            dateFilterType={dateFilterType}
            setDateFilterType={setDateFilterType}
            sortConfig={sortConfig}
            handleSort={handleSort}
            availableSources={availableSources}
            availableCriteria={availableCriteria}
            selectedAnalysis={selectedAnalysis}
            tableColumns={currentLayout?.columns}
            onColumnVisibilityChange={updateColumnVisibility}
            onAddCriteriaColumn={addCriteriaColumn}
            onRemoveCriteriaColumn={removeCriteriaColumn}
          />
        </CardHeader>
        <CardContent className="overflow-x-auto" ref={tableContainerRef} >
        <TenderTable
          results={currentResults}
          selectedResult={selectedResult}
          tableWidth={tableWidth}
          isLoading={isLoading}
          totalFetched={totalFetched}
          totalTendersCount={totalTendersCount}
          allResults={allResults}
          selectedAnalysis={selectedAnalysis}
          getTenderBoards={getTenderBoards}
          boardsLoading={boardsLoading}
          isUpdatedAfterOpened={isUpdatedAfterOpened}
          calculateDaysRemaining={calculateDaysRemaining}
          calculateProgressPercentage={calculateProgressPercentage}
          formatDate={formatDate}
          extractHour={extractHour}
          formatDateTime={formatDateTime}
          truncateText={truncateText}
          onRowClick={handleRowClick}
          onStatusChange={handleStatusChange}
          onUnopened={handleUnopened}
          onDelete={handleDelete}
          onAddToKanban={handleAddToKanban}
          visibleColumns={visibleColumns}
          onColumnResize={updateColumnWidth}
          onSort={handleSort}
          sortConfig={sortConfig}
        />
          <TendersPagination
            totalPages={totalPages}
            currentPage={currentPage}
            onPageChange={updateCurrentPage}
          />
        </CardContent>
      </Card>

      {selectedResult && (
        <AddToKanbanDialog
          open={showKanbanDialog}
          onOpenChange={(isOpen) => {
            setShowKanbanDialog(isOpen);
            if (!isOpen) {
              setSelectedResult(null);
            }
          }}
          tender={selectedResult}
          onAddSuccess={(boardId) => {
            setShowKanbanDialog(false);
            setSelectedResult(null);
            setTimeout(() => {
              setPopupMessage(t('tenders.kanban.addSuccess'));
              setAddToKanbanSuccess(true);
              setPopupOpen(true);
              fetchKanbanBoards();
            }, 100);
          }}
          onAddError={(error) => {
            setShowKanbanDialog(false);
            setSelectedResult(null);
            setTimeout(() => {
              setPopupMessage(t('tenders.kanban.addError'));
              setAddToKanbanSuccess(false);
              setPopupOpen(true);
            }, 100);
          }}
        />
      )}

      {popupOpen && (
        <Dialog open={popupOpen} onOpenChange={setPopupOpen}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <div className="flex flex-col items-center text-center space-y-4">
                <div className={`rounded-full p-3 ${addToKanbanSuccess ? 'bg-success/15' : 'bg-destructive/15'}`}>
                  {addToKanbanSuccess ? (
                    <CheckCircle2 className="h-8 w-8 text-success" strokeWidth={1.5} />
                  ) : (
                    <XCircle className="h-8 w-8 text-destructive" strokeWidth={1.5} />
                  )}
                </div>
                <DialogTitle className="text-lg font-semibold leading-none tracking-tight">
                  {popupMessage}
                </DialogTitle>
              </div>
            </DialogHeader>
            <DialogFooter className="sm:justify-center gap-2">
              {addToKanbanSuccess && (
                <Button
                  onClick={handlePopupClose}
                  variant="default"
                  className="px-6"
                >
                  {t('tenders.kanban.showAllBoards')}
                </Button>
              )}
              <Button
                onClick={() => {
                  setPopupOpen(false);
                  setAddToKanbanSuccess(null);
                }}
                variant={addToKanbanSuccess ? "outline" : "default"}
                className="px-6"
              >
                {addToKanbanSuccess ? t('tenders.kanban.stayHere') : t('tenders.kanban.exit')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default TendersList;
"use client";

import { useEffect, useState, useRef, useMemo, useCallback, startTransition } from "react";
import AllTendersPopup from "./AllTendersPopup";
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
import { useRouter, useSearchParams } from "next/navigation";
import { TenderFilters, Filters } from "./TenderFilters";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";
import { AddToKanbanDialog } from "./AddToKanbanDialog";

// Import the new components and hooks
import { useTenderTablePagination } from "@/hooks/table/useTenderTablePagination";
import { useTenderTableActions } from "@/hooks/table/useTenderTableActions";
import { useTenderTableData } from "@/hooks/table/useTenderTableData";
import { TenderTable } from "./table/TenderTable";

const LOCAL_ITEMS_PER_PAGE = 10;

interface KanbanBoardTenderItem {
  id?: string;
  board_id: string;
  column_id: string;
  tender_analysis_result_id: string;
  order: number;
  created_at?: string;
  updated_at?: string;
}

interface KanbanColumn {
  id?: string;
  name: string;
  order?: number;
  color?: string;
  limit?: number;
  tender_items: KanbanBoardTenderItem[];
}

interface KanbanBoard {
  id?: string;
  _id?: string;
  user_id: string;
  org_id?: string;
  name: string;
  shared_with: string[];
  created_at?: string;
  updated_at?: string;
  columns: KanbanColumn[];
  assigned_users: string[];
}

interface TendersListProps {
  allResults: TenderAnalysisResult[];
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  drawerRef: React.RefObject<{ setVisibility: (value: boolean) => void }>;
  setCurrentTenderBoardStatus: React.Dispatch<React.SetStateAction<string | null>>;
  isDrawerVisible: boolean; // NEW: Add this prop
  onDrawerVisibilityChange: (visible: boolean) => void; // NEW: Add this prop
}

const TendersList: React.FC<TendersListProps> = ({
  drawerRef,
  allResults,
  setAllResults,
  setCurrentTenderBoardStatus,
  isDrawerVisible, // NEW: Accept this prop
  onDrawerVisibilityChange // NEW: Accept this prop
}) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  const {
    selectedAnalysis,
    selectedResult,
    setSelectedResult,
  } = useTender();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTenderId = searchParams.get("tenderId") || null;
  const hasAutoOpenedRef = useRef(false);

  // Track the initial load
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [dateFilterType, setDateFilterType] = useState<'initiation_date' | 'submission_deadline'>('initiation_date');

  const [popupOpen, setPopupOpen] = useState(false);
  const [popupMessage, setPopupMessage] = useState("");
  const [addToKanbanSuccess, setAddToKanbanSuccess] = useState<boolean | null>(null);

  // Add kanban boards state
  const [kanbanBoards, setKanbanBoards] = useState<KanbanBoard[]>([]);
  const [boardsLoading, setBoardsLoading] = useState(false);

  // FIXED: Changed sortConfig type to allow string instead of restrictive union
  const [sortConfig, setSortConfig] = useState<{
    field: string; // Changed from restrictive union to string
    direction: 'asc' | 'desc';
  } | null>(null);

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

  const [showKanbanDialog, setShowKanbanDialog] = useState(false);
  const [includeHistorical, setIncludeHistorical] = useState(false);

  // Function to find which boards a tender belongs to
  const getTenderBoards = useCallback((tenderId: string): string[] => {
    const boardNames: string[] = [];
    for (const board of kanbanBoards) {
      for (const column of board.columns) {
        const hasItem = column.tender_items.some(item => item.tender_analysis_result_id === tenderId);
        if (hasItem) {
          boardNames.push(board.name);
          break;
        }
      }
    }
    return boardNames;
  }, [kanbanBoards]);

  // Function to fetch kanban boards
  const fetchKanbanBoards = useCallback(async () => {
    try {
      setBoardsLoading(true);
      const token = localStorage.getItem("token") || "";
      const url = `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/boards`;

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const boards = await response.json();
        setKanbanBoards(boards);
      } else {
        console.error("Failed to fetch kanban boards");
        setKanbanBoards([]);
      }
    } catch (error) {
      console.error("Error fetching kanban boards:", error);
      setKanbanBoards([]);
    } finally {
      setBoardsLoading(false);
    }
  }, []);

  // Use the new hooks
  const {
    isLoading,
    totalFetched,
    totalTendersCount,
    filteredResults,
    sortedResults,
    availableSources,
    availableCriteria,
    calculateDaysRemaining
  } = useTenderTableData({
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
  });

  const {
    currentPage,
    totalPages,
    lastKnownPage,
    setLastKnownPage,
    updateCurrentPage
  } = useTenderTablePagination({
    totalItems: sortedResults.length,
    itemsPerPage: LOCAL_ITEMS_PER_PAGE,
    isLoading,
    initialLoadComplete,
    searchQuery,
    filters,
    selectedDate,
    dateFilterType
  });

  const {
    handleRowClick,
    handleUnopened,
    handleDelete,
    handleStatusChange,
    closeDrawer,
    isUpdatedAfterOpened
  } = useTenderTableActions({
    allResults,
    setAllResults,
    selectedAnalysis,
    selectedResult,
    setSelectedResult,
    setCurrentTenderBoardStatus,
    drawerRef,
    currentPage,
    getTenderBoards,
    setLastKnownPage,
    onDrawerVisibilityChange
  });

  // Fetch kanban boards when component mounts
  useEffect(() => {
    fetchKanbanBoards();
  }, [fetchKanbanBoards]);

  // Restore page when drawer closes
  useEffect(() => {
    if (!selectedResult && lastKnownPage > 1) {
      updateCurrentPage(lastKnownPage, false);
    }
  }, [selectedResult, lastKnownPage, updateCurrentPage]);

  const currentResults = sortedResults.slice(
    (currentPage - 1) * LOCAL_ITEMS_PER_PAGE,
    currentPage * LOCAL_ITEMS_PER_PAGE
  );

  // FIXED: Updated handleSort to work with flexible field types
  const handleSort = (field: string) => {
    setSortConfig(current => {
      if (current?.field === field) {
        return { field, direction: current.direction === 'asc' ? 'desc' : 'asc' };
      }

      // Set default direction based on field type
      let defaultDirection: 'asc' | 'desc' = 'asc';
      if (field === 'tender_score' || field === 'updated_at' || field === 'created_at') {
        defaultDirection = 'desc'; // Scores and dates default to descending
      }

      return { field, direction: defaultDirection };
    });
  };

  const handlePopupClose = () => {
    setPopupOpen(false);
    setAddToKanbanSuccess(null);
    router.push("/dashboard/tenders/management");
  };

  const handleAddToKanban = (result: TenderAnalysisResult) => {
    setSelectedResult(result);
    setShowKanbanDialog(true);
  };

  // Handle auto-opening tender from URL
  useEffect(() => {
    if (hasAutoOpenedRef.current) return;
    if (isLoading || !requestedTenderId) return;
    const idx = sortedResults.findIndex(r => r._id === requestedTenderId);
    if (idx === -1) return;
    const pageOfTender = Math.floor(idx / LOCAL_ITEMS_PER_PAGE) + 1;
    if (currentPage !== pageOfTender) {
      updateCurrentPage(pageOfTender, false);
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
  ]);

  return (
    <div className="sm:px-8 py-2 w-full max-w-full overflow-x-auto overflow-y-hidden">
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
            availableCriteria={selectedAnalysis?.criteria?.map((c: any) => c.name) || []} // Pass just the names for filter
          />
        </CardHeader>

        <CardContent>
          <TenderTable
            currentResults={currentResults}
            selectedResult={selectedResult}
            selectedAnalysis={selectedAnalysis}
            isLoading={isLoading}
            totalFetched={totalFetched}
            totalTendersCount={totalTendersCount}
            allResultsLength={allResults.length}
            currentPage={currentPage}
            totalPages={totalPages}
            availableCriteria={availableCriteria}
            isUpdatedAfterOpened={isUpdatedAfterOpened}
            calculateDaysRemaining={calculateDaysRemaining}
            getTenderBoards={getTenderBoards}
            boardsLoading={boardsLoading}
            onRowClick={handleRowClick}
            onStatusChange={handleStatusChange}
            onUnopened={handleUnopened}
            isDrawerVisible={isDrawerVisible}
            onDrawerVisibilityChange={onDrawerVisibilityChange}
            onDelete={handleDelete}
            onAddToKanban={handleAddToKanban}
            onPageChange={(page) => updateCurrentPage(page, true)}
            onSortChange={(columnIdOrCriteriaName, direction) => {
              // Enhanced field mapping that covers all standard column types
              const fieldMap: Record<string, string> = {
                // Standard columns
                'source': 'source',
                'name': 'tender_metadata.name',
                'organization': 'tender_metadata.organization',
                'publication_date': 'initiation_date',
                'submission_deadline': 'submission_deadline',
                'board_status': 'status',
                'score': 'tender_score',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
              };

              // Check if this is a criteria column by seeing if it's a criteria name
              const isCriteriaSort = availableCriteria.some((c: any) => c.name === columnIdOrCriteriaName);

              if (isCriteriaSort) {
                // For criteria columns, use the criteria name directly as the field
                if (direction) {
                  setSortConfig({ field: columnIdOrCriteriaName, direction });
                } else {
                  setSortConfig(null);
                }
              } else {
                // For standard columns, use the field mapping
                const field = fieldMap[columnIdOrCriteriaName];
                if (field && direction) {
                  setSortConfig({ field, direction });
                } else {
                  setSortConfig(null);
                }
              }
            }}
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
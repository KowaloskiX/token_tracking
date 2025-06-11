"use client";

import { useEffect, useState, useRef, useMemo, useCallback, startTransition } from "react";
import AllTendersPopup from "./AllTendersPopup";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import { CheckCircle2, XCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertCircle, Archive, EyeOff, ArrowUpDown, Calendar as CalendarIcon, CheckCircle, ChevronDown, Filter, ListCheck, Loader2, MoreVertical, Percent, RefreshCw, Search, Sparkles, Trash, Clock, Plus, X } from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { useTender } from "@/context/TenderContext";
import { TenderAnalysisResult } from "@/types/tenders";
import { cn } from "@/lib/utils";
import TenderSourceIcon from "./TenderSourceIcon";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useKanban } from "@/context/KanbanContext";
import { AddToKanbanDialog } from "./AddToKanbanDialog";
import { useRouter, useSearchParams } from "next/navigation";
import { TenderFilters, Filters } from "./TenderFilters";
import TenderPageInput from "./TenderPageInput"
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

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
  drawerRef: React.RefObject<{ setVisibility: (value: boolean) => void }>;
  allResults: TenderAnalysisResult[];
  setAllResults: React.Dispatch<React.SetStateAction<TenderAnalysisResult[]>>;
  setCurrentTenderBoardStatus: React.Dispatch<React.SetStateAction<string | null>>;
}

const TendersList: React.FC<TendersListProps> = ({ drawerRef, allResults, setAllResults, setCurrentTenderBoardStatus }) => {
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  const {
    results,
    selectedAnalysis,
    selectedResult,
    setSelectedResult,
    deleteTenderResult,
    markAsOpened,
    markAsUnopened,
    updateTenderStatus,
    fetchTenderResultById,
  } = useTender();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedPage = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  const requestedTenderId = searchParams.get("tenderId") || null;
  const hasAutoOpenedRef = useRef(false);

  const initialPageRef = useRef<number>(requestedPage);
  // and store whether we've applied it:
  const initialPageAppliedRef = useRef<boolean>(false);

  // now default-currentPage can always start at 1:
  const [currentPage, setCurrentPage] = useState<number>(1);
  // Track the initial load
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  type VoivodeshipKey = keyof typeof filters.voivodeship;

  const [isLoading, setIsLoading] = useState(false);
  const [totalFetched, setTotalFetched] = useState(0);
  const [totalTendersCount, setTotalTendersCount] = useState<number | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [dateFilterType, setDateFilterType] = useState<'initiation_date' | 'submission_deadline'>('initiation_date');

  const [popupOpen, setPopupOpen] = useState(false);
  const [popupMessage, setPopupMessage] = useState("");
  const [addToKanbanSuccess, setAddToKanbanSuccess] = useState<boolean | null>(null);

  // Track if we've already handled the initial URL page parameter
  const urlPageHandledRef = useRef(false);

  // Add kanban boards state
  const [kanbanBoards, setKanbanBoards] = useState<KanbanBoard[]>([]);
  const [boardsLoading, setBoardsLoading] = useState(false);

  // Function to safely get page number from URL
  const getPageFromUrl = useCallback(() => {
    const pageParam = searchParams.get('page');
    const parsedPage = pageParam ? parseInt(pageParam, 10) : 1;
    return isNaN(parsedPage) || parsedPage < 1 ? 1 : parsedPage;
  }, [searchParams]);

  const [sortConfig, setSortConfig] = useState<{
    field: 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date';
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
  });
  const [showKanbanDialog, setShowKanbanDialog] = useState(false);
  const [tableWidth, setTableWidth] = useState(0);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const [lastKnownPage, setLastKnownPage] = useState(1);
  const [includeHistorical, setIncludeHistorical] = useState(false);

  // Function to fetch kanban boards
  const fetchKanbanBoards = useCallback(async () => {
    try {
      setBoardsLoading(true);
      const token = localStorage.getItem("token") || "";
      const url = `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/boards`;
      console.log("Fetching kanban boards from:", url);

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const boards = await response.json();
        console.log("Successfully fetched boards:", boards);
        console.log("Board structure sample:", boards[0] ? {
          name: boards[0].name,
          columnsCount: boards[0].columns?.length,
          firstColumnSample: boards[0].columns?.[0] ? {
            name: boards[0].columns[0].name,
            tenderItemsCount: boards[0].columns[0].tender_items?.length
          } : null
        } : "No boards found");
        setKanbanBoards(boards);
      } else {
        console.error("Failed to fetch kanban boards", {
          status: response.status,
          statusText: response.statusText,
          url: response.url
        });
        setKanbanBoards([]);
      }
    } catch (error) {
      console.error("Error fetching kanban boards:", error);
      setKanbanBoards([]);
    } finally {
      setBoardsLoading(false);
    }
  }, []);

  // Function to find which boards a tender belongs to
  const getTenderBoards = useCallback((tenderId: string): string[] => {
    const boardNames: string[] = [];
    for (const board of kanbanBoards) {
      for (const column of board.columns) {
        const hasItem = column.tender_items.some(item => item.tender_analysis_result_id === tenderId);
        if (hasItem) {
          boardNames.push(board.name);
          break; // Break inner loop since we found the tender in this board
        }
      }
    }
    return boardNames;
  }, [kanbanBoards]);

  // Fetch kanban boards when component mounts
  useEffect(() => {
    fetchKanbanBoards();
  }, [fetchKanbanBoards]);

  const updateCurrentPage = useCallback((newPage: number, isUserTriggered = false) => {
    setCurrentPage(newPage);

    if (isUserTriggered) {
      // ← FIXED: Only defer URL update for user-triggered events to avoid DOM conflicts
      startTransition(() => {
        setTimeout(() => {
          // Update URL without reloading the page
          const params = new URLSearchParams(window.location.search);
          params.set('page', newPage.toString());

          // Use router.replace to update URL without adding to browser history
          router.replace(`?${params.toString()}`, { scroll: false });
        }, 0);
      });
    } else {
      // For automatic navigation (initial load, filter changes), update immediately
      const params = new URLSearchParams(window.location.search);
      params.set('page', newPage.toString());
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }, [router]);

  const calculateDaysRemaining = (deadlineStr: string): number => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let deadline: Date;
    // Return NaN for obviously invalid inputs early
    if (!deadlineStr || typeof deadlineStr !== 'string' || deadlineStr.toLowerCase().includes('nan')) {
      return NaN;
    }

    if (deadlineStr.includes('-')) { // ISO-like format (YYYY-MM-DD or YYYY-MM-DD HH:MM...)
      const isoStr = deadlineStr.includes(' ') ? deadlineStr.replace(' ', 'T') : deadlineStr;
      deadline = new Date(isoStr);
    } else if (deadlineStr.includes('.')) {
      const parts = deadlineStr.split('.');
      if (parts.length !== 3 || parts.some(p => isNaN(parseInt(p)))) {
        return NaN; // Invalid DD.MM.YYYY format
      }
      // Ensure year is reasonable (e.g., > 1900)
      const year = parseInt(parts[2]);
      const month = parseInt(parts[1]);
      const day = parseInt(parts[0]);
      // Basic validation for month and day
      if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return NaN;
      deadline = new Date(year, month - 1, day);
    } else if (deadlineStr.includes('/')) { // DD/MM/YYYY or MM/DD/YYYY format with possible timezone
      // Remove timezone info in parentheses if present
      const cleanDeadlineStr = deadlineStr.replace(/\([^)]*\)/g, '').trim();

      // Try to parse with built-in Date constructor first
      deadline = new Date(cleanDeadlineStr);

      // If that fails, try more specific parsing
      if (isNaN(deadline.getTime())) {
        const parts = cleanDeadlineStr.split('/');
        if (parts.length === 3) {
          // Handle both DD/MM/YYYY and MM/DD/YYYY possibilities
          // Assume European format DD/MM/YYYY first
          let day, month, year;

          // If the first part is > 12, it's likely a day (DD/MM/YYYY)
          // Otherwise, try MM/DD/YYYY format
          if (parseInt(parts[0]) > 12) {
            day = parseInt(parts[0]);
            month = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part if present
          } else {
            // Try MM/DD/YYYY format
            month = parseInt(parts[0]);
            day = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part if present
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
      return NaN; // Unrecognized format
    }

    // Final check if date parsing resulted in a valid date
    if (isNaN(deadline.getTime())) {
      return NaN;
    }

    deadline.setHours(0, 0, 0, 0); // Normalize deadline to start of day

    const diffTime = deadline.getTime() - today.getTime();
    // Use floor for days remaining to correctly handle deadlines ending today
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
  };

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
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-analysis/${selectedAnalysis._id}/results?page=${page}&limit=${limit}${historicalParam}`,
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


  // Restore page when drawer closes
  useEffect(() => {
    if (!selectedResult && lastKnownPage > 1) {
      setCurrentPage(lastKnownPage);
    }
  }, [selectedResult, lastKnownPage]);

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

  const mergedData = allResults ? allResults.map((localTender) => {
    const updatedTender = results.find((r) => r._id === localTender._id);
    if (updatedTender) {
      return {
        ...localTender,
        status: updatedTender.status,
      };
    }
    return localTender;
  }) : [];

  const filteredResults = mergedData.filter((result) => {
    if (filters.onlyQualified && result.tender_score < 0.7) return false;

    const status = result.status || "inactive";
    const tenderBoards = getTenderBoards(result._id!);
    const isInBoard = tenderBoards.length > 0;

    // Check if any status filter matches
    const statusMatches =
      (filters.status.inactive && status === 'inactive') ||
      (filters.status.active && status === 'active') ||
      (filters.status.archived && status === 'archived') ||
      (filters.status.inBoard && isInBoard);

    // If no status filter is selected at all, show everything
    const anyStatusFilterSelected = filters.status.inactive || filters.status.active || filters.status.archived || filters.status.inBoard;

    if (anyStatusFilterSelected && !statusMatches) {
      return false;
    }

    // Rest of your existing filtering logic remains the same...
    if (result.location?.voivodeship && result.location.voivodeship !== "UNKNOWN") {
      let voivodeshipFormatted = result.location.voivodeship;

      if (voivodeshipFormatted === voivodeshipFormatted.toUpperCase()) {
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

    return true;
  });

  const sortByTimeIfDateFiltered = (results: TenderAnalysisResult[]) => {
    if (!selectedDate) return results;

    return [...results].sort((a, b) => {
      const aDateStr = dateFilterType === 'initiation_date'
        ? a.tender_metadata.initiation_date
        : a.tender_metadata.submission_deadline;

      const bDateStr = dateFilterType === 'initiation_date'
        ? b.tender_metadata.initiation_date
        : b.tender_metadata.submission_deadline;

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
  };

  let sortedResults = filteredResults;
  if (sortConfig) {
    sortedResults = [...filteredResults].sort((a, b) => {
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
          // Check for obviously invalid strings first
          if (!deadlineStr || deadlineStr.includes('NaN')) {
            return { status: 'invalid', days: Infinity }; // Treat invalid as furthest away
          }

          // Calculate days remaining, this handles different date formats
          const days = calculateDaysRemaining(deadlineStr);

          if (isNaN(days)) {
            // If calculation results in NaN, it's invalid
            return { status: 'invalid', days: Infinity };
          } else if (days < 0) {
            // Negative days means the deadline is in the past
            return { status: 'past', days: days };
          } else {
            // Zero or positive days means the deadline is today or in the future
            return { status: 'future', days: days };
          }
        };

        const aStatus = getDeadlineStatus(a.tender_metadata.submission_deadline);
        const bStatus = getDeadlineStatus(b.tender_metadata.submission_deadline);

        // Define the desired order of statuses
        const statusOrder = { future: 0, past: 1, invalid: 2 };

        // Compare based on status first
        const aOrder = statusOrder[aStatus.status];
        const bOrder = statusOrder[bStatus.status];

        let cmp = 0;

        // Always prioritize by status category: future < past < invalid
        cmp = aOrder - bOrder;

        if (cmp === 0) {
          // If statuses are the same, compare based on days remaining, considering direction
          if (aStatus.status === 'future') {
            // Asc: Nearest future first (smaller days). Desc: Furthest future first (larger days).
            cmp = sortConfig.direction === 'asc'
              ? aStatus.days - bStatus.days
              : bStatus.days - aStatus.days;
          } else if (aStatus.status === 'past') {
            // Asc: Most recent past first (less negative days). Desc: Most distant past first (more negative days).
            // Since days are negative, b-a gives ascending (e.g., -1 vs -5 => -1 - (-5) = 4)
            // Since days are negative, a-b gives descending (e.g., -1 vs -5 => -5 - (-1) = -4)
            cmp = sortConfig.direction === 'asc'
              ? bStatus.days - aStatus.days
              : aStatus.days - bStatus.days;
          }
          // 'invalid' status dates are considered equal regarding deadline time, rely on tie-breaker
        }

        // Final tie-breaker using updated_at (most recent first) if deadlines are equivalent
        if (cmp === 0) {
          const aUpdated = new Date(a.updated_at || '').getTime();
          const bUpdated = new Date(b.updated_at || '').getTime();
          // Always sort by most recent update first as tie-breaker regardless of direction
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
    sortedResults = sortByTimeIfDateFiltered(sortedResults);
  }

  const totalPages = Math.ceil(sortedResults.length / LOCAL_ITEMS_PER_PAGE);
  const currentResults = sortedResults.slice(
    (currentPage - 1) * LOCAL_ITEMS_PER_PAGE,
    currentPage * LOCAL_ITEMS_PER_PAGE
  );

  const truncateText = (text: string, maxLength: number) => {
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
  };

  const handleSort = (field: 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date') => {
    setSortConfig(current => {
      if (current?.field === field) {
        return { field, direction: current.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { field, direction: field === 'tender_score' ? 'desc' : 'asc' };
    });
  };

  const handlePopupClose = () => {
    setPopupOpen(false);
    setAddToKanbanSuccess(null); // Reset the success state
    router.push("/dashboard/tenders/management");
  };

  const handleRowClick = async (result: TenderAnalysisResult) => {
    // Store current page before opening drawer
    if (currentPage > 1) {
      setLastKnownPage(currentPage);
    }
    const tenderBoards = getTenderBoards(result._id!);
    const boardStatus = tenderBoards.length
      ? tenderBoards.length === 1
        ? tenderBoards[0]
        : `${tenderBoards[0].length > 10
          ? tenderBoards[0].slice(0, 10) + '…'
          : tenderBoards[0]}+${tenderBoards.length - 1}`
      : null;

    setCurrentTenderBoardStatus(boardStatus); // passing status up
    console.log("[TendersList] Row clicked, setting selected result:", {
      tenderId: result._id,
      hasCriteria: !!result.criteria_analysis?.length,
      hasDescription: !!result.tender_description
    });

    // FIRST set the selected result with basic data and open drawer immediately
    setSelectedResult(result);
    console.log("[TendersList] Opening drawer for tender:", result._id);
    drawerRef.current?.setVisibility(true);

    // ← FIXED: Defer URL update to avoid DOM conflicts
    startTransition(() => {
      setTimeout(() => {
        const params = new URLSearchParams(window.location.search);
        params.set("page", currentPage.toString());
        params.set("tenderId", result._id!);
        router.replace(`?${params.toString()}`, { scroll: false });
      }, 0);
    });

    // THEN fetch the full data in the background
    try {
      console.log("[TendersList] Fetching full data in background for:", result._id);

      const fullResult = await fetchTenderResultById(result._id!);

      console.log("[TendersList] Background fetch completed:", {
        success: !!fullResult,
        hasFullData: !!fullResult?.criteria_analysis && Array.isArray(fullResult.criteria_analysis) && fullResult.criteria_analysis.length > 0
      });

      if (fullResult) {
        // Update with the full data in the allResults list
        setAllResults(prev =>
          prev.map(item =>
            item._id === result._id
              ? { ...item, ...fullResult }
              : item
          )
        );

        // Update the selected result with complete data
        setSelectedResult(fullResult);
      }
    } catch (err) {
      console.error("[TendersList] Error fetching data in background:", err);
    }

    // Mark as opened if needed
    const hasUpdate = isUpdatedAfterOpened(result);
    if (!result.opened_at || hasUpdate) {
      try {
        console.log("[TendersList] Marking tender as opened:", result._id);
        await markAsOpened(result._id!);

        setAllResults(prev =>
          prev.map(item =>
            item._id === result._id
              ? { ...item, opened_at: new Date().toISOString() }
              : item
          )
        );

        result.opened_at = new Date().toISOString();
        console.log("[TendersList] Tender marked as opened successfully:", result._id);
      } catch (err) {
        console.error('[TendersList] Failed to mark as opened:', err);
      }
    }
  };

  const handleUnopened = async (result: TenderAnalysisResult) => {
    if (result.opened_at && result.opened_at !== "") {
      try {
        await markAsUnopened(result._id!);

        setAllResults(prev =>
          prev.map(item =>
            item._id === result._id
              ? { ...item, opened_at: "" }
              : item
          )
        );

        result.opened_at = "";
      } catch (err) {
        console.error('Failed to mark as unopened:', err);
      }
    }
    closeDrawer();
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



  const isUpdatedAfterOpened = (result: TenderAnalysisResult) => {
    if (!result.updated_at || !result.opened_at) return false;
    const updatedTime = new Date(result.updated_at).getTime();
    const openedTime = new Date(result.opened_at).getTime();
    return updatedTime > openedTime;
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.includes('NaN')) return '-';

    let date: Date;
    if (dateStr.includes('-')) {
      const isoStr = dateStr.includes(' ') ? dateStr.replace(' ', 'T') : dateStr;
      date = new Date(isoStr);
    } else if (dateStr.includes('.')) {
      const [day, month, year] = dateStr.split('.').map(Number);
      date = new Date(year, month - 1, day);
    } else if (dateStr.includes('/')) {
      // Remove timezone info in parentheses if present
      const cleanDateStr = dateStr.replace(/\([^)]*\)/g, '').trim();

      // Try direct parsing first
      date = new Date(cleanDateStr);

      // If that fails, try manual parsing
      if (isNaN(date.getTime())) {
        const parts = cleanDateStr.split('/');
        if (parts.length === 3) {
          // Try to determine if it's DD/MM/YYYY or MM/DD/YYYY
          let day, month, year;

          if (parseInt(parts[0]) > 12) {
            // Likely DD/MM/YYYY
            day = parseInt(parts[0]);
            month = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part
          } else {
            // Likely MM/DD/YYYY
            month = parseInt(parts[0]);
            day = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part
          }

          date = new Date(year, month - 1, day);
        } else {
          return '-';
        }
      }
    } else {
      return '-';
    }

    if (isNaN(date.getTime())) return '-';
    const d = String(date.getDate()).padStart(2, '0');
    const m = String(date.getMonth() + 1).padStart(2, '0');
    return `${d}.${m}`;
  };

  const formatDateTime = (dateTimeStr: string) => {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('pl-PL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const calculateProgressPercentage = (createdAt: string, deadlineStr: string) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const created = new Date(createdAt);
    created.setHours(0, 0, 0, 0);

    let deadline;
    if (deadlineStr.includes('-')) {
      const isoStr = deadlineStr.includes(' ') ? deadlineStr.replace(' ', 'T') : deadlineStr;
      deadline = new Date(isoStr);
    } else if (deadlineStr.includes('.')) {
      const parts = deadlineStr.split('.');
      deadline = new Date(
        parseInt(parts[2]),
        parseInt(parts[1]) - 1,
        parseInt(parts[0])
      );
    } else if (deadlineStr.includes('/')) {
      // Remove timezone info in parentheses if present
      const cleanDeadlineStr = deadlineStr.replace(/\([^)]*\)/g, '').trim();

      // Try direct parsing first
      deadline = new Date(cleanDeadlineStr);

      // If that fails, try manual parsing
      if (isNaN(deadline.getTime())) {
        const parts = cleanDeadlineStr.split('/');
        if (parts.length === 3) {
          // Try to determine if it's DD/MM/YYYY or MM/DD/YYYY
          let day, month, year;

          if (parseInt(parts[0]) > 12) {
            // Likely DD/MM/YYYY
            day = parseInt(parts[0]);
            month = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part
          } else {
            // Likely MM/DD/YYYY
            month = parseInt(parts[0]);
            day = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]); // Remove time part
          }

          deadline = new Date(year, month - 1, day);
        } else {
          return 100; // Default to 100% if format can't be parsed
        }
      }
    } else {
      return 100; // Default to 100% if format isn't recognized
    }

    if (isNaN(deadline.getTime())) {
      return 100; // Default to 100% if date is invalid
    }

    deadline.setHours(0, 0, 0, 0);

    const totalDuration = deadline.getTime() - created.getTime();
    const elapsedDuration = today.getTime() - created.getTime();

    if (totalDuration <= 0) return 100;
    if (elapsedDuration <= 0) return 0;

    const progress = (elapsedDuration / totalDuration) * 100;
    return Math.min(100, Math.max(0, progress));
  };

  // Replace the old getStatusBadge function with getBoardBadge
  const getBoardBadge = (result: TenderAnalysisResult) => {
    if (boardsLoading) {
      return <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">Wczytywanie...</Badge>;
    }

    const boardNames = getTenderBoards(result._id!);
    if (boardNames.length > 0) {
      const displayText = boardNames.length === 1
        ? truncateText(boardNames[0], 15)
        : `${truncateText(boardNames[0], 10)}+${boardNames.length - 1}`;

      return (
        <Badge
          variant="outline"
          className="border-transparent bg-secondary-hover text-primary shadow"
          title={boardNames.length > 1 ? `W tablicach: ${boardNames.join(', ')}` : boardNames[0]}
        >
          {displayText}
        </Badge>
      );
    }

    // If not in any board, show status as fallback
    const status = result.status || 'inactive';
    switch (status) {
      case 'inactive':
        return <Badge variant="outline" className="border-zinc-200 text-zinc-400 font-normal">{t('tenders.status.inactive')}</Badge>;
      case 'active':
        return <Badge variant="default" className="bg-green-600/80 hover:bg-green-600/80 font-normal">{t('tenders.status.active')}</Badge>;
      case 'archived':
        return <Badge variant="secondary" className="bg-secondary text-primary/70 hover:bg-secondary font-normal">{t('tenders.status.archived')}</Badge>;
      default:
        return <Badge variant="outline">Nieznany</Badge>;
    }
  };

  const handleStatusChange = async (resultId: string, newStatus: 'inactive' | 'active' | 'archived') => {
    try {
      await updateTenderStatus(resultId, newStatus);
      // Update local state without affecting pagination
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

  // Add a helper function to close the drawer while preserving pagination
  const closeDrawer = () => {
    // Keep track of the current page before closing
    if (currentPage > 1) {
      setLastKnownPage(currentPage);
    }
    setSelectedResult(null);
    drawerRef.current?.setVisibility(false);

    // ← FIXED: Defer URL update to avoid DOM conflicts
    startTransition(() => {
      setTimeout(() => {
        const params = new URLSearchParams(window.location.search);
        params.delete("tenderId");
        router.replace(`?${params.toString()}`, { scroll: false });
      }, 0);
    });
  };

  const availableSources = useMemo(() => {
    const sources = new Set<string>();
    allResults.forEach(result => {
      if (result.source) {
        sources.add(result.source);
      }
    });
    return Array.from(sources);
  }, [allResults]);

  // Set the page only after data is loaded and validated
  useEffect(() => {
    // once loading is done and we haven't yet applied the initial page...
    if (!isLoading && !initialPageAppliedRef.current) {
      // figure out how many pages we actually have
      const total = filteredResults.length;
      const pages = Math.max(1, Math.ceil(total / LOCAL_ITEMS_PER_PAGE));

      // clamp the requested page into [1..pages]
      const toUse = Math.min(initialPageRef.current, pages);

      // **directly** setCurrentPage—this does NOT rewrite the URL
      setCurrentPage(toUse);
      initialPageAppliedRef.current = true;
    }
  }, [isLoading, filteredResults.length]);
  useEffect(() => {
    // only act after initial load of allResults
    if (!isLoading && requestedTenderId && !selectedResult) {
      const match = allResults.find(r => r._id === requestedTenderId);
      if (match) {
        handleRowClick(match);
      } else {
        // fallback: fetch it fresh if it wasn't in the initial page
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
  }, [isLoading, requestedTenderId, allResults]);



  // Track previous values to detect what changed
  const prevSearchQuery = useRef(searchQuery);
  const prevFilters = useRef(filters);
  const prevSelectedDate = useRef(selectedDate);
  const prevDateFilterType = useRef(dateFilterType);

  const pageBeforeSearch = useRef(currentPage);

  useEffect(() => {
    // Only act after initial load is complete
    if (!initialPageAppliedRef.current || isLoading) {
      // Update refs for next comparison
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
    updateCurrentPage
  ]);


  // Listen for URL changes (browser back/forward) and update page accordingly
  useEffect(() => {
    const handleRouteChange = () => {
      const newPageFromUrl = getPageFromUrl();
      // Only update if different to avoid loops
      if (newPageFromUrl !== currentPage) {
        setCurrentPage(newPageFromUrl);
      }
    };

    // Listen for route change events
    window.addEventListener('popstate', handleRouteChange);

    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  }, [getPageFromUrl, currentPage]);

  // Reset the page when filters change, but not on initial load
  useEffect(() => {
    // Only reset page on filter changes if initial load is already complete
    if (initialLoadComplete) {
      // Store current page before resetting
      if (currentPage > 1) {
        setLastKnownPage(currentPage);
      }
      updateCurrentPage(1);
    }
  }, [filters, searchQuery, selectedDate, dateFilterType, initialLoadComplete]);
  function useNavigateOnLoad(
    isLoading: boolean,
    targetPage: number,
    navigate: (page: number) => void
  ) {
    // Ensure we only navigate once
    const hasNavigatedRef = useRef(false);

    useEffect(() => {
      if (!isLoading && !hasNavigatedRef.current) {
        navigate(targetPage);
        hasNavigatedRef.current = true;
      }
    }, [isLoading, targetPage, navigate]);
  }
  useNavigateOnLoad(isLoading, requestedPage, updateCurrentPage);
  // In your rendering pagination code, make sure to use updateCurrentPage
  const renderPaginationItems = () => {
    const items = [];

    if (totalPages <= 5) {
      for (let i = 1; i <= totalPages; i++) {
        items.push(
          <PaginationItem key={i}>
            <PaginationLink
              onClick={() => updateCurrentPage(i, true)}
              isActive={currentPage === i}
            >
              {i}
            </PaginationLink>
          </PaginationItem>
        );
      }
      return items;
    }

    items.push(
      <PaginationItem key={1}>
        <PaginationLink
          onClick={() => updateCurrentPage(1, true)}
          isActive={currentPage === 1}
        >
          1
        </PaginationLink>
      </PaginationItem>
    );

    if (currentPage > 3) {
      items.push(
        <PaginationItem key="ellipsis-left">
          <div className="flex items-center justify-center h-9 w-9">
            <TenderPageInput
              totalPages={totalPages}
              onPageJump={(page) => updateCurrentPage(page, true)}
            />
          </div>
        </PaginationItem>
      );
    }

    const startPage = Math.max(2, currentPage - 1);
    const endPage = Math.min(totalPages - 1, currentPage + 1);

    for (let i = startPage; i <= endPage; i++) {
      items.push(
        <PaginationItem key={i}>
          <PaginationLink
            onClick={() => updateCurrentPage(i, true)}
            isActive={currentPage === i}
          >
            {i}
          </PaginationLink>
        </PaginationItem>
      );
    }

    if (currentPage < totalPages - 2) {
      items.push(
        <PaginationItem key="ellipsis-right">
          <div className="flex items-center justify-center h-9 w-9">
            <TenderPageInput
              totalPages={totalPages}
              onPageJump={(page) => updateCurrentPage(page, true)}
            />
          </div>
        </PaginationItem>
      );
    }

    if (totalPages > 1) {
      items.push(
        <PaginationItem key={totalPages}>
          <PaginationLink
            onClick={() => updateCurrentPage(totalPages, true)}
            isActive={currentPage === totalPages}
          >
            {totalPages}
          </PaginationLink>
        </PaginationItem>
      );
    }

    return items;
  };

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
  ]);

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
          />
        </CardHeader>
        <CardContent className="overflow-x-auto" ref={tableContainerRef}>
          <div className="rounded-md border shadow-sm overflow-hidden">
            <Table className="w-full table-fixed">
              <TableHeader className="bg-white/20 shadow">
                <TableRow>
                  <TableHead className={cn("text-xs", tableWidth < 700 ? "w-[15%]" : "w-[5%]")}>{t('tenders.list.source')}</TableHead>
                  <TableHead className={cn("text-xs", tableWidth < 700 ? "w-[45%]" : "w-[25%]")}>{t('tenders.list.order')}</TableHead>
                  {tableWidth >= 700 && <TableHead className="text-xs w-[15%]">{t('tenders.details.client')}</TableHead>}
                  {tableWidth >= 700 && (
                    <TableHead className="text-xs w-[20%]">
                      <div className="flex justify-between items-center pr-4">
                        <p>{t('tenders.details.publicationDate')}</p>
                        <p>{t('tenders.details.submissionDeadline')}</p>
                      </div>
                    </TableHead>
                  )}
                  {tableWidth < 700 && (
                    <TableHead className="text-xs w-[20%]">Termin zgłoszenia</TableHead>
                  )}
                  {tableWidth >= 700 && <TableHead className="text-xs w-[10%]">{t('tenders.list.boardStatus')}</TableHead>}
                  <TableHead className={cn("text-xs", tableWidth < 700 ? "w-[15%]" : "w-[10%]")}>{t('tenders.list.relevance')}</TableHead>
                  <TableHead className={cn("text-xs", tableWidth < 700 ? "w-[5%]" : "w-[5%]")}></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={tableWidth >= 700 ? 7 : 5} className="h-[500px]">
                      <div className="flex flex-col w-full h-full items-center justify-center space-y-2">
                        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
                        <p className="text-sm text-muted-foreground">
                          {t('tenders.list.loading', {
                            fetched: totalFetched,
                            total: totalTendersCount !== null ? ` / ${totalTendersCount}` : ''
                          })}
                        </p>
                        {totalTendersCount !== null && totalTendersCount > 0 && (
                          <div className="w-1/4 h-1 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-1 bg-primary transition-all duration-300"
                              style={{ width: `${(totalFetched / totalTendersCount) * 100}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : currentResults.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={tableWidth >= 700 ? 7 : 5} className="text-center text-muted-foreground py-20">
                      {allResults.length > 0 ?
                        t('tenders.list.noTenders') :
                        selectedAnalysis ?
                          t('tenders.list.noResults') :
                          t('tenders.list.selectAnalysis')
                      }
                    </TableCell>
                  </TableRow>
                ) : (
                  currentResults.map((result: TenderAnalysisResult) => {
                    const hasUpdate = isUpdatedAfterOpened(result);
                    const daysRemaining = calculateDaysRemaining(result.tender_metadata.submission_deadline);

                    const voivodeship = result.location?.voivodeship &&
                      result.location.voivodeship !== "UNKNOWN" ?
                      result.location.voivodeship.charAt(0).toUpperCase() +
                      result.location.voivodeship.slice(1).toLowerCase() :
                      "-";

                    return (
                      <TableRow
                        key={result._id}
                        className={cn(
                          "cursor-pointer hover:bg-secondary/70 transition-colors",
                          selectedResult?._id === result._id
                            ? "bg-secondary-hover"
                            : ((!result.opened_at || result.opened_at === "")
                              ? "bg-green-600/5 font-semibold"
                              : hasUpdate
                                ? "bg-orange-700/5"
                                : "bg-background"),
                          !result.opened_at && selectedResult?._id !== result._id
                            ? "!border-l-2 !border-l-green-600/70 shadow-sm"
                            : hasUpdate && result.opened_at && selectedResult?._id !== result._id
                              ? "!border-l-2 !border-l-orange-600"
                              : ""
                        )}
                        onClick={() => handleRowClick(result)}
                      >
                        <TableCell className="relative font-medium">
                          {!result.opened_at && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div className="absolute top-1 left-1">
                                    <Badge variant="outline" className="bg-green-400/20 text-green-700 border-green-700/20 px-0.5 flex items-center justify-center h-4">
                                      <Sparkles className="h-2.5 w-2.5" />
                                    </Badge>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                  <p className="text-xs">{t('tenders.tooltips.updated', { time: formatDateTime(result.updated_at!) })}</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                          <TenderSourceIcon source={result.source} url={result.tender_url} />
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <div className="flex items-center">
                              {truncateText(result.tender_metadata.name, tableWidth < 700 ? 60 : 85)}
                            </div>
                            <div className="text-xs text-foreground/50 font-medium mt-0.5 flex gap-2 items-center">
                              {voivodeship !== "-" && <span>{truncateText(voivodeship, 25)}</span>}
                              <span>{"#" + result.order_number}</span>
                            </div>
                          </div>
                        </TableCell>
                        {tableWidth >= 700 && (
                          <TableCell>{truncateText(result.tender_metadata.organization, 25)}</TableCell>
                        )}
                        {tableWidth >= 700 && (
                          <TableCell>
                            <div className="flex flex-col w-full">
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-500 whitespace-nowrap min-w-[45px]">
                                  {formatDate(result.tender_metadata.initiation_date || result.tender_metadata.submission_deadline).split('.').slice(0, 2).join('.')}
                                </span>

                                <div className="w-24 sm:w-28 bg-secondary-hover rounded-full h-2">
                                  <div
                                    className={`h-2 rounded-full ${!result.tender_metadata.submission_deadline ||
                                      result.tender_metadata.submission_deadline.includes('NaN') ? "bg-gray-400" :
                                      daysRemaining < 0 ? "bg-gray-400" :
                                        daysRemaining <= 3 ? "bg-red-600 opacity-70" :
                                          daysRemaining <= 10 ? "bg-amber-600 opacity-70" :
                                            daysRemaining <= 21 ? "bg-yellow-600 opacity-70" :
                                              "bg-green-600 opacity-70"
                                      }`}
                                    style={{
                                      width: `${!result.tender_metadata.submission_deadline ||
                                        result.tender_metadata.submission_deadline.includes('NaN') ? "100" :
                                        calculateProgressPercentage(result.created_at, result.tender_metadata.submission_deadline)
                                        }%`
                                    }}
                                  ></div>
                                </div>

                                <div className="flex items-center">
                                  <span className="text-xs text-gray-500 whitespace-nowrap min-w-[45px]">
                                    {!result.tender_metadata.submission_deadline ||
                                      result.tender_metadata.submission_deadline.includes('NaN') ?
                                      "-" : formatDate(result.tender_metadata.submission_deadline)}
                                  </span>
                                  <Badge className="ml-1 text-xs px-1 py-0" variant="outline">
                                    <span className={`text-xs ${!result.tender_metadata.submission_deadline ||
                                      result.tender_metadata.submission_deadline.includes('NaN') ? "text-gray-600 opacity-70" :
                                      daysRemaining < 0 ? "text-gray-600 opacity-70" :
                                        daysRemaining <= 3 ? "text-red-600 opacity-70" :
                                          daysRemaining <= 10 ? "text-amber-600 opacity-70" :
                                            daysRemaining <= 21 ? "text-yellow-600 opacity-70" :
                                              "text-green-600 opacity-70"
                                      }`}>
                                      {!result.tender_metadata.submission_deadline ||
                                        result.tender_metadata.submission_deadline.includes('NaN') ||
                                        isNaN(daysRemaining) ?
                                        '-' :
                                        daysRemaining < 0 ?
                                          'Zak.' :
                                          daysRemaining === 0 ?
                                            'Dziś' :
                                            daysRemaining === 1 ?
                                              '1d' :
                                              `${daysRemaining}d`}
                                    </span>
                                  </Badge>
                                </div>
                              </div>
                            </div>
                          </TableCell>
                        )}
                        {tableWidth < 700 && (
                          <TableCell>
                            <div className="flex items-center justify-start">
                              <Badge className="text-xs px-2 py-1" variant="outline">
                                <span className={`text-xs font-medium ${!result.tender_metadata.submission_deadline ||
                                  result.tender_metadata.submission_deadline.includes('NaN') ? "text-gray-600 opacity-70" :
                                  daysRemaining < 0 ? "text-gray-600 opacity-70" :
                                    daysRemaining <= 3 ? "text-red-600 opacity-70" :
                                      daysRemaining <= 10 ? "text-amber-600 opacity-70" :
                                        daysRemaining <= 21 ? "text-yellow-600 opacity-70" :
                                          "text-green-600 opacity-70"
                                  }`}>
                                  {!result.tender_metadata.submission_deadline ||
                                    result.tender_metadata.submission_deadline.includes('NaN') ||
                                    isNaN(daysRemaining) ?
                                    '-' :
                                    daysRemaining < 0 ?
                                      t('tenders.details.finished') :
                                      daysRemaining === 0 ?
                                        t('tenders.details.today') :
                                        daysRemaining === 1 ?
                                          `1 ${t('tenders.details.day')}` :
                                          `${daysRemaining} ${t('tenders.details.days')}`}
                                </span>
                              </Badge>
                            </div>
                          </TableCell>
                        )}
                        {tableWidth >= 700 && <TableCell>{getBoardBadge(result)}</TableCell>}
                        <TableCell><ScoreIndicator score={result.tender_score} /></TableCell>
                        <TableCell className="p-0">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" onClick={(e) => e.stopPropagation()}>
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {result.status !== 'active' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleStatusChange(result._id!, 'active'); }}>
                                  <CheckCircle className="mr-2 h-4 w-4 text-green-500" />
                                  {t('tenders.status.activate')}
                                </DropdownMenuItem>
                              )}
                              {result.status === 'active' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleStatusChange(result._id!, 'inactive'); }}>
                                  <AlertCircle className="mr-2 h-4 w-4 text-gray-500" />
                                  {commonT('delete')}
                                </DropdownMenuItem>
                              )}
                              {result.status !== 'archived' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleStatusChange(result._id!, 'archived'); }}>
                                  <Archive className="mr-2 h-4 w-4 text-gray-700" />
                                  {t('tenders.status.archive')}
                                </DropdownMenuItem>
                              )}

                              {(result.opened_at && result.opened_at !== '') && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleUnopened(result); }}>
                                  <EyeOff className="mr-2 h-4 w-4 text-gray-700" />
                                  {t('tenders.status.markUnread')}
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={(e) => handleDelete(e, result._id)} className="text-destructive focus:text-destructive">
                                <Trash className="mr-2 h-4 w-4" />
                                {t('tenders.status.delete')}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedResult(result);
                                  setShowKanbanDialog(true);
                                }}
                                disabled={result.status !== 'active'}
                              >
                                <ListCheck className="mr-2 h-4 w-4" />
                                {t('tenders.kanban.addToKanban')}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
          {totalPages > 1 && (
            <div className="mt-4 flex justify-center">
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious onClick={() => updateCurrentPage(Math.max(currentPage - 1, 1), true)} />
                  </PaginationItem>
                  {renderPaginationItems()}
                  <PaginationItem>
                    <PaginationNext onClick={() => updateCurrentPage(Math.min(currentPage + 1, totalPages), true)} />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </CardContent>
      </Card>
      {
        selectedResult && (
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
                // Refresh kanban boards to update the display
                fetchKanbanBoards();
              }, 100);
            }}
            onAddError={(error) => {
              // Close the Kanban dialog on error
              setShowKanbanDialog(false);
              setSelectedResult(null);
              // Small delay before showing error popup
              setTimeout(() => {
                setPopupMessage(t('tenders.kanban.addError'));
                setAddToKanbanSuccess(false);
                setPopupOpen(true);
              }, 100);
            }}
          />
        )
      }
      {
        popupOpen && (
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
                    setAddToKanbanSuccess(null); // Reset the success state
                  }}
                  variant={addToKanbanSuccess ? "outline" : "default"}
                  className="px-6"
                >
                  {addToKanbanSuccess ? t('tenders.kanban.stayHere') : t('tenders.kanban.exit')}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )
      }
    </div >
  );
};

const ScoreIndicator: React.FC<{ score: number }> = ({ score }) => {
  const percentage = score * 100;
  let color = "bg-red-500/80";
  if (percentage >= 60) color = "bg-green-600/80";
  else if (percentage >= 45) color = "bg-yellow-500/80";
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span>{percentage.toFixed(1)}%</span>
    </div>
  );
};

export default TendersList;
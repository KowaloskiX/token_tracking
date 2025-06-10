import React, { useState, useEffect } from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { format } from "date-fns";
import { AlertCircle, Archive, ArrowUpDown, Calendar as CalendarIcon, CheckCircle, ChevronDown, Filter, ListCheck, Loader2, MoreVertical, Percent, RefreshCw, Search, Sparkles, Trash, Clock, Plus, X } from 'lucide-react';
import { cn } from "@/lib/utils";
import TenderSourceIcon from "./TenderSourceIcon"; // Assuming TenderSourceIcon is needed/reused
import { TenderAnalysisResult } from "@/types/tenders"; // Import the type


type VoivodeshipKey = keyof Filters['voivodeship'];
type SourceKey = keyof Filters['source'];

export interface Filters {
  onlyQualified: boolean;
  status: { inactive: boolean; active: boolean; archived: boolean; inBoard: boolean };
  voivodeship: {
    "Dolnośląskie": boolean;
    "Kujawsko-pomorskie": boolean;
    "Lubelskie": boolean;
    "Lubuskie": boolean;
    "Łódzkie": boolean;
    "Małopolskie": boolean;
    "Mazowieckie": boolean;
    "Opolskie": boolean;
    "Podkarpackie": boolean;
    "Podlaskie": boolean;
    "Pomorskie": boolean;
    "Śląskie": boolean;
    "Świętokrzyskie": boolean;
    "Warmińsko-mazurskie": boolean;
    "Wielkopolskie": boolean;
    "Zachodniopomorskie": boolean;
  };
  source: Record<string, boolean>; // Added source filter
}

interface TenderFiltersProps {
  filters: Filters;
  setFilters: React.Dispatch<React.SetStateAction<Filters>>;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedDate: Date | undefined;
  setSelectedDate: (date: Date | undefined) => void;
  dateFilterType: 'initiation_date' | 'submission_deadline';
  setDateFilterType: (type: 'initiation_date' | 'submission_deadline') => void;
  sortConfig: {
    field: 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date';
    direction: 'asc' | 'desc';
  } | null;
  handleSort: (field: 'submission_deadline' | 'tender_score' | 'updated_at' | 'created_at' | 'initiation_date') => void;
  availableSources: string[]; // Pass available sources from parent
}

export const TenderFilters: React.FC<TenderFiltersProps> = ({
  filters,
  setFilters,
  searchQuery,
  setSearchQuery,
  selectedDate,
  setSelectedDate,
  dateFilterType,
  setDateFilterType,
  sortConfig,
  handleSort,
  availableSources,
}) => {
  const [showVoivodeships, setShowVoivodeships] = useState(false);
  const [showSources, setShowSources] = useState(false); // State for source filter expansion
  const [showStatus, setShowStatus] = useState(true); // State for status filter expansion, expanded by default

  // Initialize / sync source filters when availableSources changes, but avoid
  // triggering a state update if nothing actually changed to prevent unwanted
  // side-effects such as pagination reset.
  useEffect(() => {
    setFilters(prev => {
      // Build the desired source filter object based on availableSources
      const desired: Record<string, boolean> = {};
      availableSources.forEach(src => {
        desired[src] = prev.source?.[src] ?? true;
      });

      // Remove any sources that are no longer available
      Object.keys(prev.source || {}).forEach(src => {
        if (!availableSources.includes(src)) {
          // keep consistency by omitting disappeared sources
          // (they will be absent from `desired`)
        }
      });

      // Fast comparison – if keys and their boolean values are identical, do not update
      const prevKeys = Object.keys(prev.source || {});
      const desiredKeys = Object.keys(desired);
      if (
        prevKeys.length === desiredKeys.length &&
        prevKeys.every(key => desired[key] === prev.source[key])
      ) {
        return prev; // No meaningful change
      }

      return { ...prev, source: desired };
    });
  }, [availableSources, setFilters]);

  // Updated to handle the new 'inBoard' status
  const toggleStatusFilter = (status: 'inactive' | 'active' | 'archived' | 'inBoard') => {
    setFilters(prev => ({
      ...prev,
      status: { ...prev.status, [status]: !prev.status[status] },
    }));
  };

  const toggleAllStatus = (setToValue: boolean) => {
    const newStatus = { ...filters.status };
    Object.keys(newStatus).forEach(key => {
      newStatus[key as keyof typeof filters.status] = setToValue;
    });
    setFilters(prev => ({
      ...prev,
      status: newStatus
    }));
  };

  const areAllStatusSelected = () => {
    return Object.values(filters.status).every(Boolean);
  };

  const toggleVoivodeshipFilter = (voivodeship: string) => {
    const key = voivodeship as VoivodeshipKey;
    setFilters(prev => ({
      ...prev,
      voivodeship: {
        ...prev.voivodeship,
        [key]: !prev.voivodeship[key]
      },
    }));
  };

  const toggleAllVoivodeships = (setToValue: boolean) => {
    const newVoivodeships = { ...filters.voivodeship };
    Object.keys(newVoivodeships).forEach(key => {
      newVoivodeships[key as keyof typeof filters.voivodeship] = setToValue;
    });
    setFilters(prev => ({
      ...prev,
      voivodeship: newVoivodeships
    }));
  };

  const areAllVoivodeshipsSelected = () => {
    return Object.values(filters.voivodeship).every(Boolean);
  };

  // --- Source Filter Logic ---
  const toggleSourceFilter = (source: string) => {
    setFilters(prev => ({
      ...prev,
      source: {
        ...prev.source,
        [source]: !prev.source[source]
      },
    }));
  };

  const toggleAllSources = (setToValue: boolean) => {
    const newSources = { ...filters.source };
    Object.keys(newSources).forEach(key => {
      newSources[key] = setToValue;
    });
    setFilters(prev => ({
      ...prev,
      source: newSources
    }));
  };

  const areAllSourcesSelected = () => {
    // Ensure filters.source exists and has keys before checking values
    return filters.source && Object.keys(filters.source).length > 0 && Object.values(filters.source).every(Boolean);
  };
  // ---------------------------

  const hasActiveFilters = filters.onlyQualified ||
                           !Object.values(filters.status).every(Boolean) ||
                           !Object.values(filters.voivodeship).every(Boolean) ||
                           (filters.source && Object.keys(filters.source).length > 0 && !Object.values(filters.source).every(Boolean)); // Check source filter


  return (
    <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 mt-4">
      <div className="relative w-full sm:w-2/3 lg:w-3/4">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Wyszukaj po nazwie, numerze, organizacji, lokalizacji..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9 pr-9"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 transform -translate-y-1/2"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 w-full sm:w-auto">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "bg-white/20 shadow min-w-40 justify-start text-left",
                selectedDate && "text-primary"
              )}
              size="sm"
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {selectedDate ? format(selectedDate, "dd.MM.yyyy") : "Wybierz termin"}
              {selectedDate && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedDate(undefined);
                  }}
                  className="ml-auto"
                >
                  <X className="h-4 w-4 text-muted-foreground" />
                </button>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <div className="p-2 border-b">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Filtruj po:</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-8 gap-1 text-sm">
                      {dateFilterType === 'initiation_date' ? 'Dacie publikacji' : 'Terminie zgłoszenia'}
                      <ChevronDown className="h-3 w-3 opacity-50" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => setDateFilterType('initiation_date')}
                    >
                      Data ogłoszenia
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setDateFilterType('submission_deadline')}
                    >
                      Termin zgłoszenia
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
            <Calendar
              mode="single"
              selected={selectedDate}
              onSelect={setSelectedDate}
              initialFocus
            />
          </PopoverContent>
        </Popover>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button className="bg-white/20 shadow" variant="outline" size="sm">
              <Filter className="mr-2 h-4 w-4" />
              Filtry {hasActiveFilters &&
                    <span className="ml-1 h-2 w-2 rounded-full bg-primary-hover" />}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72"> {/* Increased width from w-64 to w-72 */}
            {/* Status section */}
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setShowStatus(!showStatus);
              }}
              className="flex justify-between items-center cursor-pointer px-2"
            >
              <span className="text-xs text-muted-foreground">Status</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showStatus ? 'rotate-180' : ''}`} />
            </DropdownMenuItem>

            {showStatus && (
              <>
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    toggleAllStatus(!areAllStatusSelected());
                  }}
                  className="flex justify-between items-center cursor-pointer py-1 my-1 bg-secondary/40 px-2"
                >
                  <div className="truncate text-xs font-medium">
                    {areAllStatusSelected() ? 'Odznacz wszystkie' : 'Zaznacz wszystkie'}
                  </div>
                </DropdownMenuItem>
                <div className="max-h-[180px] overflow-y-auto border-t border-t-muted/20 pt-1">
                  <DropdownMenuCheckboxItem
                    checked={filters.status.active}
                    onSelect={(e) => { e.preventDefault(); toggleStatusFilter('active'); }}
                    className="px-2 flex items-center"
                  >
                    <span className="truncate pr-6 pl-6">Aktywne</span>
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={filters.status.inactive}
                    onSelect={(e) => { e.preventDefault(); toggleStatusFilter('inactive'); }}
                    className="px-2 flex items-center"
                  >
                    <span className="truncate pr-6 pl-6">Nieaktywne</span>
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={filters.status.archived}
                    onSelect={(e) => { e.preventDefault(); toggleStatusFilter('archived'); }}
                    className="px-2 flex items-center"
                  >
                    <span className="truncate pr-6 pl-6">Zarchiwizowane</span>
                  </DropdownMenuCheckboxItem>
                  {/* NEW: In Board Filter Option */}
                  <DropdownMenuCheckboxItem
                    checked={filters.status.inBoard}
                    onSelect={(e) => { e.preventDefault(); toggleStatusFilter('inBoard'); }}
                    className="px-2 flex items-center"
                  >
                    <span className="truncate pr-6 pl-6">W tablicy</span>
                  </DropdownMenuCheckboxItem>
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            {/* --------------------- */}

             {/* Source Section - New */}
             <DropdownMenuItem
               onSelect={(e) => {
                 e.preventDefault();
                 setShowSources(!showSources);
               }}
               className="flex justify-between items-center cursor-pointer px-2"
             >
               <span className="text-xs text-muted-foreground">Źródła</span>
               <ChevronDown className={`h-4 w-4 transition-transform ${showSources ? 'rotate-180' : ''}`} />
             </DropdownMenuItem>

             {showSources && (
               <>
                 <DropdownMenuItem
                   onSelect={(e) => {
                     e.preventDefault();
                     toggleAllSources(!areAllSourcesSelected());
                   }}
                   className="flex justify-between items-center cursor-pointer py-1 my-1 bg-secondary/40 px-2"
                 >
                   <div className="truncate text-xs font-medium">
                     {areAllSourcesSelected() ? 'Odznacz wszystkie' : 'Zaznacz wszystkie'}
                   </div>
                 </DropdownMenuItem>

                 <div className="max-h-[180px] overflow-y-auto border-t border-t-muted/20 pt-1">
                   {Object.entries(filters.source ?? {}).sort(([sourceA], [sourceB]) => sourceA.localeCompare(sourceB)) // Sort alphabetically, handle undefined source
                   .map(([source, isChecked]) => (
                     <DropdownMenuCheckboxItem
                       key={source}
                       checked={isChecked}
                       onSelect={(e) => {
                         e.preventDefault();
                         toggleSourceFilter(source);
                       }}
                       className="px-2 flex items-center"
                     >
                       <div className="flex items-center gap-2 truncate w-full pl-6 pr-6">
                          <TenderSourceIcon source={source} url={''} />
                          <span className="truncate">{source ? source.charAt(0).toUpperCase() + source.slice(1) : 'Nieznane'}</span>
                       </div>
                     </DropdownMenuCheckboxItem>
                   ))}
                 </div>
                 <DropdownMenuSeparator />
               </>
             )}
             {/* --------------------- */}


            {/* Voivodeship section */}
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setShowVoivodeships(!showVoivodeships);
              }}
              className="flex justify-between items-center cursor-pointer px-2"
            >
              <span className="text-xs text-muted-foreground">Województwa</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showVoivodeships ? 'rotate-180' : ''}`} />
            </DropdownMenuItem>

            {showVoivodeships && (
              <>
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    toggleAllVoivodeships(!areAllVoivodeshipsSelected());
                  }}
                  className="flex justify-between items-center cursor-pointer py-1 my-1 bg-secondary/40 px-2"
                >
                  <div className="truncate text-xs font-medium">
                    {areAllVoivodeshipsSelected() ? 'Odznacz wszystkie' : 'Zaznacz wszystkie'}
                  </div>
                </DropdownMenuItem>

                <div className="max-h-[180px] overflow-y-auto border-t border-t-muted/20 pt-1">
                  {Object.entries(filters.voivodeship).map(([voivodeship, isChecked]) => (
                    <DropdownMenuCheckboxItem
                      key={voivodeship}
                      checked={isChecked}
                      onSelect={(e) => {
                        e.preventDefault();
                        toggleVoivodeshipFilter(voivodeship);
                      }}
                      className="px-2 flex items-center"
                    >
                      <div className="truncate w-full pl-6 pr-6">
                        {voivodeship}
                      </div>
                    </DropdownMenuCheckboxItem>
                  ))}
                </div>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button className="bg-white/20 shadow" variant="outline" size="sm">
              <ArrowUpDown className="mr-2 h-4 w-4" />
              Sortuj
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleSort('submission_deadline')} className="flex items-center">
              <CalendarIcon className="mr-2 h-4 w-4" />
              Termin zgłoszenia {sortConfig?.field === 'submission_deadline' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSort('tender_score')} className="flex items-center">
              <Percent className="mr-2 h-4 w-4" />
              Relewantność {sortConfig?.field === 'tender_score' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSort('updated_at')} className="flex items-center">
              <RefreshCw className="mr-2 h-4 w-4" />
              Ostatnia aktualizacja {sortConfig?.field === 'updated_at' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSort('created_at')} className="flex items-center">
              <Clock className="mr-2 h-4 w-4" />
              Data utworzenia {sortConfig?.field === 'created_at' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
            </DropdownMenuItem>
             <DropdownMenuItem onClick={() => handleSort('initiation_date')} className="flex items-center">
               <Clock className="mr-2 h-4 w-4" /> {/* Changed icon for consistency */}
               Data publikacji {sortConfig?.field === 'initiation_date' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
             </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};
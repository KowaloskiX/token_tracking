"use client"
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Search, Play, ChevronDown, Info, Plus, X, Calendar as CalendarIcon, Filter, Loader2 } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

export interface FilterCondition {
  field: string;
  op: string;
  value: string | string[];
}

interface SearchFormProps {
  searchPhrase: string;
  setSearchPhrase: (value: string) => void;
  companyDescription: string;
  setCompanyDescription: (value: string) => void;
  sources: string[];
  setSources: (value: string[]) => void;
  topK: number;
  setTopK: (value: number) => void;
  saveResults: boolean;
  setSaveResults: (value: boolean) => void;
  scoreThreshold: number[];
  setScoreThreshold: (value: number[]) => void;
  embeddingModel: string;
  setEmbeddingModel: (value: string) => void;
  tenderNamesIndex: string;
  setTenderNamesIndex: (value: string) => void;
  elasticsearchIndex: string;
  setElasticsearchIndex: (value: string) => void;
  filterConditions: FilterCondition[];
  setFilterConditions: (conditions: FilterCondition[]) => void;
  searchLoading: boolean;
  onRunSearch: () => void;
  
  // Add these missing props:
  analysisId: string;
  setAnalysisId: (value: string) => void;
  searchId: string;
  setSearchId: (value: string) => void;
  tenderIdsToCompare: string[];
  setTenderIdsToCompare: (value: string[]) => void;
}

const availableSources = [
  { 
    id: 'ezamowienia', 
    label: 'eZamówienia', 
    description: 'Polish public procurement platform',
    category: 'polish'
  },
  { 
    id: 'smartpzp', 
    label: 'SmartPZP', 
    description: 'Public procurement platform',
    category: 'polish'
  },
  { 
    id: 'platformazakupowa', 
    label: 'Platforma Zakupowa', 
    description: 'Public purchasing platform',
    category: 'polish'
  },
  { 
    id: 'egospodarka', 
    label: 'eGospodarka', 
    description: 'Economic portal with tenders',
    category: 'polish'
  },
  { 
    id: 'eb2b', 
    label: 'eB2B', 
    description: 'B2B platform for orders',
    category: 'polish'
  },
  { 
    id: 'ezamawiajacy', 
    label: 'eZamawiający', 
    description: 'System for public contracting authorities',
    category: 'polish'
  },
  { 
    id: 'logintrade', 
    label: 'LoginTrade', 
    description: 'Trading platform',
    category: 'polish'
  },
  { 
    id: 'bazakonkurencyjnosci', 
    label: 'Baza Konkurencyjnosci', 
    description: 'Competitive tender database',
    category: 'polish'
  },
  { 
    id: 'epropublico_main', 
    label: 'eProPublico', 
    description: 'Main public tender platform',
    category: 'polish'
  },
  { 
    id: 'orlenconnect', 
    label: 'Orlen Connect', 
    description: 'Orlen procurement platform',
    category: 'corporate'
  },
  { 
    id: 'pge', 
    label: 'PGE', 
    description: 'PGE procurement platform',
    category: 'corporate'
  },
  { 
    id: 'vergabe', 
    label: 'Vergabe', 
    description: 'German tender platform',
    category: 'german'
  },
  { 
    id: 'dtvp_like', 
    label: 'DTVP Like', 
    description: 'DTVP-type platforms',
    category: 'german'
  },
  { 
    id: 'vergabeplatforms', 
    label: 'Vergabe Platforms', 
    description: 'German tender platforms',
    category: 'german'
  },
  { 
    id: 'ted', 
    label: 'TED (Poland)', 
    description: 'Tenders Electronic Daily - Poland',
    category: 'ted'
  },
  { 
    id: 'ted_germany', 
    label: 'TED (Germany)', 
    description: 'Tenders Electronic Daily - Germany',
    category: 'ted'
  },
  { 
    id: 'ted_france', 
    label: 'TED (France)', 
    description: 'Tenders Electronic Daily - France',
    category: 'ted'
  },
  { 
    id: 'ted_spain', 
    label: 'TED (Spain)', 
    description: 'Tenders Electronic Daily - Spain',
    category: 'ted'
  },
  { 
    id: 'ted_italy', 
    label: 'TED (Italy)', 
    description: 'Tenders Electronic Daily - Italy',
    category: 'ted'
  },
  { 
    id: 'ted_belgium', 
    label: 'TED (Belgium)', 
    description: 'Tenders Electronic Daily - Belgium',
    category: 'ted'
  },
  { 
    id: 'ted_netherlands', 
    label: 'TED (Netherlands)', 
    description: 'Tenders Electronic Daily - Netherlands',
    category: 'ted'
  },
  { 
    id: 'ted_sweden', 
    label: 'TED (Sweden)', 
    description: 'Tenders Electronic Daily - Sweden',
    category: 'ted'
  },
  { 
    id: 'ted_czechia', 
    label: 'TED (Czech Republic)', 
    description: 'Tenders Electronic Daily - Czech Republic',
    category: 'ted'
  },
  { 
    id: 'ted_austria', 
    label: 'TED (Austria)', 
    description: 'Tenders Electronic Daily - Austria',
    category: 'ted'
  },
  { 
    id: 'ted_portugal', 
    label: 'TED (Portugal)', 
    description: 'Tenders Electronic Daily - Portugal',
    category: 'ted'
  },
  { 
    id: 'ted_denmark', 
    label: 'TED (Denmark)', 
    description: 'Tenders Electronic Daily - Denmark',
    category: 'ted'
  },
  { 
    id: 'ted_finland', 
    label: 'TED (Finland)', 
    description: 'Tenders Electronic Daily - Finland',
    category: 'ted'
  },
  { 
    id: 'ted_norway', 
    label: 'TED (Norway)', 
    description: 'Tenders Electronic Daily - Norway',
    category: 'ted'
  },
  { 
    id: 'ted_ireland', 
    label: 'TED (Ireland)', 
    description: 'Tenders Electronic Daily - Ireland',
    category: 'ted'
  },
  { 
    id: 'ted_greece', 
    label: 'TED (Greece)', 
    description: 'Tenders Electronic Daily - Greece',
    category: 'ted'
  },
  { 
    id: 'ted_hungary', 
    label: 'TED (Hungary)', 
    description: 'Tenders Electronic Daily - Hungary',
    category: 'ted'
  },
  { 
    id: 'ted_slovakia', 
    label: 'TED (Slovakia)', 
    description: 'Tenders Electronic Daily - Slovakia',
    category: 'ted'
  },
  { 
    id: 'ted_slovenia', 
    label: 'TED (Slovenia)', 
    description: 'Tenders Electronic Daily - Slovenia',
    category: 'ted'
  },
  { 
    id: 'ted_croatia', 
    label: 'TED (Croatia)', 
    description: 'Tenders Electronic Daily - Croatia',
    category: 'ted'
  },
  { 
    id: 'ted_romania', 
    label: 'TED (Romania)', 
    description: 'Tenders Electronic Daily - Romania',
    category: 'ted'
  },
  { 
    id: 'ted_bulgaria', 
    label: 'TED (Bulgaria)', 
    description: 'Tenders Electronic Daily - Bulgaria',
    category: 'ted'
  },
  { 
    id: 'ted_estonia', 
    label: 'TED (Estonia)', 
    description: 'Tenders Electronic Daily - Estonia',
    category: 'ted'
  },
  { 
    id: 'ted_latvia', 
    label: 'TED (Latvia)', 
    description: 'Tenders Electronic Daily - Latvia',
    category: 'ted'
  },
  { 
    id: 'ted_lithuania', 
    label: 'TED (Lithuania)', 
    description: 'Tenders Electronic Daily - Lithuania',
    category: 'ted'
  },
  { 
    id: 'ted_luxembourg', 
    label: 'TED (Luxembourg)', 
    description: 'Tenders Electronic Daily - Luxembourg',
    category: 'ted'
  }
];

const embeddingModels = [
  { 
    value: 'text-embedding-3-large', 
    label: 'OpenAI Large (Recommended)', 
    description: 'Most accurate, slower' 
  },
  { 
    value: 'text-embedding-3-small', 
    label: 'OpenAI Small', 
    description: 'Faster, less accurate' 
  },
  { 
    value: 'text-embedding-ada-002', 
    label: 'OpenAI Ada (Legacy)', 
    description: 'Legacy model, compatible' 
  }
];

const availableFields = [
  {
    id: 'initiation_date',
    label: 'Publication Date',
    description: 'Tender publication/initiation date',
    type: 'date'
  },
  {
    id: 'submission_deadline',
    label: 'Submission Deadline',
    description: 'Deadline for submitting offers',
    type: 'date'
  },
  {
    id: 'location',
    label: 'Location',
    description: 'Geographic location of tender',
    type: 'text'
  },
  {
    id: 'organization',
    label: 'Organization',
    description: 'Name of organization issuing the tender',
    type: 'text'
  },
  {
    id: 'procedure_type',
    label: 'Procedure Type',
    description: 'Type of tender procedure',
    type: 'select',
    options: ['Open', 'Restricted', 'Negotiated', 'Competitive Dialogue', 'Innovation Partnership']
  }
];

// Note: Backend only supports 'eq' and 'in' operators
const operatorOptions = [
  { value: 'eq', label: 'Equals', description: 'Exact match' },
  { value: 'in', label: 'In', description: 'Value from list of options' }
  // Removed unsupported operators: gt, lt, gte, lte, contains, starts_with
];

export function SearchForm({
  searchPhrase,
  setSearchPhrase,
  companyDescription,
  setCompanyDescription,
  sources,
  setSources,
  topK,
  setTopK,
  saveResults,
  setSaveResults,
  scoreThreshold,
  setScoreThreshold,
  embeddingModel,
  setEmbeddingModel,
  tenderNamesIndex,
  setTenderNamesIndex,
  elasticsearchIndex,
  setElasticsearchIndex,
  filterConditions,
  setFilterConditions,
  searchLoading,
  onRunSearch,
  analysisId,
  setAnalysisId,
  searchId,
  setSearchId,
  tenderIdsToCompare,
  setTenderIdsToCompare,
}: SearchFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  // Filter form state
  const [newFilter, setNewFilter] = useState<Partial<FilterCondition>>({});
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();
  const [multiSelectValues, setMultiSelectValues] = useState<string[]>([]);

  // Check which option is being used - Fix boolean logic
  const hasBrowserId = Boolean(analysisId && analysisId.trim().length > 0);
  const hasManualInput = Boolean((searchPhrase && searchPhrase.trim().length > 0) || (companyDescription && companyDescription.trim().length > 0) || sources.length > 0);
  const hasSearchId = Boolean(searchId && searchId.trim().length > 0);

  const handleRemoveSource = (sourceId: string) => {
    setSources(sources.filter(s => s !== sourceId));
  };

  const handleAddSource = (sourceId: string) => {
    if (sourceId && !sources.includes(sourceId)) {
      setSources([...sources, sourceId]);
    }
  };

  const getSourceLabel = (sourceId: string) => {
    const source = availableSources.find(s => s.id === sourceId);
    return source ? source.label : sourceId;
  };

  const availableSourcesForDropdown = availableSources.filter(
    source => !sources.includes(source.id)
  );

  // Filter helper functions
  const getFieldInfo = (fieldId: string) => {
    return availableFields.find(f => f.id === fieldId);
  };

  const getOperatorLabel = (op: string) => {
    return operatorOptions.find(o => o.value === op)?.label || op;
  };

  const getAvailableOperators = (fieldType: string) => {
    // Backend supports 'eq' and 'in' operators - allow both for all field types
    return [
      { value: 'eq', label: 'Equals', description: 'Exact match' },
      { value: 'in', label: 'In', description: 'Value from list of options' }
    ];
  };

  const addFilter = () => {
    if (!newFilter.field || !newFilter.op) return;

    const fieldInfo = getFieldInfo(newFilter.field);
    let value: string | string[];

    if (fieldInfo?.type === 'date') {
      if (newFilter.op === 'in') {
        value = multiSelectValues; // Array of date strings
      } else if (selectedDate) {
        value = format(selectedDate, 'yyyy-MM-dd'); // Single date string
      } else {
        return; // No date selected
      }
    } else if (fieldInfo?.type === 'select' && newFilter.op === 'in') {
      value = multiSelectValues; // Keep as array for 'in' operator
    } else if (newFilter.value) {
      value = typeof newFilter.value === 'string' ? newFilter.value.trim() : newFilter.value;
    } else {
      return;
    }

    // Validation
    if (!value || 
        (Array.isArray(value) && value.length === 0) || 
        (typeof value === 'string' && value.trim() === '')) {
      return;
    }

    console.log('🎯 ADDING FILTER:', {
      field: newFilter.field,
      op: newFilter.op,
      value: value,
      type: typeof value,
      isArray: Array.isArray(value)
    });

    const condition: FilterCondition = {
      field: newFilter.field,
      op: newFilter.op,
      value: value
    };

    setFilterConditions([...filterConditions, condition]);
    
    // Reset form
    setNewFilter({ field: '', op: '', value: '' });
    setSelectedDate(undefined);
    setMultiSelectValues([]);
  };

  const removeFilter = (index: number) => {
    setFilterConditions(filterConditions.filter((_, i) => i !== index));
  };

  const renderValueInput = () => {
    if (!newFilter.field) return null;

    const fieldInfo = getFieldInfo(newFilter.field);

    if (fieldInfo?.type === 'date') {
      if (newFilter.op === 'in') {
        // Multiple date selection for 'in' operator
        return (
          <div className="space-y-2">
            <Label>Select Dates</Label>
            <div className="space-y-2">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "justify-start text-left font-normal w-full",
                      !selectedDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {selectedDate ? format(selectedDate, "dd.MM.yyyy") : "Add date..."}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={selectedDate}
                    onSelect={(date) => {
                      if (date) {
                        const dateStr = format(date, 'yyyy-MM-dd');
                        if (!multiSelectValues.includes(dateStr)) {
                          setMultiSelectValues([...multiSelectValues, dateStr]);
                        }
                        setSelectedDate(undefined); // Reset after adding
                      }
                    }}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
              
              {multiSelectValues.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm text-muted-foreground">
                    Selected dates ({multiSelectValues.length}):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {multiSelectValues.map((dateStr, idx) => (
                      <Badge key={idx} variant="secondary" className="flex items-center gap-1">
                        {format(new Date(dateStr), "dd.MM.yyyy")}
                        <button
                          onClick={() => setMultiSelectValues(multiSelectValues.filter(d => d !== dateStr))}
                          className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      } else {
        // Single date selection for 'eq' operator - now matches multiple date styling
        return (
          <div className="space-y-2">
            <Label>Value</Label>
            <div className="space-y-2">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "justify-start text-left font-normal w-full",
                      !selectedDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {selectedDate ? format(selectedDate, "dd.MM.yyyy") : "Select date"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={selectedDate}
                    onSelect={setSelectedDate}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>
          </div>
        );
      }
    }

    if (fieldInfo?.type === 'select') {
      if (newFilter.op === 'in') {
        return (
          <div className="space-y-2">
            <Label>Values (multiple selection)</Label>
            <Select onValueChange={(value) => {
              if (!multiSelectValues.includes(value)) {
                setMultiSelectValues([...multiSelectValues, value]);
              }
            }}>
              <SelectTrigger>
                <SelectValue placeholder="Add value..." />
              </SelectTrigger>
              <SelectContent>
                {fieldInfo.options?.filter(opt => !multiSelectValues.includes(opt)).map(option => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                )) || []}
              </SelectContent>
            </Select>
            {multiSelectValues.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {multiSelectValues.map((value, idx) => (
                  <Badge key={idx} variant="secondary" className="flex items-center gap-1">
                    {value}
                    <button
                      onClick={() => setMultiSelectValues(multiSelectValues.filter(v => v !== value))}
                      className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>
        );
      } else {
        return (
          <div className="space-y-2">
            <Label>Value</Label>
            <Select onValueChange={(value) => setNewFilter({ ...newFilter, value })}>
              <SelectTrigger>
                <SelectValue placeholder="Select value..." />
              </SelectTrigger>
              <SelectContent>
                {fieldInfo.options?.map(option => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                )) || []}
              </SelectContent>
            </Select>
          </div>
        );
      }
    }

    return (
      <div className="space-y-2">
        <Label>Value</Label>
        <Input
          placeholder="Enter value..."
          value={newFilter.value || ''}
          onChange={(e) => setNewFilter({ ...newFilter, value: e.target.value })}
        />
      </div>
    );
  };

  const formatFilterValue = (condition: FilterCondition) => {
    if (Array.isArray(condition.value)) {
      return condition.value.join(', ');
    }
    return condition.value;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Tender Search Test
        </CardTitle>
        <CardDescription>
          Configure and run tender search operations
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Browser ID Option */}
        <div className={cn(
          "space-y-2 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasManualInput || hasSearchId) && !hasBrowserId && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            Option 1: Saved Configuration
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="browser-id">Browser ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Load search configuration from a saved tender browser session</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="browser-id"
              placeholder="60f7c8e4a4b3f12d34567890"
              value={analysisId}
              onChange={(e) => setAnalysisId(e.target.value)}
              disabled={(hasManualInput || hasSearchId) && !hasBrowserId}
            />
          </div>
        </div>

        {/* Manual Configuration Option - NOW OPTION 2 */}
        <div className={cn(
          "space-y-4 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasBrowserId || hasSearchId) && !hasManualInput && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            Option 2: Create New Search
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="search-phrase">Search Phrase</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Keywords to search in tender titles and descriptions</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="search-phrase"
              placeholder="e.g. solar panels, construction, IT services"
              value={searchPhrase}
              onChange={(e) => setSearchPhrase(e.target.value)}
              disabled={(hasBrowserId || hasSearchId) && !hasManualInput}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="company-description">Company Description (Optional)</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Describe your company to find relevant tenders using AI matching</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Textarea
              id="company-description"
              placeholder="e.g. We are a renewable energy company specializing in solar panel installation and maintenance..."
              value={companyDescription}
              onChange={(e) => setCompanyDescription(e.target.value)}
              rows={3}
              disabled={(hasBrowserId || hasSearchId) && !hasManualInput}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label>Data Sources</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Select which databases to search for tenders. If none selected, all available sources will be searched.</p>
                </TooltipContent>
              </Tooltip>
            </div>
            
            {/* Current Sources List */}
            {sources.length > 0 && (
              <div className="space-y-2 p-3 border rounded-md bg-secondary/20">
                <div className="text-sm font-medium text-muted-foreground">
                  Selected sources ({sources.length}):
                </div>
                <div className="flex flex-wrap gap-2">
                  {sources.map((sourceId) => (
                    <Badge
                      key={sourceId}
                      variant="secondary"
                      className="flex items-center gap-1 pr-1"
                    >
                      {getSourceLabel(sourceId)}
                      <button
                        type="button"
                        onClick={() => handleRemoveSource(sourceId)}
                        className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                        disabled={(hasBrowserId || hasSearchId) && !hasManualInput}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Add Source Dropdown */}
            <div>
              <Select value="" onValueChange={handleAddSource} disabled={(hasBrowserId || hasSearchId) && !hasManualInput}>
                <SelectTrigger>
                  <SelectValue placeholder={
                    sources.length === 0 
                      ? "All sources selected" 
                      : "Add specific source..."
                  } />
                </SelectTrigger>
                <SelectContent>
                  <div className="font-medium px-2 py-1 text-xs text-muted-foreground">
                    Polish Platforms
                  </div>
                  {availableSourcesForDropdown
                    .filter(source => source.category === 'polish')
                    .map((source) => (
                      <SelectItem key={source.id} value={source.id}>
                        <div>
                          <div className="font-medium">{source.label}</div>
                          <div className="text-xs text-muted-foreground">{source.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  
                  <div className="font-medium px-2 py-1 text-xs text-muted-foreground mt-2">
                    Corporate Platforms
                  </div>
                  {availableSourcesForDropdown
                    .filter(source => source.category === 'corporate')
                    .map((source) => (
                      <SelectItem key={source.id} value={source.id}>
                        <div>
                          <div className="font-medium">{source.label}</div>
                          <div className="text-xs text-muted-foreground">{source.description}</div>
                        </div>
                      </SelectItem>
                    ))}

                  <div className="font-medium px-2 py-1 text-xs text-muted-foreground mt-2">
                    German Platforms
                  </div>
                  {availableSourcesForDropdown
                    .filter(source => source.category === 'german')
                    .map((source) => (
                      <SelectItem key={source.id} value={source.id}>
                        <div>
                          <div className="font-medium">{source.label}</div>
                          <div className="text-xs text-muted-foreground">{source.description}</div>
                        </div>
                      </SelectItem>
                    ))}

                  <div className="font-medium px-2 py-1 text-xs text-muted-foreground mt-2">
                    TED (Europe)
                  </div>
                  {availableSourcesForDropdown
                    .filter(source => source.category === 'ted')
                    .map((source) => (
                      <SelectItem key={source.id} value={source.id}>
                        <div>
                          <div className="font-medium">{source.label}</div>
                          <div className="text-xs text-muted-foreground">{source.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
           </div>
         </div>

        {/* Search ID Option - NOW OPTION 3 */}
        <div className={cn(
          "space-y-2 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasBrowserId || hasManualInput) && !hasSearchId && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
            Option 3: Retrieve Saved Results
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="search-id-main">Search ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Retrieve previously completed search results</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="search-id-main"
              placeholder="684c358348d483311fdc0e08"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              disabled={(hasBrowserId || hasManualInput) && !hasSearchId}
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label htmlFor="top-k">Maximum Number of Results</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Maximum number of tender results to return (1-100)</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Input
            id="top-k"
            type="number"
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value) || 30)}
            min="1"
            max="100"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Switch
            id="save-results"
            checked={saveResults}
            onCheckedChange={setSaveResults}
          />
          <Label htmlFor="save-results" className="text-sm">
            Save Results for Later Analysis
          </Label>
        </div>

        {/* Advanced Filters Toggle */}
        <Collapsible open={showFilters} onOpenChange={setShowFilters}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0">
              <span className="text-sm font-medium">
                Advanced Filters {filterConditions.length > 0 && `(${filterConditions.length})`}
              </span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            {/* Current Filters */}
            {filterConditions.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">Active filters ({filterConditions.length}):</Label>
                <div className="space-y-2 p-3 border rounded-md bg-secondary/20">
                  {filterConditions.map((condition, index) => {
                    const fieldInfo = getFieldInfo(condition.field);
                    return (
                      <div key={index} className="flex items-center justify-between bg-background p-2 rounded border">
                        <div className="flex-1">
                          <div className="text-sm font-medium">
                            {fieldInfo?.label || condition.field}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {getOperatorLabel(condition.op)}: {formatFilterValue(condition)}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFilter(index)}
                          className="h-8 w-8 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Add New Filter */}
            <div className="space-y-4 p-4 border rounded-md">
              <Label className="text-sm font-medium flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Add new filter:
              </Label>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label>Field</Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Select field to filter by</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Select value={newFilter.field || ''} onValueChange={(value) => {
                    // Don't auto-set operator for any field type now - let user choose
                    setNewFilter({ field: value, op: '', value: '' });
                    // Reset form state
                    setSelectedDate(undefined);
                    setMultiSelectValues([]);
                  }}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select field..." />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFields.map(field => (
                        <SelectItem key={field.id} value={field.id}>
                          {field.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Always show operator dropdown when field is selected */}
                {newFilter.field && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Label>Operator</Label>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Select value comparison method</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Select 
                      value={newFilter.op || ''}
                      onValueChange={(value) => {
                        setNewFilter({ ...newFilter, op: value });
                        // Reset value-related state when operator changes
                        setSelectedDate(undefined);
                        setMultiSelectValues([]);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select operator..." />
                      </SelectTrigger>
                      <SelectContent>
                        {getAvailableOperators('any').map(op => (
                          <SelectItem key={op.value} value={op.value}>
                            {op.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              {newFilter.field && newFilter.op && (
                <div className="space-y-4">
                  {renderValueInput()}
                  
                  <Button
                    onClick={addFilter}
                    disabled={!newFilter.field || !newFilter.op || (!newFilter.value && !selectedDate && multiSelectValues.length === 0)}
                    className="w-full"
                    size="sm"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Filter
                  </Button>
                </div>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Advanced Settings */}
        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0">
              <span className="text-sm font-medium">Advanced Settings</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
             <div className="space-y-2">
               <div className="flex items-center gap-2">
                 <Label htmlFor="tender-ids-compare">Tender IDs to Compare (Optional)</Label>
                 <Tooltip>
                   <TooltipTrigger>
                     <Info className="h-4 w-4 text-muted-foreground" />
                   </TooltipTrigger>
                   <TooltipContent>
                     <p>Comma-separated list of tender IDs to compare against search results</p>
                   </TooltipContent>
                 </Tooltip>
               </div>
               <Textarea
                 id="tender-ids-compare"
                 placeholder="tender_id_1, tender_id_2, tender_id_3"
                 value={tenderIdsToCompare?.join(', ') || ''}
                 onChange={(e) => setTenderIdsToCompare(
                   e.target.value.split(',').map(id => id.trim()).filter(id => id.length > 0)
                 )}
                 rows={2}
               />
             </div>

             <div className="space-y-2">
               <div className="flex items-center gap-2">
                 <Label>Quality Threshold: {scoreThreshold[0].toFixed(2)}</Label>
                 <Tooltip>
                   <TooltipTrigger>
                     <Info className="h-4 w-4 text-muted-foreground" />
                   </TooltipTrigger>
                   <TooltipContent>
                     <p>Minimum relevance score (0.0-1.0). Higher = more strict matching</p>
                   </TooltipContent>
                 </Tooltip>
               </div>
               <Slider
                 value={scoreThreshold}
                 onValueChange={setScoreThreshold}
                 max={1}
                 min={0}
                 step={0.1}
                 className="w-full"
               />
               <div className="flex justify-between text-xs text-muted-foreground">
                 <span>Loose (0.0)</span>
                 <span>Strict (1.0)</span>
               </div>
             </div>

            {/* AI Model selection - hidden but kept in code */}
            {/* 
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label>AI Model</Label>
                <Tooltip>
                  <TooltipTrigger>
                    <Info className="h-4 w-4 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>AI model used for semantic matching. Large = more accurate but slower</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Select value={embeddingModel} onValueChange={setEmbeddingModel}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {embeddingModels.map((model) => (
                    <SelectItem key={model.value} value={model.value}>
                      <div>
                        <div className="font-medium">{model.label}</div>
                        <div className="text-xs text-muted-foreground">{model.description}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            */}

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <Label htmlFor="tender-names-index">Tender Index</Label>
                <Input
                  id="tender-names-index"
                  value={tenderNamesIndex}
                  onChange={(e) => setTenderNamesIndex(e.target.value)}
                  placeholder="tenders"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="elasticsearch-index">Search Index</Label>
                <Input
                  id="elasticsearch-index"
                  value={elasticsearchIndex}
                  onChange={(e) => setElasticsearchIndex(e.target.value)}
                  placeholder="tenders"
                />
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <Button 
          onClick={onRunSearch} 
          disabled={searchLoading}
          className="w-full"
        >
          {searchLoading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          Run Search
        </Button>

        <Button 
          onClick={() => {
            setSearchPhrase('');
            setCompanyDescription('');
            setSources([]);
            setAnalysisId('');
            setSearchId('');
            setTenderIdsToCompare([]);
            setFilterConditions([]);
            setTopK(30);
            setSaveResults(true);
            setScoreThreshold([0.5]);
            setEmbeddingModel('text-embedding-3-large');
            setTenderNamesIndex('tenders');
            setElasticsearchIndex('tenders');
            // Reset filter form state
            setNewFilter({});
            setSelectedDate(undefined);
            setMultiSelectValues([]);
          }}
          variant="outline"
          className="w-full"
        >
          Clear Form
        </Button>
      </CardContent>
    </Card>
  );
}
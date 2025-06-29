"use client"
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Loader2, Filter, Play, Info, ChevronDown } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface SearchResult {
  search_id: string;
}

interface FilterFormProps {
  analysisId: string;
  setAnalysisId: (value: string) => void;
  searchId: string;
  setSearchId: (value: string) => void;
  companyDescription: string;
  setCompanyDescription: (value: string) => void;
  searchPhrase: string;
  setSearchPhrase: (value: string) => void;
  filterId: string;
  setFilterId: (value: string) => void;
  aiBatchSize: number;
  setAiBatchSize: (value: number) => void;
  saveResults: boolean;
  setSaveResults: (value: boolean) => void;
  tenderIdsToCompare: string[];
  setTenderIdsToCompare: (value: string[]) => void;
  filterLoading: boolean;
  onRunFilter: () => void;
  searchResults: SearchResult | null;
}

export function FilterForm({
  analysisId,
  setAnalysisId,
  searchId,
  setSearchId,
  companyDescription,
  setCompanyDescription,
  searchPhrase,
  setSearchPhrase,
  filterId,
  setFilterId,
  aiBatchSize,
  setAiBatchSize,
  saveResults,
  setSaveResults,
  tenderIdsToCompare,
  setTenderIdsToCompare,
  filterLoading,
  onRunFilter,
  searchResults,
}: FilterFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [option1SearchId, setOption1SearchId] = useState('');
  const [option2SearchId, setOption2SearchId] = useState('');

  // ANY field in option 1 means lock option 2 and 3
  const hasOption1Input = Boolean(analysisId.trim() || option1SearchId.trim());
  // ANY field in option 2 means lock option 1 and 3  
  const hasOption2Input = Boolean(companyDescription.trim() || searchPhrase.trim() || option2SearchId.trim());
  // ANY field in option 3 means lock option 1 and 2
  const hasOption3Input = Boolean(filterId.trim());

  // Update main searchId based on which option is being used
  const handleOption1SearchChange = (value: string) => {
    setOption1SearchId(value);
    setSearchId(value);
  };

  const handleOption2SearchChange = (value: string) => {
    setOption2SearchId(value);
    setSearchId(value);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Filter className="h-5 w-5" />
          Tender Filtering Test
        </CardTitle>
        <CardDescription>
          Apply AI filtering to search results
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Browser Configuration ID Option */}
        <div className={cn(
          "space-y-4 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasOption2Input || hasOption3Input) && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            Option 1: Browser Configuration
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="search-id-1">Search Results ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>ID of search results to apply filtering to</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="search-id-1"
              placeholder="684c358348d483311fdc0e08"
              value={option1SearchId}
              onChange={(e) => handleOption1SearchChange(e.target.value)}
              disabled={hasOption2Input}
            />
            {searchResults && searchResults.search_id && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleOption1SearchChange(searchResults.search_id)}
                className="text-xs w-full"
                disabled={hasOption2Input}
              >
                Use last search ID ({searchResults.search_id.substring(0, 8)}...)
              </Button>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="analysis-id">Browser Configuration ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>ID of saved browser configuration containing filtering criteria</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="analysis-id"
              placeholder="60f7c8e4a4b3f12d34567890"
              value={analysisId}
              onChange={(e) => setAnalysisId(e.target.value)}
              disabled={hasOption2Input}
            />
          </div>
        </div>

        {/* Manual Configuration Option */}
        <div className={cn(
          "space-y-4 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasOption1Input || hasOption3Input) && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            Option 2: Manual Configuration
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="search-id-2">Search Results ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>ID of saved search results to filter</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="search-id-2"
              placeholder="684c358348d483311fdc0e08"
              value={option2SearchId}
              onChange={(e) => handleOption2SearchChange(e.target.value)}
              disabled={hasOption1Input}
            />
            {searchResults && searchResults.search_id && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleOption2SearchChange(searchResults.search_id)}
                className="text-xs w-full"
                disabled={hasOption1Input}
              >
                Use last search ID ({searchResults.search_id.substring(0, 8)}...)
              </Button>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="filter-search-phrase">Search Phrase</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Keywords for filtering criteria</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="filter-search-phrase"
              placeholder="e.g. solar panels, construction, IT services"
              value={searchPhrase}
              onChange={(e) => setSearchPhrase(e.target.value)}
              disabled={hasOption1Input}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="filter-company-description">Company Description</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>Describe your company for filtering criteria</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Textarea
              id="filter-company-description"
              placeholder="e.g. We are a renewable energy company..."
              value={companyDescription}
              onChange={(e) => setCompanyDescription(e.target.value)}
              className="min-h-[100px]"
              disabled={hasOption1Input}
            />
          </div>
        </div>

        {/* Retrieve Saved Filter Results Option */}
        <div className={cn(
          "space-y-4 p-3 border rounded-lg bg-muted/20 transition-all duration-200",
          (hasOption1Input || hasOption2Input) && "opacity-50 pointer-events-none"
        )}>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
            Option 3: Retrieve Saved Filter Results
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="filter-id">Filter Results ID</Label>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>ID of previously saved filter results to retrieve</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="filter-id"
              placeholder="60f7c8e4a4b3f12d34567890"
              value={filterId}
              onChange={(e) => setFilterId(e.target.value)}
              disabled={hasOption1Input || hasOption2Input}
            />
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Switch
            id="save-filter-results"
            checked={saveResults}
            onCheckedChange={setSaveResults}
          />
          <Label htmlFor="save-filter-results" className="text-sm">
            Save Filter Results
          </Label>
        </div>

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
                <Label htmlFor="ai-batch-size">AI Batch Size</Label>
                <Tooltip>
                  <TooltipTrigger>
                    <Info className="h-4 w-4 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Number of tenders to process in each AI batch (default: 20)</p>
                  </TooltipContent>
                  </Tooltip>
              </div>
              <Input
                id="ai-batch-size"
                type="number"
                value={aiBatchSize}
                onChange={(e) => setAiBatchSize(parseInt(e.target.value) || 20)}
                min="1"
                max="100"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="tender-ids-compare">Tender IDs to Compare (Optional)</Label>
                <Tooltip>
                  <TooltipTrigger>
                    <Info className="h-4 w-4 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Comma-separated list of tender IDs for comparison analysis</p>
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
          </CollapsibleContent>
        </Collapsible>

        <Button 
          onClick={onRunFilter} 
          disabled={filterLoading}
          className="w-full"
        >
          {filterLoading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          Run AI Filter
        </Button>

        <Button 
          onClick={() => {
            setAnalysisId('');
            setOption1SearchId('');
            setOption2SearchId('');
            setSearchId('');
            setCompanyDescription('');
            setSearchPhrase('');
            setFilterId('');
            setTenderIdsToCompare([]);
            setAiBatchSize(20);
            setSaveResults(true);
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
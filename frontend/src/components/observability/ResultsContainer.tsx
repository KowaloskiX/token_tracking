"use client"
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Copy, Download } from 'lucide-react';
import { SearchResultsPanel } from './SearchResultsPanel';
import { FilterResultsPanel } from './FilterResultsPanel';
import { 
  SearchResult, 
  SearchResponse, 
  FilterResponse, 
  ComparisonData, 
  ComparisonOperation 
} from '@/types/observability';

interface ResultsContainerProps {
  type: 'search' | 'filter';
  searchResults?: SearchResponse | null;
  filterResults?: FilterResponse | null;
  sources?: string[];
  onCopyId: (id: string) => void;
  onExportCsv: (data: SearchResult[], filename: string) => void;
  comparison?: ComparisonData;
  comparisonOperation?: ComparisonOperation;
}

export function ResultsContainer({
  type,
  searchResults,
  filterResults,
  sources = [],
  onCopyId,
  onExportCsv,
  comparison,
  comparisonOperation,
}: ResultsContainerProps) {
  if (type === 'search') {
    return (
      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Search Results</CardTitle>
              {searchResults && (
                <CardDescription>
                  ID: {searchResults.search_id} • {searchResults.total_matches} matches
                  {comparison && comparisonOperation && (
                    <span className="ml-2 text-blue-600">
                      • vs {comparisonOperation.id.substring(0, 8)}...
                    </span>
                  )}
                  <span className="ml-2 text-muted-foreground text-xs">
                    (last result)
                  </span>
                </CardDescription>
              )}
            </div>
            {searchResults && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onCopyId(searchResults.search_id)}
                >
                  <Copy className="h-4 w-4 mr-1" />
                  Copy ID
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onExportCsv(searchResults.matches, `search-${searchResults.search_id}.csv`)}
                >
                  <Download className="h-4 w-4 mr-1" />
                  Export CSV
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {searchResults ? (
            <SearchResultsPanel 
              results={searchResults} 
              sources={sources}
              comparison={comparison}
              comparisonOperation={comparisonOperation}
            />
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              No search results. Run a search to see results here.
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Filter Results</CardTitle>
            {filterResults && (
              <CardDescription>
                ID: {filterResults.initial_ai_filter_id}
                {comparison && comparisonOperation && (
                  <span className="ml-2 text-blue-600">
                    • vs {comparisonOperation.id.substring(0, 8)}...
                  </span>
                )}
                <span className="ml-2 text-muted-foreground text-xs">
                  (last result)
                </span>
              </CardDescription>
            )}
          </div>
          {filterResults && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onCopyId(filterResults.initial_ai_filter_id)}
              >
                <Copy className="h-4 w-4 mr-1" />
                Copy ID
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onExportCsv(filterResults.filtered_tenders, `filter-${filterResults.initial_ai_filter_id}.csv`)}
              >
                <Download className="h-4 w-4 mr-1" />
                Export CSV
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {filterResults ? (
          <FilterResultsPanel 
            results={filterResults}
            comparison={comparison}
            comparisonOperation={comparisonOperation}
          />
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            No filter results. Run a filter operation to see results here.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
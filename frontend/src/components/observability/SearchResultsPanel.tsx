import React from 'react';
import { MetricsDisplay } from './MetricsDisplay';
import { TenderTable } from './TenderTable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { 
  SearchResponse, 
  ComparisonData, 
  ComparisonOperation 
} from '@/types/observability';

interface SearchResultsPanelProps {
  results: SearchResponse;
  sources: string[];
  comparison?: ComparisonData;
  comparisonOperation?: ComparisonOperation;
}

export function SearchResultsPanel({ 
  results, 
  sources, 
  comparison, 
  comparisonOperation 
}: SearchResultsPanelProps) {
  if (comparison) {
    const netChange = comparison.summary.newCount - comparison.summary.removedCount;

    return (
      <div className="space-y-4">
        {/* Comparison Stats */}
        <MetricsDisplay 
          stats={[
            { label: 'Total Matches', value: results.total_matches, color: 'text-primary' },
            { label: 'Sources Used', value: sources.length === 0 ? 'All' : sources.length, color: 'text-blue-600' },
            { 
              label: 'Net Change', 
              value: `${netChange > 0 ? '+' : ''}${netChange}`, 
              color: netChange > 0 ? 'text-green-600' : netChange < 0 ? 'text-red-600' : 'text-gray-600' 
            }
          ]}
        />

        {/* Comparison Banner - Updated with creamy colors */}
        <div className="bg-secondary border border-secondary-border rounded-lg p-3">
          <div className="text-sm text-primary">
            📊 Comparing with search from {comparisonOperation ? formatDistanceToNow(new Date(comparisonOperation.timestamp), { addSuffix: true }) : 'previous operation'}
            {comparisonOperation && (
              <span className="ml-1 font-mono text-xs text-muted-foreground">
                ({comparisonOperation.id.substring(0, 8)}...)
              </span>
            )}
          </div>
        </div>

        {/* Simplified Comparison Results with 5 Tabs */}
        <Tabs defaultValue="this" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="this" className="relative">
              This
              <Badge variant="secondary" className="ml-2 text-xs">
                {results.matches.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="previous" className="relative">
              Previous
              <Badge variant="secondary" className="ml-2 text-xs bg-gray-100 text-gray-700">
                {comparison.common.length + comparison.removed.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="added" className="relative">
              Added
              <Badge variant="secondary" className="ml-2 text-xs bg-green-100 text-green-700">
                +{comparison.summary.newCount}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="unchanged" className="relative">
              Unchanged
              <Badge variant="secondary" className="ml-2 text-xs bg-blue-100 text-blue-700">
                {comparison.summary.commonCount}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="removed" className="relative">
              Removed
              <Badge variant="secondary" className="ml-2 text-xs bg-red-100 text-red-700">
                -{comparison.summary.removedCount}
              </Badge>
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="this" className="space-y-2">
            <div className="text-sm text-muted-foreground mb-2">
              Results from the current search operation
            </div>
            <TenderTable results={results.matches} />
          </TabsContent>
          
          <TabsContent value="previous" className="space-y-2">
            <div className="text-sm text-muted-foreground mb-2">
              Results from the previous search operation
            </div>
            <TenderTable results={[...comparison.common, ...comparison.removed]} />
          </TabsContent>
          
          <TabsContent value="added" className="space-y-2">
            <div className="text-sm text-muted-foreground mb-2">
              Results that are new in this search (not in previous search)
            </div>
            <TenderTable results={comparison.new} />
          </TabsContent>
          
          <TabsContent value="unchanged" className="space-y-2">
            <div className="text-sm text-muted-foreground mb-2">
              Results that appear in both current and previous search
            </div>
            <TenderTable results={comparison.common} />
          </TabsContent>
          
          <TabsContent value="removed" className="space-y-2">
            <div className="text-sm text-muted-foreground mb-2">
              Results that were in the previous search but not in current search
            </div>
            <TenderTable results={comparison.removed} />
          </TabsContent>
        </Tabs>
      </div>
    );
  }

  // Regular display without comparison
  return (
    <div className="space-y-4">
      <MetricsDisplay 
        stats={[
          { label: 'Total Matches', value: results.total_matches, color: 'text-primary' },
          { label: 'Sources Used', value: sources.length === 0 ? 'All' : sources.length, color: 'text-blue-600' }
        ]}
      />
      <TenderTable results={results.matches} />
    </div>
  );
}
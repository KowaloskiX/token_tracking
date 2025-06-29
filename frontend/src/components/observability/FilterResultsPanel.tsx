import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TenderTable } from './TenderTable';
import { MetricsDisplay } from './MetricsDisplay';
import { formatDistanceToNow } from 'date-fns';
import { 
  FilterResponse, 
  FilterResult, 
  ComparisonData, 
  ComparisonOperation 
} from '@/types/observability';

interface FilterResultsPanelProps {
  results: FilterResponse;
  comparison?: ComparisonData;
  comparisonOperation?: ComparisonOperation;
}

export function FilterResultsPanel({ 
  results, 
  comparison, 
  comparisonOperation 
}: FilterResultsPanelProps) {
  const retentionRate = Math.round(
    (results.total_filtered / (results.total_filtered + results.total_filtered_out)) * 100
  );

  return (
    <div className="space-y-4">
      {/* Stats using MetricsDisplay */}
      <MetricsDisplay 
        stats={[
          { label: 'Kept (Relevant)', value: results.total_filtered, color: 'text-green-600' },
          { label: 'Filtered Out', value: results.total_filtered_out, color: 'text-red-600' },
          { label: 'Retention Rate', value: `${retentionRate}%`, color: 'text-blue-600' },
          ...(comparison ? [{ 
            label: 'Net Change', 
            value: `${comparison.summary.newCount - comparison.summary.removedCount > 0 ? '+' : ''}${comparison.summary.newCount - comparison.summary.removedCount}`, 
            color: comparison.summary.newCount > comparison.summary.removedCount ? 'text-green-600' : 
                   comparison.summary.newCount < comparison.summary.removedCount ? 'text-red-600' : 'text-gray-600'
          }] : [])
        ]}
      />

      {/* Results with Backend Comparison (tender_ids_to_compare) */}
      {results.comparison ? (
        <Card>
          <CardHeader>
            <CardTitle>Filter Results with Tender ID Comparison</CardTitle>
            <CardDescription>
              Comparing AI filtered results against provided tender IDs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="filtered" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="filtered">All Filtered ({results.total_filtered})</TabsTrigger>
                <TabsTrigger value="covered">Covered ({results.comparison.total_covered})</TabsTrigger>
                <TabsTrigger value="extra">Extra ({results.comparison.total_extra_filtered})</TabsTrigger>
                <TabsTrigger value="missing">Missing ({results.comparison.total_missing})</TabsTrigger>
              </TabsList>
              
              <TabsContent value="filtered" className="space-y-2">
                <h4 className="font-medium text-sm">All Filtered Results</h4>
                <TenderTable results={results.filtered_tenders} maxRows={10} />
              </TabsContent>
              
              <TabsContent value="covered" className="space-y-2">
                <h4 className="font-medium text-sm">Covered by AI Filter</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Tenders that were in your comparison list AND kept by AI filter
                </p>
                <TenderTable results={results.comparison.covered} maxRows={10} />
              </TabsContent>
              
              <TabsContent value="extra" className="space-y-2">
                <h4 className="font-medium text-sm">Extra Filtered by AI</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Tenders kept by AI filter but NOT in your comparison list
                </p>
                <TenderTable results={results.comparison.extra_filtered} maxRows={10} />
              </TabsContent>
              
              <TabsContent value="missing" className="space-y-2">
                <h4 className="font-medium text-sm">Missing from AI Filter</h4>
                <p className="text-xs text-muted-foreground mb-2">
                  Tender IDs from your comparison list that were NOT kept by AI filter
                </p>
                <div className="space-y-2">
                  {results.comparison.missing_ids.map((id, index) => (
                    <Badge key={index} variant="outline" className="mr-2 mb-2">
                      {id}
                    </Badge>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      ) : comparison ? (
        /* History-based comparison results */
        <div className="space-y-4">
          {/* Comparison Banner - Updated with creamy colors */}
          <div className="bg-secondary border border-secondary-border rounded-lg p-3">
            <div className="text-sm text-primary">
              📊 Comparing with filter from {comparisonOperation ? formatDistanceToNow(new Date(comparisonOperation.timestamp), { addSuffix: true }) : 'previous operation'}
              {comparisonOperation && (
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  ({comparisonOperation.id.substring(0, 8)}...)
                </span>
              )}
            </div>
          </div>

          <Tabs defaultValue="this" className="w-full">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="this" className="relative">
                This
                <Badge variant="secondary" className="ml-2 text-xs">
                  {results.filtered_tenders.length}
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
                Results from the current filter operation
              </div>
              <TenderTable results={results.filtered_tenders} />
            </TabsContent>
            
            <TabsContent value="previous" className="space-y-2">
              <div className="text-sm text-muted-foreground mb-2">
                Results from the previous filter operation
              </div>
              <TenderTable results={[...comparison.common, ...comparison.removed]} />
            </TabsContent>
            
            <TabsContent value="added" className="space-y-2">
              <div className="text-sm text-muted-foreground mb-2">
                Results that are new in this filter (not in previous filter)
              </div>
              <TenderTable results={comparison.new} />
            </TabsContent>
            
            <TabsContent value="unchanged" className="space-y-2">
              <div className="text-sm text-muted-foreground mb-2">
                Results that appear in both current and previous filter
              </div>
              <TenderTable results={comparison.common} />
            </TabsContent>
            
            <TabsContent value="removed" className="space-y-2">
              <div className="text-sm text-muted-foreground mb-2">
                Results that were in the previous filter but not in current filter
              </div>
              <TenderTable results={comparison.removed} />
            </TabsContent>
          </Tabs>
        </div>
      ) : (
        /* Original simple display when no comparison */
        <div className="space-y-2">
          <h4 className="font-medium text-sm">Kept Results</h4>
          <TenderTable results={results.filtered_tenders} />  {/* ✅ Shows all results */}
        </div>
      )}
    </div>
  );
}
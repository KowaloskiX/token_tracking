"use client"
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { History, Search, Filter, Copy, CheckCircle, AlertCircle, Clock, Target } from 'lucide-react';
import { HistoryItem } from '@/types/observability';

interface HistoryTableProps {
  history: HistoryItem[];
  onCopyId: (id: string) => void;
}

export function HistoryTable({ history, onCopyId }: HistoryTableProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'success':
        return 'Success';
      case 'warning':
        return 'Warning';
      case 'error':
        return 'Error';
      default:
        return status;
    }
  };

  const getEndpointText = (endpoint: string) => {
    switch (endpoint) {
      case 'search':
        return 'Search';
      case 'filter':
        return 'Filter';
      case 'analyze-single-tender':
        return 'Analysis';
      default:
        return endpoint;
    }
  };

  const getEndpointIcon = (endpoint: string) => {
    switch (endpoint) {
      case 'search':
        return <Search className="h-4 w-4" />;
      case 'filter':
        return <Filter className="h-4 w-4" />;
      case 'analyze-single-tender':
        return <Target className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  // Sort history by timestamp (newest first)
  const sortedHistory = [...history].sort((a, b) => 
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Operation History
        </CardTitle>
        <CardDescription>
          Browse and manage previous search, filter, and analysis operations
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sortedHistory.length > 0 ? (
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedHistory.map((item) => (
                  <TableRow key={item.timestamp}>
                    <TableCell className="text-sm">
                      {new Date(item.timestamp).toLocaleString('en-US')}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getEndpointIcon(item.endpoint)}
                        <span>{getEndpointText(item.endpoint)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {item.id.substring(0, 12)}...
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(item.status)}
                        <span className="text-sm">{getStatusText(item.status)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.endpoint === 'search' && item.results && 'total_matches' in item.results ? (
                        `${item.results.total_matches} matches`
                      ) : item.endpoint === 'filter' && item.results && 'total_filtered' in item.results ? (
                        `${item.results.total_filtered} kept, ${item.results.total_filtered_out} filtered out`
                      ) : item.endpoint === 'analyze-single-tender' && item.results && 'result' in item.results && item.results.result && item.results.result.tender_score !== undefined ? (
                        `Score: ${(item.results.result.tender_score * 100).toFixed(1)}%`
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onCopyId(item.id)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            No operations in history.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
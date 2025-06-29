import React, { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react';

interface TenderResult {
  id: string;
  name: string;
  organization: string;
  location: string;
  source: string;
  score?: number;
  source_type: string;
}

interface TenderTableProps {
  results: TenderResult[];
  pageSize?: number;
  maxRows?: number;
}

export function TenderTable({ results, pageSize = 20, maxRows }: TenderTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  
  // Use maxRows if provided, otherwise use all results
  const limitedResults = maxRows ? results.slice(0, maxRows) : results;
  
  const totalPages = Math.ceil(limitedResults.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const displayResults = limitedResults.slice(startIndex, endIndex);

  const truncateText = (text: string | null | undefined, maxLength: number) => {
    if (!text || typeof text !== 'string') {
      return 'N/A';
    }
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
  };

  const goToPage = (page: number) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
  };

  return (
    <TooltipProvider>
    <div className="space-y-4">
      <div className="border rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead className="w-48 max-w-48">Name</TableHead>
              <TableHead className="w-40 max-w-40">Organization</TableHead>
              <TableHead className="w-24">Source</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayResults.map((result, index) => (
              <TableRow key={result.id}>
                <TableCell className="font-medium w-12">{startIndex + index + 1}</TableCell>
                <TableCell className="w-48 max-w-48">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="truncate cursor-help">
                        {truncateText(result.name, 40)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-sm">
                      <p className="whitespace-normal">{result.name}</p>
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="w-40 max-w-40">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="truncate cursor-help">
                        {truncateText(result.organization, 30)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-sm">
                      <p className="whitespace-normal">{result.organization}</p>
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="w-24">
                  <Badge variant="secondary" className="text-xs">
                    {truncateText(result.source, 12)}
                  </Badge>
                </TableCell>
                <TableCell className="w-12">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(result.id, '_blank')}
                    className="h-7 w-7 p-0"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      
      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {startIndex + 1}-{Math.min(endIndex, limitedResults.length)} of {limitedResults.length} results
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="flex items-center space-x-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const page = i + Math.max(1, currentPage - 2);
                if (page > totalPages) return null;
                return (
                  <Button
                    key={page}
                    variant={page === currentPage ? "default" : "outline"}
                    size="sm"
                    onClick={() => goToPage(page)}
                    className="w-8 h-8 p-0"
                  >
                    {page}
                  </Button>
                );
              })}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}
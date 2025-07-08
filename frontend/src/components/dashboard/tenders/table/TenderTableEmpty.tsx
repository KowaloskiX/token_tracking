import React, { useEffect, useRef } from 'react';
import { TableRow, TableCell } from '@/components/ui/table';
import { createPortal } from 'react-dom';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderTableEmptyProps {
  tableWidth: number;
  allResultsLength: number;
  selectedAnalysis: any;
  columnCount: number;
}

export const TenderTableEmpty: React.FC<TenderTableEmptyProps> = ({
  tableWidth,
  allResultsLength,
  selectedAnalysis,
  columnCount
}) => {
  const t = useTendersTranslations();
  const cellRef = useRef<HTMLTableCellElement>(null);

  const getMessage = () => {
    if (allResultsLength > 0) {
      return t('tenders.list.noTenders');
    } else if (selectedAnalysis) {
      return t('tenders.list.noResults');
    } else {
      return t('tenders.list.selectAnalysis');
    }
  };

  // Find the table container to create an overlay
  const getTableContainer = () => {
    if (!cellRef.current) return null;
    
    // Walk up the DOM to find the table container (the div with relative positioning)
    let element = cellRef.current.parentElement;
    while (element) {
      if (element.classList.contains('overflow-hidden') && 
          element.classList.contains('relative')) {
        return element;
      }
      element = element.parentElement;
    }
    return null;
  };

  const tableContainer = getTableContainer();

  const emptyStateOverlay = (
    <div 
      className="absolute inset-0 flex items-center justify-center z-40 pointer-events-none"
      style={{
        paddingTop: '10%', // Shift content slightly down to center better in table area
        paddingBottom: '30%'
      }}
    >
      <div className="flex flex-col items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            {getMessage()}
          </p>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Table row placeholder to maintain table structure */}
      <TableRow className="relative">
        <TableCell 
          ref={cellRef}
          colSpan={columnCount} 
          className="h-96 relative opacity-0"
        >
          {/* Hidden content to maintain table height */}
        </TableCell>
      </TableRow>
      
      {/* Render overlay using portal if table container is found */}
      {tableContainer && createPortal(emptyStateOverlay, tableContainer)}
    </>
  );
};
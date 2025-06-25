import React from 'react';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import TenderPageInput from "../TenderPageInput";

interface TendersPaginationProps {
  totalPages: number;
  currentPage: number;
  onPageChange: (page: number, isUserTriggered?: boolean) => void;
}

export const TendersPagination: React.FC<TendersPaginationProps> = ({
  totalPages,
  currentPage,
  onPageChange
}) => {
  const renderPaginationItems = () => {
    const items = [];

    if (totalPages <= 5) {
      for (let i = 1; i <= totalPages; i++) {
        items.push(
          <PaginationItem key={i}>
            <PaginationLink
              onClick={() => onPageChange(i, true)}
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
          onClick={() => onPageChange(1, true)}
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
              onPageJump={(page) => onPageChange(page, true)}
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
            onClick={() => onPageChange(i, true)}
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
              onPageJump={(page) => onPageChange(page, true)}
            />
          </div>
        </PaginationItem>
      );
    }

    if (totalPages > 1) {
      items.push(
        <PaginationItem key={totalPages}>
          <PaginationLink
            onClick={() => onPageChange(totalPages, true)}
            isActive={currentPage === totalPages}
          >
            {totalPages}
          </PaginationLink>
        </PaginationItem>
      );
    }

    return items;
  };

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="mt-4 flex justify-center">
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious 
              onClick={() => onPageChange(Math.max(currentPage - 1, 1), true)} 
            />
          </PaginationItem>
          {renderPaginationItems()}
          <PaginationItem>
            <PaginationNext 
              onClick={() => onPageChange(Math.min(currentPage + 1, totalPages), true)} 
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
};
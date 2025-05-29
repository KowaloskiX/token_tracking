'use client';

import { useState } from 'react';
import { Search, MoreHorizontal, Forward, Trash2 } from 'lucide-react';
import { SidebarMenuButton, SidebarMenuAction } from "@/components/ui/sidebar";
import { TenderAnalysis } from '@/types/tenders';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Portal } from "@radix-ui/react-portal";
import { DeletePopup } from '../popup/DeletePopup';
import Link from 'next/link';

interface Props {
  analysis: TenderAnalysis;
  onDelete: any;
  isDeleting?: boolean;
}

export function TenderAnalysisSidebarItem({ analysis, onDelete, isDeleting = false }: Props) {
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    isLoading: boolean;
  }>({ isOpen: false, isLoading: false });

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setDeleteDialog(prev => ({ ...prev, isLoading: true }));
    await onDelete(analysis._id);
    setDeleteDialog({ isOpen: false, isLoading: false });
  }

  return (
    <div className="group/analysis relative w-full">
      <Link href={`/dashboard/tenders/${analysis._id}`} passHref>
        <SidebarMenuButton asChild className="w-full">
          <div className="relative w-full flex items-center gap-2">
            <Search className="shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="block truncate">{analysis.name}</span>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuAction 
                  className="invisible absolute right-1 top-1/2 -translate-y-1/2 group-hover/analysis:visible shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4" />
                  <span className="sr-only">More</span>
                </SidebarMenuAction>
              </DropdownMenuTrigger>
              <Portal>
                <DropdownMenuContent
                  className="w-48 rounded-lg"
                  side="right"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuItem onClick={(e) => e.stopPropagation()}>
                    <Forward className="mr-2 text-muted-foreground" />
                    <span>Share Analysis</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteDialog(prev => ({ ...prev, isOpen: true }));
                    }}
                    className="text-destructive focus:text-destructive"
                    disabled={isDeleting || deleteDialog.isLoading}
                  >
                    <Trash2 className="mr-2" />
                    <span>
                      {isDeleting || deleteDialog.isLoading ? 'Deleting...' : 'Delete Analysis'}
                    </span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </Portal>
            </DropdownMenu>
          </div>
        </SidebarMenuButton>
      </Link>
      
      <DeletePopup 
        isOpen={deleteDialog.isOpen}
        onOpenChange={(open) => 
          setDeleteDialog(prev => ({ ...prev, isOpen: open }))
        }
        onConfirm={handleDelete}
        title="Usuń wyszukiwarkę"
        description="Czy jesteś pewien? Ta akcja jest nieodwracalna."
        isLoading={deleteDialog.isLoading}
      />
    </div>
  );
}
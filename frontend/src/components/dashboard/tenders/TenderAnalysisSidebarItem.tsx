'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Search, MoreHorizontal, Trash2, UserPlus, Share2, X } from 'lucide-react';
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
import { useDashboard } from '@/hooks/useDashboard';
import { AssignUsersModal } from './AssignUsersModal';
import { useTender } from '@/context/TenderContext';
import { useDashboardTranslations, useTendersTranslations } from "@/hooks/useTranslations";

interface Props {
  analysis: TenderAnalysis;
  onDelete: any;
  isDeleting?: boolean;
}

// Comprehensive cleanup function
const forceCleanupModals = () => {
  // Remove body scroll lock
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';
  document.body.classList.remove('modal-open');
  document.documentElement.classList.remove('modal-open');
  
  // Remove all radix portal overlays
  const portals = document.querySelectorAll('[data-radix-portal]');
  portals.forEach(portal => {
    // Check if portal is actually closed or empty
    if (!portal.hasChildNodes() || 
        portal.getAttribute('data-state') === 'closed' ||
        portal.querySelector('[data-state="closed"]')) {
      portal.remove();
    }
  });
  
  // Remove any lingering overlay elements
  const overlays = document.querySelectorAll('[data-radix-dialog-overlay], [data-radix-popover-content]');
  overlays.forEach(overlay => {
    if (overlay.getAttribute('data-state') === 'closed') {
      overlay.remove();
    }
  });
  
  // Re-enable pointer events on body (in case they were disabled)
  document.body.style.pointerEvents = '';
  
  // Force a reflow to ensure changes take effect
  void document.body.offsetHeight;
};

export function TenderAnalysisSidebarItem({ analysis, onDelete, isDeleting = false }: Props) {
  const { user } = useDashboard();
  const { assignUsers } = useTender();
  const t = useTendersTranslations();
  const tDashboard = useDashboardTranslations();
  
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    isLoading: boolean;
  }>({ isOpen: false, isLoading: false });
  const [assignUsersOpen, setAssignUsersOpen] = useState(false);
  const [isSharing, setIsSharing] = useState(false);
  const [orgMembers, setOrgMembers] = useState<any[]>([]);
  const [currentAssignedUsers, setCurrentAssignedUsers] = useState<string[]>([]);

  // Only allow admins or the analysis owner to manage users
  const canManageUsers = user?.role === 'admin' || user?._id === analysis.user_id;
  
  // Check if analysis is currently shared with organization (has any assigned users beyond owner)
  const isSharedWithOrg = currentAssignedUsers.some(userId => userId !== analysis.user_id);

  // Enhanced modal close handler with comprehensive cleanup
  const handleAssignUsersModalChange = useCallback((open: boolean) => {
    if (!open) {
      setAssignUsersOpen(false);
      
      // Use multiple cleanup attempts with different delays
      setTimeout(forceCleanupModals, 0);
      setTimeout(forceCleanupModals, 100);
      setTimeout(forceCleanupModals, 300);
    } else {
      setAssignUsersOpen(open);
    }
  }, []);

  // Cleanup effect that runs when the modal state changes
  useEffect(() => {
    if (!assignUsersOpen) {
      // Cleanup immediately and with delays
      forceCleanupModals();
      
      const timeouts = [
        setTimeout(forceCleanupModals, 50),
        setTimeout(forceCleanupModals, 150),
        setTimeout(forceCleanupModals, 500)
      ];
      
      return () => {
        timeouts.forEach(clearTimeout);
      };
    }
  }, [assignUsersOpen]);

  // Global cleanup on component unmount
  useEffect(() => {
    return () => {
      forceCleanupModals();
    };
  }, []);

  async function fetchOrgMembers() {
    if (!user?.org_id) return;
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setOrgMembers(data.members || []);
      }
    } catch (error) {
      console.error('Error fetching org members:', error);
    }
  }

  // Fetch org members when component mounts
  React.useEffect(() => {
    fetchOrgMembers();
  }, [user?.org_id]);

  // Initialize and sync assigned users state
  React.useEffect(() => {
    const assignedUsers = Array.isArray(analysis.assigned_users) ? analysis.assigned_users : [];
    setCurrentAssignedUsers(assignedUsers);
  }, [analysis.assigned_users]);

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setDeleteDialog(prev => ({ ...prev, isLoading: true }));
    await onDelete(analysis._id);
    setDeleteDialog({ isOpen: false, isLoading: false });
  }

  async function handleShareWithOrganization(e: React.MouseEvent) {
    e.stopPropagation();
    if (!analysis._id) return;

    // compute newAssignedUsers exactly as before…
    const orgMemberIds = orgMembers.map(m => m.id);
    const newAssignedUsers = isSharedWithOrg
      ? currentAssignedUsers.filter(u => !orgMemberIds.includes(u) || u === analysis.user_id)
      : Array.from(new Set([...currentAssignedUsers, ...orgMemberIds]));

    try {
      setIsSharing(true);
      // update via context — this will refresh all badges
      await assignUsers(analysis._id, newAssignedUsers);

      // local mirror for sidebar state
      setCurrentAssignedUsers(newAssignedUsers);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSharing(false);
    }
  }

  const getDeleteTitle = () => t('tenders.sidebar.deleteSearch');
  const getDeleteDescription = () => tDashboard('projects.delete_project_confirm');

  return (
    <div className="group/analysis relative w-full">
      {/* Main clickable link area */}
      <Link href={`/dashboard/tenders/${analysis._id}`} passHref>
        <SidebarMenuButton asChild className="w-full">
          <div className="relative w-full flex items-center gap-2 overflow-hidden pr-8">
            <Search className="shrink-0" />
            <div className="flex-1 min-w-0 overflow-hidden">
              <span className="block truncate max-w-36">{analysis.name}</span>
            </div>
          </div>
        </SidebarMenuButton>
      </Link>
      
      {/* Dropdown menu positioned absolutely outside the Link */}
      {canManageUsers && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuAction 
              className="absolute right-1 top-1/2 -translate-y-1/2 shrink-0 opacity-0 group-hover/analysis:opacity-100 transition-opacity duration-200 z-10"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">More</span>
            </SidebarMenuAction>
          </DropdownMenuTrigger>
          <Portal>
            <DropdownMenuContent
              className="w-56 rounded-lg"
              side="right"
              align="start"
              sideOffset={4}
            >
              <DropdownMenuItem
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setAssignUsersOpen(true);
                }}
              >
                <UserPlus className="mr-2 text-muted-foreground" />
                <span>{t('tenders.sidebar.assignUsers')}</span>
              </DropdownMenuItem>
              
              <DropdownMenuItem 
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleShareWithOrganization(e);
                }}
                disabled={isSharing}
              >
                {isSharedWithOrg ? (
                  <X className="mr-2 text-muted-foreground" />
                ) : (
                  <Share2 className="mr-2 text-muted-foreground" />
                )}
                <span>
                  {isSharing 
                    ? (isSharedWithOrg ? t('tenders.sidebar.cancellingShare') : t('tenders.sidebar.sharing'))
                    : (isSharedWithOrg ? t('tenders.sidebar.stopSharing') : t('tenders.sidebar.shareInOrganization'))
                  }
                </span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDeleteDialog(prev => ({ ...prev, isOpen: true }));
                }}
                className="text-destructive focus:text-destructive"
                disabled={isDeleting || deleteDialog.isLoading}
              >
                <Trash2 className="mr-2" />
                <span>
                  {isDeleting || deleteDialog.isLoading ? t('tenders.sidebar.deleting') : getDeleteTitle()}
                </span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </Portal>
        </DropdownMenu>
      )}
      
      <DeletePopup 
        isOpen={deleteDialog.isOpen}
        onOpenChange={(open) => 
          setDeleteDialog(prev => ({ ...prev, isOpen: open }))
        }
        onConfirm={handleDelete}
        title={getDeleteTitle()}
        description={getDeleteDescription()}
        isLoading={deleteDialog.isLoading}
      />
      
      {/* Modal with enhanced cleanup */}
      <AssignUsersModal
        analysis={{ ...analysis, assigned_users: currentAssignedUsers }}
        open={assignUsersOpen}
        onOpenChange={handleAssignUsersModalChange}
      />

    </div>
  );
}
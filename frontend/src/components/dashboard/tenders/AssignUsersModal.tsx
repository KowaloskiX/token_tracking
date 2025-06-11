'use client';

import { useState, useEffect, useCallback } from 'react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogFooter 
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { TenderAnalysis } from "@/types/tenders";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Check, Shield, Info, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useTender } from '@/context/TenderContext';
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

type OrgMember = {
  id: string;
  name: string;
  email: string;
  role: string;
  isCurrentUser: boolean;
};

interface AssignUsersModalProps {
  analysis: TenderAnalysis;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Enhanced cleanup function specifically for dialog modals
const forceCleanupDialog = () => {
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';
  document.body.classList.remove('modal-open');
  document.documentElement.classList.remove('modal-open');
  document.body.style.pointerEvents = '';
  const dialogOverlays = document.querySelectorAll('[data-radix-dialog-overlay]');
  dialogOverlays.forEach(overlay => {
    const state = overlay.getAttribute('data-state');
    if (state === 'closed' || !overlay.parentElement) overlay.remove();
  });
  const portals = document.querySelectorAll('[data-radix-portal]');
  portals.forEach(portal => {
    if (!portal.hasChildNodes() || portal.children.length === 0) portal.remove();
  });
  void document.body.offsetHeight;
};

export const AssignUsersModal = ({ analysis, open, onOpenChange }: AssignUsersModalProps) => {
  const { assignUsers } = useTender();
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();
  
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = useCallback((newOpen: boolean) => {
    if (!newOpen) {
      setError(null);
      setIsSaving(false);
      onOpenChange(false);
      setTimeout(forceCleanupDialog, 0);
      setTimeout(forceCleanupDialog, 50);
      setTimeout(forceCleanupDialog, 150);
      setTimeout(forceCleanupDialog, 300);
    } else {
      onOpenChange(newOpen);
    }
  }, [onOpenChange]);

  useEffect(() => {
    if (open) {
      fetchOrgMembers();
      const initialUsers = Array.isArray(analysis.assigned_users) ? analysis.assigned_users : [];
      setSelectedUsers(initialUsers);
    } else {
      setError(null);
      setIsLoading(false);
      setIsSaving(false);
      setTimeout(forceCleanupDialog, 0);
    }
  }, [open, analysis]);

  useEffect(() => {
    if (!open) {
      const cleanupTimeouts = [
        setTimeout(forceCleanupDialog, 0),
        setTimeout(forceCleanupDialog, 100),
        setTimeout(forceCleanupDialog, 250),
        setTimeout(forceCleanupDialog, 500)
      ];
      return () => cleanupTimeouts.forEach(clearTimeout);
    }
  }, [open]);

  useEffect(() => () => { forceCleanupDialog(); }, []);

  const fetchOrgMembers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } }
      );
      if (!response.ok) throw new Error(`Failed to fetch organization members: ${response.status}`);
      const data = await response.json();
      setOrgMembers(data.members || []);
    } catch (err) {
      console.error('Error fetching org members:', err);
      setError(t('tenders.edit.assignUsers.fetchError'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleUserToggle = (userId: string) => {
    setSelectedUsers(prev => prev.includes(userId)
      ? prev.filter(id => id !== userId)
      : [...prev, userId]
    );
  };

  const handleSave = async () => {
    if (!analysis._id) {
      setError(t('tenders.edit.assignUsers.noIdError'));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await assignUsers(analysis._id, selectedUsers);
      handleClose(false);
    } catch (err) {
      console.error('Error assigning users:', err);
      setError(t('tenders.edit.assignUsers.saveError'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => handleClose(false);

  return (
    <Dialog open={open} onOpenChange={handleClose} modal>
      <DialogContent
        className="sm:max-w-md"
        onPointerDownOutside={() => handleClose(false)}
        onEscapeKeyDown={() => handleClose(false)}
        onAnimationEnd={() => !open && setTimeout(forceCleanupDialog, 0)}
      >
        <DialogHeader>
          <DialogTitle>{t('tenders.edit.assignUsers')}</DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <h3 className="text-sm font-medium mb-2">
            {t('tenders.sidebar.search')}: {analysis.name}
          </h3>
          {isLoading ? (
            <div className="flex justify-center items-center h-32">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="text-destructive text-sm p-2">{error}</div>
          ) : orgMembers.length === 0 ? (
            <div className="text-muted-foreground text-sm p-2">
              {t('tenders.edit.noUsers')}
            </div>
          ) : (
            <>
              <div className="mb-4 border border-border bg-muted/50 p-3 rounded-md flex items-start gap-2">
                <Info className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                <div className="text-xs text-muted-foreground">
                  {t('tenders.edit.assignInfo')}
                </div>
              </div>
              <ScrollArea className="max-h-[300px] pr-4 pb-4 overflow-y-auto">
                <div className="space-y-4">
                  {orgMembers.map(member => {
                    const isAssigned = selectedUsers.includes(member.id);
                    const isOwner = member.id === analysis.user_id;
                    return (
                      <div
                        key={member.id}
                        className={`flex items-center space-x-2 py-2 px-1 rounded-md transition-colors ${isAssigned ? 'bg-secondary/70' : 'hover:bg-secondary/30'}`}
                      >                        
                        <Checkbox
                          id={`user-${member.id}`}
                          checked={isAssigned || isOwner}
                          onCheckedChange={() => !isOwner && handleUserToggle(member.id)}
                          disabled={isOwner}
                          className={isOwner ? 'opacity-50' : ''}
                        />
                        <Label htmlFor={`user-${member.id}`} className="flex-1 cursor-pointer flex items-center gap-2">
                          <div className="flex flex-col">
                            <div className="flex items-center">
                              <span className="font-medium">{member.name || member.email.split('@')[0]}</span>
                              {member.isCurrentUser && <Badge variant="outline" className="ml-2 text-xs">{commonT('user')}</Badge>}
                              {member.role === 'admin' && <Badge variant="secondary" className="ml-2 text-xs"><Shield className="h-3 w-3 mr-1"/>Admin</Badge>}
                              {isOwner && (
                                <TooltipProvider>
                                  <Tooltip>
                                    <TooltipTrigger>
                                      <Badge variant="default" className="ml-2 text-xs">
                                        <User className="h-3 w-3 mr-1" />
                                        {t('tenders.edit.ownerBadge')}
                                      </Badge>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      <p className="text-xs">{t('tenders.edit.ownerAlwaysAccess')}</p>
                                    </TooltipContent>
                                  </Tooltip>
                                </TooltipProvider>
                              )}
                            </div>
                            <div className="text-xs text-muted-foreground">{member.email}</div>
                          </div>
                        </Label>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            {commonT('cancel')}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isLoading || isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            {commonT('save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Check, Shield, Info, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useKanban } from "@/context/KanbanContext";
import { KanbanBoard } from "@/types/kanban";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

/**
 * Organisation member as returned by GET /organizations/members
 */
interface OrgMember {
  id: string;
  name: string;
  email: string;
  role: string;
  isCurrentUser: boolean;
}

interface AssignUsersBoardModalProps {
  board: KanbanBoard;
  open: boolean;
  initialSelectedUsers: string[]
  onOpenChange: (open: boolean) => void;
}

/**
 * Force‑remove any Radix dialog overlays/portals that linger when we
 * programmatically close the modal before Radix' transition ends.
 */
const forceCleanupDialog = () => {
  document.body.style.overflow = "";
  document.body.style.paddingRight = "";
  document.body.classList.remove("modal-open");
  document.documentElement.classList.remove("modal-open");
  document.body.style.pointerEvents = "";

  document
    .querySelectorAll("[data-radix-dialog-overlay]")
    .forEach((overlay) => {
      if (
        overlay.getAttribute("data-state") === "closed" ||
        !overlay.parentElement
      ) {
        overlay.remove();
      }
    });

  document.querySelectorAll("[data-radix-portal]").forEach((portal) => {
    if (!portal.hasChildNodes()) portal.remove();
  });

  void document.body.offsetHeight;
};

export const AssignUsersToBoardModal = ({
  board,
  open,
  initialSelectedUsers,
  onOpenChange,
}: AssignUsersBoardModalProps) => {
  const { updateBoardAction } = useKanban();
  const { assignUsersToBoard } = useKanban();
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  /**
   * Close / open handler that also clears transient state and
   * cleans up leftover Radix portals when closing.
   */
  const handleClose = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        setError(null);
        setIsSaving(false);
        onOpenChange(false);

        [0, 50, 150, 300].forEach((ms) =>
          setTimeout(forceCleanupDialog, ms)
        );
      } else {
        onOpenChange(true);
      }
    },
    [onOpenChange]
  );

  useEffect(() => {
    if (!open) return;

    setSelectedUsers(
      Array.isArray(initialSelectedUsers)
        ? [...initialSelectedUsers]
        : []
    );

    setError(null);
    setIsLoading(true);

    (async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }
        );
        if (!res.ok) throw new Error(`Status ${res.status}`);
        const json = await res.json();
        setOrgMembers(json.members || []);
      } catch (err) {
        console.error("Error fetching org members:", err);
        setError(t('tenders.board.failedUpdateAssignments'));
      } finally {
        setIsLoading(false);
      }
    })();
  }, [open, initialSelectedUsers, t]);

  /**
   * When the modal opens we:
   *   1. seed `selectedUsers` from board.assigned_users
   *   2. fetch the organisation members list
   */
  useEffect(() => {
    if (!open) return;

    setSelectedUsers(
       Array.isArray(board.assigned_users)
    ? board.assigned_users.map(String)
    : []
    );

    setIsLoading(true);

    (async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (!res.ok) throw new Error(`Status ${res.status}`);

        const json = await res.json();
        setOrgMembers(json.members || []);
      } catch (err) {
        console.error("Error fetching org members:", err);
        setError(t('tenders.board.failedUpdateAssignments'));
      } finally {
        setIsLoading(false);
      }
    })();
  }, [open, board.assigned_users, t]);

  /**
   * Toggle a single user in/out of `selectedUsers`.
   */
  const handleUserToggle = (userId: string, checked: boolean) => {
    setSelectedUsers((prev) =>
      checked ? (prev.includes(userId) ? prev : [...prev, userId]) : prev.filter((id) => id !== userId)
    );
  };

  /**
   * Persist the current `selectedUsers` to the backend.
   */
  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await assignUsersToBoard(board.id, selectedUsers);
      handleClose(false);
    } catch (err) {
      setError(t('tenders.board.failedUpdateAssignments'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose} modal>
      <DialogContent
        className="sm:max-w-md"
        onPointerDownOutside={() => handleClose(false)}
        onEscapeKeyDown={() => handleClose(false)}
        onAnimationEnd={() => !open && forceCleanupDialog()}
      >
        <DialogHeader>
          <DialogTitle>{t('tenders.board.assignUsersToBoard')}</DialogTitle>
        </DialogHeader>

        <div className="py-4">
          <h3 className="text-sm font-medium mb-2">{t('tenders.kanban.board')}: {board.name}</h3>

          {isLoading ? (
            <div className="flex justify-center items-center h-32">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="text-destructive text-sm p-2">{error}</div>
          ) : orgMembers.length === 0 ? (
            <div className="text-muted-foreground text-sm p-2">
              {t('tenders.board.noUsersAvailable')}
            </div>
          ) : (
            <>
              <div className="mb-4 border border-border bg-muted/50 p-3 rounded-md flex items-start gap-2">
                <Info className="h-5 w-5 text-muted-foreground mt-0.5" />
                <p className="text-xs text-muted-foreground">
                  {t('tenders.board.assignInfo')}
                </p>
              </div>

              <ScrollArea className="max-h-[300px] pr-4 pb-4 overflow-y-auto">
                <div className="space-y-4">
                  {orgMembers.map((member) => {
                    const isOwner = member.id === board.user_id;
                    const isChecked = isOwner || selectedUsers.includes(String(member.id));

                    return (
                      <div
                        key={member.id}
                        className={`flex items-center space-x-2 py-2 px-1 rounded-md transition-colors ${
                          isChecked ? "bg-secondary/70" : "hover:bg-secondary/30"
                        }`}
                      >
                        <Checkbox
                          id={`user-${member.id}`}
                          checked={isChecked}
                          disabled={isOwner}
                          onCheckedChange={(checked: boolean) =>
                            !isOwner && handleUserToggle(member.id, checked as boolean)
                          }
                          className={isOwner ? "opacity-50" : ""}
                        />

                        <Label
                          htmlFor={`user-${member.id}`}
                          className="flex-1 cursor-pointer flex items-center gap-2"
                        >
                          <div className="flex flex-col">
                            <div className="flex items-center">
                              <span className="font-medium">
                                {member.name || member.email.split("@")[0]}
                              </span>

                              {member.isCurrentUser && (
                                <Badge variant="outline" className="ml-2 text-xs">
                                  {t('tenders.board.you')}
                                </Badge>
                              )}

                              {member.role === "admin" && (
                                <Badge variant="secondary" className="ml-2 text-xs">
                                  <Shield className="h-3 w-3 mr-1" />
                                  {t('tenders.board.admin')}
                                </Badge>
                              )}

                              {isOwner && (
                                <TooltipProvider>
                                  <Tooltip>
                                    <TooltipTrigger>
                                      <Badge variant="default" className="ml-2 text-xs">
                                        <User className="h-3 w-3 mr-1" />
                                        {t('tenders.board.owner')}
                                      </Badge>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      <p className="text-xs">
                                        {t('tenders.board.ownerAlwaysHasAccess')}
                                      </p>
                                    </TooltipContent>
                                  </Tooltip>
                                </TooltipProvider>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {member.email}
                            </span>
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
          <Button variant="outline" onClick={() => handleClose(false)}>
            {tCommon('cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isLoading || isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            {tCommon('save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
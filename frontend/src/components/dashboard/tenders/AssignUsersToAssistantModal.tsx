"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
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
import { useDashboard } from "@/hooks/useDashboard";
import { Assistant } from "@/types";

interface OrgMember {
  id: string;
  name: string;
  email: string;
  role: string;
  isCurrentUser: boolean;
}

interface AssignUsersAssistantModalProps {
  assistant: Assistant;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAssignmentsChange?: (newUserIds: string[]) => void;
}

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

  // trigger re‑flow so the browser actually removes the nodes
  void document.body.offsetHeight;
};

export default function AssignUsersToAssistantModal({
  assistant,
  open,
  onOpenChange,
  onAssignmentsChange,
}: AssignUsersAssistantModalProps) {
  const { assignUsersToAssistant } = useDashboard();
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasChanges = useMemo(() => {
    const original = Array.isArray(assistant.assigned_users)
      ? assistant.assigned_users.map(String)
      : [];
    if (original.length !== selectedUsers.length) return true;
    return !selectedUsers.every((id) => original.includes(id));
  }, [assistant.assigned_users, selectedUsers]);

  // single effect: reset state and fetch members when opened
  useEffect(() => {
    if (!open) return;

    setError(null);
    setIsSaving(false);

    // seed current selections
    setSelectedUsers(
      Array.isArray(assistant.assigned_users)
        ? assistant.assigned_users.map(String)
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
        console.error(err);
        setError("Failed to load organization members.");
      } finally {
        setIsLoading(false);
      }
    })();
  }, [open, assistant.assigned_users]);

  const handleClose = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        // reset selected only; keep cached members if needed
        setSelectedUsers([]);
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

  const handleToggle = (id: string, checked: boolean) => {
    setSelectedUsers((prev) =>
      checked
        ? prev.includes(id)
          ? prev
          : [...prev, id]
        : prev.filter((x) => x !== id)
    );
  };

  const handleSave = async () => {
    if (!hasChanges) {
      handleClose(false);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
    const updated = await assignUsersToAssistant(assistant._id!, selectedUsers);
    onAssignmentsChange?.(updated.assigned_users ?? []);
      handleClose(false);
    } catch {
      setError("Error saving assignments.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose} modal>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Przypisz użytkowników do projektu</DialogTitle>
        </DialogHeader>

        <div className="py-4">
          <h3 className="text-sm font-medium mb-2">Projekt: {assistant.name}</h3>

          {isLoading ? (
            <div className="flex justify-center h-32 items-center">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-destructive p-2">{error}</div>
          ) : orgMembers.length === 0 ? (
            <div className="text-muted-foreground p-2">
              Brak użytkowników w organizacji.
            </div>
          ) : (
            <>
              <div className="mb-4 border border-border bg-muted/50 p-3 rounded-md flex items-start gap-2">
                <Info className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                <div className="text-xs text-muted-foreground">
                  Użytkownicy zaznaczeni poniżej będą mieli dostęp do tej analizy i jej wyników. Posiadacz analizy zawsze ma dostęp.
                </div>
              </div>

              <ScrollArea className="max-h-[300px] pr-4 pb-4 overflow-y-auto">
                <div className="space-y-4">
                  {orgMembers.map((m) => {
                    const isOwner = m.id === assistant.owner_id;
                    const checked = isOwner || selectedUsers.includes(m.id);
                    return (
                      <div
                        key={m.id}
                        className={`flex items-center space-x-2 py-2 px-1 rounded-md ${
                          checked ? "bg-secondary/70" : "hover:bg-secondary/30"
                        }`}
                      >
                        <Checkbox
                          id={`usr-${m.id}`}
                          checked={checked}
                          disabled={isOwner}
                          onCheckedChange={(c) =>
                            !isOwner && handleToggle(m.id, c as boolean)
                          }
                          className={isOwner ? "opacity-50" : ""}
                        />
                        <Label
                          htmlFor={`usr-${m.id}`}
                          className="flex-1 cursor-pointer flex items-center gap-2"
                        >
                          <div className="flex flex-col">
                            <div className="flex items-center">
                              <span className="font-medium">
                                {m.name || m.email.split("@")[0]}
                              </span>
                              {m.isCurrentUser && (
                                <Badge variant="outline" className="ml-2 text-xs">
                                  Ty
                                </Badge>
                              )}
                              {m.role === "admin" && (
                                <Badge variant="secondary" className="ml-2 text-xs">
                                  <Shield className="h-3 w-3 mr-1" />
                                  Admin
                                </Badge>
                              )}
                              {isOwner && (
                                <Badge variant="default" className="ml-2 text-xs">
                                  <User className="h-3 w-3 mr-1" />
                                  Właściciel
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {m.email}
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
            Anuluj
          </Button>
          <Button onClick={handleSave} disabled={isLoading || isSaving || !hasChanges}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            Zapisz
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

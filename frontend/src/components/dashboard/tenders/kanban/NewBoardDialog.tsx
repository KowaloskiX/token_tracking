"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useKanban } from "@/context/KanbanContext";
import { useDashboard } from "@/hooks/useDashboard";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface NewBoardDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onBoardCreated?: (boardId: string) => void;
}

export function NewBoardDialog({ open, onOpenChange, onBoardCreated }: NewBoardDialogProps) {
  const { user } = useDashboard();
  const { createBoardAction } = useKanban();
  const [name, setName] = useState("");
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  const handleCreateBoard = async () => {
    if (!name.trim() || !user?._id) return;

    try {
      const newBoard = await createBoardAction({
        name,
        user_id: user._id,
        org_id: user?.org_id || null,
        shared_with: [],
      });
      
      onOpenChange(false);
      setName("");
      onBoardCreated?.(newBoard.id);
    } catch (err) {
      console.error("Error creating board:", err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('tenders.board.newBoard')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="boardName">{t('tenders.board.boardName')}</Label>
          <Input
            id="boardName"
            value={name}
            placeholder={t('tenders.board.newBoard')}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateBoard()}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {tCommon('cancel')}
          </Button>
          <Button onClick={handleCreateBoard}>{t('tenders.board.createBoard')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
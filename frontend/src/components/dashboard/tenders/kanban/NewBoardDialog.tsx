"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useKanban } from "@/context/KanbanContext";
import { useDashboard } from "@/hooks/useDashboard";

interface NewBoardDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onBoardCreated?: (boardId: string) => void;
}

export function NewBoardDialog({ open, onOpenChange, onBoardCreated }: NewBoardDialogProps) {
  const { user } = useDashboard();
  const { createBoardAction } = useKanban();
  const [name, setName] = useState("");

  const handleCreateBoard = async () => {
    if (!name.trim() || !user?._id) return;

    try {
      const newBoard = await createBoardAction({
        name,
        user_id: user._id,
        org_id: user?.org_id || null, // Include organization ID for board sharing
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
          <DialogTitle>Utwórz nową tablicę</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="boardName">Nazwa tablicy</Label>
          <Input
            id="boardName"
            value={name}
            placeholder="np. Nowa tablica"
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateBoard()}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Anuluj
          </Button>
          <Button onClick={handleCreateBoard}>Utwórz</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
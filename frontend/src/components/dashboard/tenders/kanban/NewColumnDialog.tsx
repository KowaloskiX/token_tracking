"use client";

import React from "react";
import { useKanban } from "@/context/KanbanContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { DEFAULT_COLUMN_COLOR } from "@/types/kanban";

interface NewColumnDialogProps {
  boardId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewColumnDialog({ boardId, open, onOpenChange }: NewColumnDialogProps) {
  const { createColumnAction, selectedBoard } = useKanban();
  const [name, setName] = React.useState("");
  const [isCreating, setIsCreating] = useState(false);

  const handleCreateColumn = async () => {
    if (!name.trim()) return;

    try {
      await createColumnAction(boardId, {
        name,
        order: selectedBoard?.columns?.length || 0,
        color: DEFAULT_COLUMN_COLOR,
      });
      onOpenChange(false);
      setName("");
    } catch (err) {
      console.error("Error creating column:", err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Utwórz nową kolumnę</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="columnName">Nazwa kolumny</Label>
          <Input
            id="columnName"
            placeholder="np. Do przejrzenia"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateColumn()}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Anuluj
          </Button>
          <Button onClick={handleCreateColumn} disabled={isCreating}>
            {isCreating ? "Tworzenie..." : "Utwórz"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useKanban } from "@/context/KanbanContext";
import { Trash, Loader2 } from "lucide-react";

interface DeleteBoardDialogProps {
  boardId: string;
  boardName: string; // Add this prop
  onDeleted: () => void; // Change from onDelete to onDeleted to match usage
  children?: React.ReactNode;
}

export function DeleteBoardDialog({ boardId, boardName, onDeleted, children }: DeleteBoardDialogProps) {
  const router = useRouter();
  const { deleteBoardAction } = useKanban();

  const [isDeleting, setIsDeleting] = useState(false);

  // Update to accept an event parameter
  const handleDelete = async (e: React.MouseEvent) => {
    // Stop event propagation to prevent card onClick from firing
    e.stopPropagation();
    
    try {
      setIsDeleting(true);
      await deleteBoardAction(boardId);
      onDeleted(); // Call the callback when deletion is successful
    } catch (error) {
      console.error("Failed to delete board:", error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        {children || (
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive/80 hover:text-destructive hover:bg-destructive/10"
          >
            <Trash className="h-4 w-4 mr-2" />
            <span className="hidden sm:inline">Usuń tablicę</span>
          </Button>
        )}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Czy jesteś pewien?</AlertDialogTitle>
          <AlertDialogDescription>
            Tej akcji nie można cofnąć. Spowoduje to trwałe usunięcie tablicy
            oraz wszystkich jej kolumn i elementów.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Anuluj</AlertDialogCancel>

          <AlertDialogAction
            disabled={isDeleting}
            onClick={handleDelete}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 flex justify-center items-center"
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Usuwanie...
              </>
            ) : (
              <>
                <Trash className="h-4 w-4 mr-2" />
                Potwierdź usunięcie
              </>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

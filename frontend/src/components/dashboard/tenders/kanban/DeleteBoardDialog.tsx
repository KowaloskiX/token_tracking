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
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface DeleteBoardDialogProps {
  boardId: string;
  boardName: string;
  onDeleted: () => void;
  children?: React.ReactNode;
}

export function DeleteBoardDialog({ boardId, boardName, onDeleted, children }: DeleteBoardDialogProps) {
  const router = useRouter();
  const { deleteBoardAction } = useKanban();
  const [isDeleting, setIsDeleting] = useState(false);
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      setIsDeleting(true);
      await deleteBoardAction(boardId);
      onDeleted();
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
            <span className="hidden sm:inline">{t('tenders.board.deleteBoard')}</span>
          </Button>
        )}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('tenders.board.deleteConfirm')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t('tenders.board.deleteWarning')}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>{tCommon('cancel')}</AlertDialogCancel>

          <AlertDialogAction
            disabled={isDeleting}
            onClick={handleDelete}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 flex justify-center items-center"
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {tCommon('deleting')}
              </>
            ) : (
              <>
                <Trash className="h-4 w-4 mr-2" />
                {t('tenders.board.confirmDelete')}
              </>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
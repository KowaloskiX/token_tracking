"use client"

import React, { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useTranslations } from 'next-intl';

interface DeletePopupProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (e: React.MouseEvent) => Promise<void> | void;
  title?: string;
  description?: string;
  isLoading?: boolean;
}

export function DeletePopup({
  isOpen,
  onOpenChange,
  onConfirm,
  title,
  description,
  isLoading: externalLoading = false
}: DeletePopupProps) {
  const [internalLoading, setInternalLoading] = useState(false);
  const isLoading = internalLoading || externalLoading;

  // Translation hooks
  const t = useTranslations('dashboard.chat');
  const tCommon = useTranslations('common');

  const handleConfirm = async (e: React.MouseEvent) => {
    try {
      setInternalLoading(true);
      await onConfirm(e);
    } finally {
      setInternalLoading(false);
    }
  };

  // Use provided title/description or fallback to translations
  const dialogTitle = title || t('delete_conversation');
  const dialogDescription = description || t('delete_conversation_confirm');

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => {
      if (!isLoading) {
        onOpenChange(open);
      }
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{dialogTitle}</AlertDialogTitle>
          <AlertDialogDescription>
            {dialogDescription}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel 
            onClick={(e) => e.stopPropagation()}
            disabled={isLoading}
          >
            {tCommon('cancel')}
          </AlertDialogCancel>
          <Button 
            onClick={handleConfirm}
            className="bg-destructive hover:bg-destructive/90 gap-2 bg-red-500"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {tCommon('deleting')}
              </>
            ) : (
              tCommon('delete')
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
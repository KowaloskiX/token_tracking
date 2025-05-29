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
  title = "Usuń konwersację",
  description = "Are you sure you want to delete this conversation? This action cannot be undone.",
  isLoading: externalLoading = false
}: DeletePopupProps) {
  const [internalLoading, setInternalLoading] = useState(false);
  const isLoading = internalLoading || externalLoading;

  const handleConfirm = async (e: React.MouseEvent) => {
    try {
      setInternalLoading(true);
      await onConfirm(e);
    } finally {
      setInternalLoading(false);
    }
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => {
      if (!isLoading) {
        onOpenChange(open);
      }
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel 
            onClick={(e) => e.stopPropagation()}
            disabled={isLoading}
          >
            Anuluj
          </AlertDialogCancel>
          <Button 
            onClick={handleConfirm}
            className="bg-destructive hover:bg-destructive/90 gap-2 bg-red-500"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Usuwanie...
              </>
            ) : (
              'Usuń'
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
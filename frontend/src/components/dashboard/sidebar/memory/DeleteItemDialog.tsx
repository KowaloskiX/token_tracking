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

interface DeleteItemDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (e?: React.MouseEvent) => Promise<void> | void;
  itemName: string;
  itemType: string;
}

export const DeleteItemDialog: React.FC<DeleteItemDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  itemName,
  itemType
}) => {
  const t = useTranslations('dashboard.memory');
  const tCommon = useTranslations('common');
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async (e?: React.MouseEvent) => {
    try {
      setIsLoading(true);
      await onConfirm(e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => {
      if (!isLoading && !open) {
        onClose();
      }
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{tCommon('delete')} {itemType}</AlertDialogTitle>
          <AlertDialogDescription>
            {itemType === 'folder' ? t('delete_folder_confirm') : t('delete_file_confirm')}
            &quot;{itemName}&quot;?
            {itemType === 'folder' && (
              <span className="block text-black mt-4">
                {t('delete_folder_warning')}
              </span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel 
            onClick={(e) => e?.stopPropagation()}
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
};
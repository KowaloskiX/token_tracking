"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTender } from "@/context/TenderContext";
import { useKanban } from "@/context/KanbanContext";
import { TenderAnalysisResult } from "@/types/tenders";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { KanbanTenderItem } from "@/types/kanban";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

interface NewItemDialogProps {
  boardId: string;
  columnId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingTenderItems: KanbanTenderItem[];
}

export function NewItemDialog({
  boardId,
  columnId,
  open,
  onOpenChange,
  existingTenderItems,
}: NewItemDialogProps) {
  const router = useRouter();
  const { activeTenders, fetchAllActiveTenders } = useTender();
  const { createTenderItemAction } = useKanban();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTender, setSelectedTender] = useState<TenderAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [popupOpen, setPopupOpen] = useState(false);
  const [popupMessage, setPopupMessage] = useState("");
  
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  useEffect(() => {
    if (open) {
      setLoading(true);
      fetchAllActiveTenders()
        .catch((error) => console.error("Error fetching tenders:", error))
        .finally(() => setLoading(false));
    }
  }, [open, fetchAllActiveTenders]);

  const filteredTenders = activeTenders.filter(
    (tender) =>
      !existingTenderItems.some(
        (item) => item.tender_analysis_result_id === tender._id
      ) &&
      tender.tender_metadata?.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateItem = async () => {
    if (!selectedTender) return;
    try {
      await createTenderItemAction(boardId, columnId, {
        board_id: boardId,
        column_id: columnId,
        tender_analysis_result_id: selectedTender._id!,
        name: selectedTender.tender_metadata?.name,
        order: 0,
      });
      setPopupMessage(t('tenders.board.tenderSuccessfullyAdded'));
      setPopupOpen(true);
    } catch (err) {
      console.error("Error creating item:", err);
      setPopupMessage(t('tenders.board.errorAddingTender'));
      setPopupOpen(true);
    }
  };

  const handlePopupClose = () => {
    setPopupOpen(false);
    onOpenChange(false);
    router.push("/dashboard/tenders/management");
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('tenders.board.selectActiveTender')}</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            <Input
              placeholder={t('tenders.board.searchTender')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            {loading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <ScrollArea className="h-64">
                {filteredTenders.length === 0 ? (
                  <div className="text-center py-4 text-muted-foreground">
                    {t('tenders.board.noActiveTenders')}
                  </div>
                ) : (
                  filteredTenders.map((tender) => (
                    <div
                      key={tender._id}
                      className="p-2 hover:bg-secondary cursor-pointer rounded-md"
                      onClick={() => setSelectedTender(tender)}
                    >
                      <div
                        className={cn(
                          "p-2 border rounded-md",
                          selectedTender?._id === tender._id && "border-primary"
                        )}
                      >
                        <h3 className="font-medium">
                          {tender.tender_metadata?.name || t('tenders.board.unnamedTender')}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {tender.tender_metadata?.organization}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </ScrollArea>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {tCommon('cancel')}
            </Button>
            <Button onClick={handleCreateItem} disabled={!selectedTender}>
              {t('tenders.board.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={popupOpen} onOpenChange={setPopupOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{popupMessage}</DialogTitle>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={handlePopupClose}>{t('tenders.board.goToBoards')}</Button>
            <Button onClick={() => setPopupOpen(false)}>{t('tenders.board.close')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
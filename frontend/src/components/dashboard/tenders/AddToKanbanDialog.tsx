"use client";

import { useState } from "react";
import { useKanban } from "@/context/KanbanContext";
import { useDashboard } from "@/hooks/useDashboard";
import { TenderAnalysisResult } from "@/types/tenders";
import { DEFAULT_COLUMN_COLOR, KanbanTenderItem } from "@/types/kanban";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, ArrowRight } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface AddToKanbanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tender: TenderAnalysisResult;
  onAddSuccess?: (boardId: string) => void;
  onAddError?: (error: unknown) => void;
}

export function AddToKanbanDialog({
  open,
  onOpenChange,
  tender,
  onAddSuccess,
  onAddError
}: AddToKanbanDialogProps) {
  const { user } = useDashboard();
  const { 
    boards, 
    createBoardAction, 
    createColumnAction,
    createTenderItemAction 
  } = useKanban();

  // Step tracking (1: board selection, 2: column selection)
  const [currentStep, setCurrentStep] = useState(1);
  
  // Board state
  const [selectedBoardId, setSelectedBoardId] = useState<string>("");
  const [boardSelectionType, setBoardSelectionType] = useState<"existing" | "new">(
    boards.length > 0 ? "existing" : "new"
  );
  const [newBoardName, setNewBoardName] = useState<string>("");
  
  // Column state
  const [selectedColumnId, setSelectedColumnId] = useState<string>("");
  const [columnSelectionType, setColumnSelectionType] = useState<"existing" | "new">("existing");
  const [newColumnName, setNewColumnName] = useState<string>("");

  // Get columns for the selected board
  const selectedBoardColumns = boards.find(b => b.id === selectedBoardId)?.columns || [];
  
  // Reset dependent state when board changes
  const handleBoardChange = (boardId: string) => {
    setSelectedBoardId(boardId);
    setSelectedColumnId("");
    setColumnSelectionType(
      selectedBoardColumns.length > 0 ? "existing" : "new"
    );
  };

  const handleCreateBoard = async () => {
    if (!user?._id || !newBoardName.trim()) return;

    try {
      const newBoard = await createBoardAction({
        name: newBoardName,
        user_id: user._id,
        shared_with: []
      });
      
      setSelectedBoardId(newBoard.id);
      setNewBoardName("");
      setColumnSelectionType("new"); // New board won't have columns
      setCurrentStep(2); // Move to column selection
    } catch (error) {
      console.error("Error creating board:", error);
    }
  };

  const handleCreateColumn = async () => {
    if (!selectedBoardId || !newColumnName.trim()) return;

    try {
      const selectedBoard = boards.find(b => b.id === selectedBoardId);
      const order = selectedBoard?.columns?.length || 0;

      const newColumn = await createColumnAction(selectedBoardId, {
        name: newColumnName,
        order,
        color: DEFAULT_COLUMN_COLOR
      });

      setSelectedColumnId(newColumn.id);
      setNewColumnName("");
      return newColumn.id;
    } catch (error) {
      console.error("Error creating column:", error);
      throw error;
    }
  };

  const handleAddToKanban = async () => {
    if (!selectedBoardId || !selectedColumnId || !tender) return;

    try {
      const selectedColumn = boards
        .find(b => b.id === selectedBoardId)
        ?.columns.find(c => c.id === selectedColumnId);

      const order = selectedColumn?.tenderItems?.length || 0;

      await createTenderItemAction(
        selectedBoardId,
        selectedColumnId,
        {
          board_id: selectedBoardId,
          column_id: selectedColumnId,
          tender_analysis_result_id: tender._id,
          order,
          name: tender.tender_metadata?.name || "Unnamed Tender"
        } as Partial<KanbanTenderItem>
      );
      
      onOpenChange(false);
      onAddSuccess?.(selectedBoardId);
    } catch (error) {
      console.error("Error adding to Kanban:", error);
      onAddError?.(error);
    }
  };

  // Handle "next" button in step 1
  const handleBoardSelectionNext = async () => {
    if (boardSelectionType === "new" && newBoardName.trim()) {
      await handleCreateBoard();
    } else if (boardSelectionType === "existing" && selectedBoardId) {
      setCurrentStep(2);
    }
  };

  // Handle "add" button in step 2
  const handleColumnSelectionFinish = async () => {
    if (columnSelectionType === "new" && newColumnName.trim()) {
      // Create column and then immediately add tender
      await handleCreateColumn();
      await handleAddToKanban();
    } else if (columnSelectionType === "existing" && selectedColumnId) {
      await handleAddToKanban();
    }
  };

  const resetDialog = () => {
    setCurrentStep(1);
    setSelectedBoardId("");
    setSelectedColumnId("");
    setNewBoardName("");
    setNewColumnName("");
    setBoardSelectionType(boards.length > 0 ? "existing" : "new");
    setColumnSelectionType("existing");
  };

  const getBoardName = () => {
    return boards.find(b => b.id === selectedBoardId)?.name || "Wybrana tablica";
  };

  const getColumnName = () => {
    return selectedBoardColumns.find(c => c.id === selectedColumnId)?.name || "Wybrana kolumna";
  };

  return (
    <Dialog 
      open={open} 
      onOpenChange={(isOpen) => {
        if (!isOpen) resetDialog();
        onOpenChange(isOpen);
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Dodaj do Kanban</DialogTitle>
        </DialogHeader>

        {/* Step 1: Board Selection */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <Tabs 
              defaultValue={boardSelectionType} 
              onValueChange={(value) => setBoardSelectionType(value as "existing" | "new")}
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="existing" disabled={boards.length === 0}>
                  Istniejąca tablica
                </TabsTrigger>
                <TabsTrigger value="new">Nowa tablica</TabsTrigger>
              </TabsList>
              
              <TabsContent value="existing" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Wybierz tablicę</Label>
                  <Select
                    value={selectedBoardId}
                    onValueChange={handleBoardChange}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Wybierz tablicę" />
                    </SelectTrigger>
                    <SelectContent>
                      {boards.map((board) => (
                        <SelectItem key={board.id} value={board.id}>
                          {board.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </TabsContent>
              
              <TabsContent value="new" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Nazwa nowej tablicy</Label>
                  <Input
                    value={newBoardName}
                    onChange={(e) => setNewBoardName(e.target.value)}
                    placeholder="Wpisz nazwę tablicy"
                  />
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Anuluj
              </Button>
              <Button 
                onClick={handleBoardSelectionNext}
                disabled={(boardSelectionType === "existing" && !selectedBoardId) || 
                         (boardSelectionType === "new" && !newBoardName.trim())}
              >
                Dalej <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 2: Column Selection */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground mb-2">
              Tablica: <span className="font-medium text-foreground">{getBoardName()}</span>
            </div>

            <Tabs 
              defaultValue={columnSelectionType} 
              onValueChange={(value) => setColumnSelectionType(value as "existing" | "new")}
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="existing" disabled={selectedBoardColumns.length === 0}>
                  Istniejąca kolumna
                </TabsTrigger>
                <TabsTrigger value="new">Nowa kolumna</TabsTrigger>
              </TabsList>
              
              <TabsContent value="existing" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Wybierz kolumnę</Label>
                  <Select
                    value={selectedColumnId}
                    onValueChange={setSelectedColumnId}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Wybierz kolumnę" />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedBoardColumns.map((col) => (
                        <SelectItem key={col.id} value={col.id}>
                          {col.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </TabsContent>
              
              <TabsContent value="new" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Nazwa nowej kolumny</Label>
                  <Input
                    value={newColumnName}
                    onChange={(e) => setNewColumnName(e.target.value)}
                    placeholder="Wpisz nazwę kolumny"
                  />
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button variant="outline" onClick={() => setCurrentStep(1)}>
                Wstecz
              </Button>
              <Button 
                onClick={handleColumnSelectionFinish}
                disabled={(columnSelectionType === "existing" && !selectedColumnId) || 
                         (columnSelectionType === "new" && !newColumnName.trim())}
              >
                Dodaj do Kanban
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
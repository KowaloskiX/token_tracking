"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import {
  Plus,
  Pencil,
  MoreHorizontal,
  Trash2,
  CalendarDays,
  ArrowUpAZ,
  Proportions,
  Loader2,
  Settings2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NewBoardDialog } from "@/components/dashboard/tenders/kanban/NewBoardDialog";
import { DeleteBoardDialog } from "@/components/dashboard/tenders/kanban/DeleteBoardDialog";
import { useKanban } from "@/context/KanbanContext";
import { Badge } from "@/components/ui/badge";
import { Share2, X } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";

type SortType = "name" | "date" | null;
type SortDirection = "asc" | "desc";

export default function BoardManagementHome() {
  const { user } = useDashboard();
  const { boards, isLoading, updateBoardAction, deleteBoardAction, fetchAllBoards } =
    useKanban();
  const router = useRouter();

  const [showNewBoardDialog, setShowNewBoardDialog] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [sortConfig, setSortConfig] = useState<{
    type: SortType;
    direction: SortDirection;
  }>({
    type: "date",
    direction: "desc",
  });

  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchAllBoards();
  }, [fetchAllBoards]);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingId]);

  const formatDate = (dateString: string | Date | undefined) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString("pl", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch (e) {
      console.error("Invalid date format:", dateString);
      return "N/A";
    }
  };

  const handleSort = (type: SortType) => {
    setSortConfig((prev) => ({
      type,
      direction: prev.type === type && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const sortedBoards = [...boards].sort((a, b) => {
    if (!sortConfig.type) return 0;
    const multiplier = sortConfig.direction === "asc" ? 1 : -1;
    if (sortConfig.type === "name") {
      return a.name.localeCompare(b.name) * multiplier;
    }
    const dateA = new Date(a.created_at || 0).getTime();
    const dateB = new Date(b.created_at || 0).getTime();
    return (dateA - dateB) * multiplier;
  });

  const handleNameEdit = (boardId: string, currentName: string) => {
    setEditingId(boardId);
    setEditingName(currentName);
  };

  const handleNameSave = async (boardId: string) => {
    try {
      await updateBoardAction(boardId, { name: editingName });
      setEditingId(null);
      fetchAllBoards();
    } catch (err) {
      console.error("Error updating board name:", err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, boardId: string) => {
    if (e.key === "Enter") handleNameSave(boardId);
    if (e.key === "Escape") setEditingId(null);
  };

  const openBoard = (boardId: string) => {
    if (editingId === boardId) return;
    router.push(`/dashboard/tenders/management/${boardId}`);
  };

  const handleShareToggle = async (board: any, e: React.MouseEvent) => {
    e.stopPropagation();

    try {
      const updateData = {
        org_id: board.org_id ? "" : user?.org_id || "",
      };

      await updateBoardAction(board.id, updateData);
      fetchAllBoards();
    } catch (err) {
      console.error("Error toggling share status:", err);
    }
  };

  if (isLoading) {
    return (
      <div className="w-full h-64 flex justify-center items-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6 w-full align-center">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold">Twoje tablice</h1>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="p-2 hover:bg-secondary rounded-md text-sm flex items-center gap-2">
                <span className="text-neutral-600">Posortuj</span>
                <Settings2 className="w-4 h-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => handleSort("name")}
              >
                <ArrowUpAZ className="w-4 h-4" />
                <span className="flex-1">Sortuj po nazwie</span>
                {sortConfig.type === "name" && (
                  <span className="text-xs text-muted-foreground">
                    {sortConfig.direction === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => handleSort("date")}
              >
                <CalendarDays className="w-4 h-4" />
                <span className="flex-1">Sortuj po dacie</span>
                {sortConfig.type === "date" && (
                  <span className="text-xs text-muted-foreground">
                    {sortConfig.direction === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mt-6">
          <Card
            onClick={() => setShowNewBoardDialog(true)}
            className="group cursor-pointer rounded-xl transition-all duration-300 ease-in-out border-2 border-dashed border-body-text/50 hover:border-body-text flex flex-col items-center justify-center py-6"
          >
            <div className="flex flex-col items-center space-y-2">
              <div className="p-2 bg-secondary rounded-md group-hover:bg-secondary-hover transition-colors">
                <Plus className="w-4 h-4 text-primary" />
              </div>
              <p className="text-sm font-medium text-foreground">
                Utwórz nową tablicę
              </p>
            </div>
          </Card>

          {sortedBoards.map((board) => (
            <Card
              key={board.id}
              onClick={() => openBoard(board.id)}
              className="group cursor-pointer bg-white/40 transition-all duration-300 hover:scale-102 hover:shadow-md py-2 rounded-xl"
            >
              <CardHeader className="p-3 pb-2 space-y-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 bg-secondary rounded-md group-hover:bg-secondary-hover transition-colors">
                    <Proportions className="w-4 h-4 text-primary" />
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger
                      asChild
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button className="p-1 hover:bg-secondary rounded-md">
                        <MoreHorizontal className="w-4 h-4 text-foreground" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {user?.org_id && (
                        <DropdownMenuItem
                          className="focus:bg-secondary"
                          onClick={(e) => handleShareToggle(board, e)}
                        >
                          {board.org_id ? (
                            <>
                              <X className="w-4 h-4 mr-2" />
                              Przestań udostępniać
                            </>
                          ) : (
                            <>
                              <Share2 className="w-4 h-4 mr-2" />
                              Udostępnij w organizacji
                            </>
                          )}
                        </DropdownMenuItem>
                      )}
                      <DeleteBoardDialog
                        boardId={board.id}
                        boardName={board.name}
                        onDeleted={() => {
                          // Just refresh the boards list
                          fetchAllBoards();
                        }}
                      >
                        <DropdownMenuItem
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={(e) => e.stopPropagation()}
                          onSelect={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                          className="text-red-600 focus:text-red-600 focus:bg-secondary"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Usuń
                        </DropdownMenuItem>
                      </DeleteBoardDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <CardTitle className="text-sm font-semibold truncate relative group">
                  {editingId === board.id ? (
                    <input
                      ref={editInputRef}
                      type="text"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onBlur={() => handleNameSave(board.id)}
                      onKeyDown={(e) => handleKeyDown(e, board.id)}
                      className="w-full bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-primary rounded px-1"
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <>
                      {board.name}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleNameEdit(board.id, board.name);
                        }}
                        className="ml-2 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Pencil className="w-3 h-3 text-neutral-400 hover:text-primary ml-1" />
                      </button>
                    </>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0 relative">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-foreground">
                    <span className="hidden sm:inline">Utworzono</span>{" "}
                    {formatDate(board.created_at)}
                  </p>
                  <Badge
                    variant={board.org_id ? "default" : "secondary"}
                    className="text-xs font-medium"
                  >
                    {board.org_id ? "Udostępnione" : "Prywatne"}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <NewBoardDialog
        open={showNewBoardDialog}
        onOpenChange={(open) => {
          setShowNewBoardDialog(open);
          if (!open) fetchAllBoards();
        }}
      />
    </div>
  );
}

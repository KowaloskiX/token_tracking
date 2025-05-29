"use client"
import { ChevronsUpDown, Loader2, Plus, Pencil, Table2 } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenuButton } from "@/components/ui/sidebar"
import { useDashboard } from "@/hooks/useDashboard"
import { useEffect, useState } from "react"
import CreateAssistantForm from "../forms/CreateAssistantForm"
import EditAssistantForm from "../forms/EditAssistantForm"
import { Assistant } from "@/types"
import { getUserAssistants } from "@/utils/assistantActions"

export function AssistantsDropdown() {
  const [isNewAssistantModalOpen, setIsNewAssistantModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [assistantToEdit, setAssistantToEdit] = useState<Assistant | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { 
    currentAssistant, 
    setCurrentAssistant, 
    assistants = [],
    setAssistants,
    user
  } = useDashboard();

  const fetchAssistants = async () => {
    setIsLoading(true);
    setError(null);
    if (user?._id) {
      try {
        const data = await getUserAssistants(user._id)
        setAssistants(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error fetching assistants');
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Fetch assistants when dropdown opens
  useEffect(() => {
    if (dropdownOpen) {
      fetchAssistants();
    }
  }, [dropdownOpen]);

  // Only set initial assistant on mount
  useEffect(() => {
    if (assistants.length > 0 && !currentAssistant) {
      setCurrentAssistant(assistants[assistants.length - 1]);
    }
  }, []); // Empty dependency array for mount-only

  const handleSelectAssistant = (assistant: Assistant) => {
    setDropdownOpen(false);
    if (currentAssistant?._id !== assistant._id) {
      setCurrentAssistant(assistant);
    }
  };

  const handleEditClick = (assistant: Assistant, e: React.MouseEvent) => {
    e.stopPropagation();
    setDropdownOpen(false);
    setAssistantToEdit(assistant);
    setIsEditModalOpen(true);
  };
  
  return (
    <>
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild className="outline-none">
          <SidebarMenuButton
            className="data-[state=open]:bg-sidebar-accent py-6 data-[state=open]:text-sidebar-accent-foreground outline-none px-2"
          >
            <div className="flex aspect-square items-center justify-center rounded-lg bg-transparent text-sidebar-primary">
              <Table2 className="size-4" />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight ml-2">
              <span className="truncate font-semibold">
                {currentAssistant?.name || "Select Assistant"}
              </span>
              <span className="truncate text-xs">
                Projekt
              </span>
            </div>
            <ChevronsUpDown className="ml-auto" />
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
          align="start"
          side="bottom"
          sideOffset={4}
        >
          <DropdownMenuLabel className="text-xs text-muted-foreground">
            Projekty
          </DropdownMenuLabel>
          
          {isLoading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="size-4 animate-spin" />
            </div>
          )}
          
          {error && (
            <div className="px-2 py-4 text-sm text-destructive">
              {error}
            </div>
          )}

          {!isLoading && !error && (
            <div className={`${assistants.length > 7 ? 'max-h-64 overflow-y-auto scrollbar-hide' : ''}`}>
              {assistants.map((assistant) => (
                <DropdownMenuItem
                  key={assistant._id}
                  onClick={() => handleSelectAssistant(assistant)}
                  className="gap-2 p-2 cursor-pointer group"
                >
                  <div className="flex size-6 items-center justify-center rounded-sm border">
                    <Table2 className="size-4 shrink-0" />
                  </div>
                  <span className="flex-grow">{assistant.name}</span>
                  <div 
                    className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:text-blue-500"
                    onClick={(e) => handleEditClick(assistant, e)}
                  >
                    <Pencil className="size-4 text-muted-foreground hover:text-blue-500" />
                  </div>
                </DropdownMenuItem>
              ))}

              {assistants.length === 0 && (
                <div className="px-2 py-4 text-sm text-muted-foreground">
                  Brak projektów
                </div>
              )}
            </div>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem 
            className="gap-2 p-2 cursor-pointer hover:bg-gray-100"
            onClick={() => {
              setIsNewAssistantModalOpen(true);
              setDropdownOpen(false);
            }}
          >
            <div className="flex size-6 items-center justify-center rounded-md border bg-background">
              <Plus className="size-4" />
            </div>
            <div className="font-medium text-muted-foreground">
              Nowy Projekt
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <CreateAssistantForm 
        open={isNewAssistantModalOpen}
        onOpenChange={setIsNewAssistantModalOpen}
      />

      {assistantToEdit && (
        <EditAssistantForm 
          open={isEditModalOpen}
          onOpenChange={setIsEditModalOpen}
          assistant={assistantToEdit}
        />
      )}
    </>
  )
}
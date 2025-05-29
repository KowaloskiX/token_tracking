import { SidebarMenuButton, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ArrowDown, ArrowUp, Bell, Check, Copy, CornerUpLeft, Pencil, FileText, GalleryVerticalEnd, LineChart, Link, LucideIcon, MessageSquarePlus, MoreHorizontal, Settings2, Star, Trash, Trash2 } from "lucide-react";
import { Button } from "../../ui/button";
import { useConversation } from "@/hooks/useConversation";
import { useCallback, useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDashboard } from "@/context/DashboardContext";
import { deleteConversation, updateConversationTitle } from '@/utils/conversationActions';
import { DeletePopup } from "../popup/DeletePopup";
import { checkOrCreateConversation } from "@/utils/conversationActions";

const data = {
  actions: [
    [
      {
        label: "Copy Link",
        icon: Link,
      },
      {
        label: "Rename",
        icon: Pencil,
      },
      {
        label: "Delete",
        icon: Trash2,
      },
    ]
  ]
}

export default function Header() {
  const { currentConversation, setCurrentConversation } = useDashboard();
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState(currentConversation?.title || "");
  const inputRef = useRef<HTMLInputElement>(null);
  const editContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (editContainerRef.current && !editContainerRef.current.contains(event.target as Node)) {
        setIsEditing(false);
        setEditedTitle(currentConversation?.title || "");
      }
    };

    if (isEditing) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isEditing, currentConversation?.title]);

  const handleSubmitTitle = async () => {
    if (!currentConversation || editedTitle.trim() === currentConversation.title) {
      setIsEditing(false);
      return;
    }

    try {
      const updatedConversation = await updateConversationTitle(
        currentConversation._id,
        editedTitle.trim()
      );
      setCurrentConversation(updatedConversation);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update conversation title:', error);
      setEditedTitle(currentConversation.title);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSubmitTitle();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setEditedTitle(currentConversation?.title || "");
    }
  };
  
  return (
    <header className="flex w-full justify-between h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12 px-8">
      <div className="flex items-center gap-2 px-4">
        <SidebarTrigger className="-ml-6" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <div className="flex gap-2 items-center">
          {isEditing ? (
            <div ref={editContainerRef} className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={handleKeyDown}
                className="border rounded px-2 py-1 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="Enter title..."
              />
              <Button
                size="sm"
                className="h-7 w-7 bg-black hover:bg-black/90"
                onClick={handleSubmitTitle}
              >
                <Check className="h-4 w-4 text-white" />
              </Button>
            </div>
          ) : (
            <h2 className="font-semibold">{currentConversation?.title}</h2>
          )}
        </div>
      </div>
      <HeaderActions 
        actions={data.actions} 
        onRename={() => {
          setIsEditing(true);
          setEditedTitle(currentConversation?.title || "");
        }}
      />
    </header>
  );
}


function HeaderActions({
  actions,
  onRename,
}: {
  actions: {
    label: string
    icon: LucideIcon
  }[][]
  onRename: () => void
}) {
  const { createNewConversation } = useConversation();
  const router = useRouter();
  const { 
    setConversationLoading,
    currentConversation,
    setCurrentConversation,
    user, 
    currentAssistant
  } = useDashboard();

  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    isLoading: boolean;
  }>({ isOpen: false, isLoading: false });

  const handleNewConversation = useCallback(async () => {
    try {
      setConversationLoading(true);
      const conversation = await createNewConversation();
      router.push(`/dashboard/${conversation._id}`);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    } finally {
      setConversationLoading(false)
    }
  }, [createNewConversation, router, setConversationLoading]);

  const handleCopyLink = useCallback(() => {
    const url = window.location.href;
    navigator.clipboard.writeText(url)
  }, []);

  const handleDelete = async () => {
    if (!currentConversation || !currentAssistant || !user) return;
    
    try {
      setDeleteDialog(prev => ({ ...prev, isLoading: true }));
      await deleteConversation(currentConversation._id);
      
      const newConversation = await checkOrCreateConversation(
        user._id,
        currentAssistant._id
      );
      setCurrentConversation(newConversation)
    
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setDeleteDialog({ isOpen: false, isLoading: false });
    }
  };

  return (
    <div className="flex items-center gap-4 text-sm">
      <SidebarMenuButton     
        className="h-7 w-7"             
        tooltip={{
          children: "Nowa konwersacja",
          hidden: false,
        }}
        onClick={handleNewConversation}
      >
        <MessageSquarePlus className="size-4"/>
      </SidebarMenuButton>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 data-[state=open]:bg-accent"
          >
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          {actions.map((group, groupIndex) => (
            <DropdownMenuGroup key={groupIndex}>
              {group.map((item, itemIndex) => (
                <DropdownMenuItem 
                  key={itemIndex}
                  onClick={() => {
                    if (item.label === "Copy Link") handleCopyLink();
                    if (item.label === "Delete") {
                      setDeleteDialog(prev => ({ ...prev, isOpen: true }));
                    }
                    if (item.label === "Rename") {
                      onRename();
                    }
                  }}
                  className={item.label === "Delete" ? "text-red-600 focus:text-red-600 focus:bg-red-100 cursor-pointer" : "cursor-pointer"}
                  disabled={item.label === "Delete" && deleteDialog.isLoading}
                >
                  <item.icon className={`mr-2 h-4 w-4 ${item.label === "Delete" ? "text-red-600" : ""}`} />
                  <span>
                    {item.label === "Delete" && deleteDialog.isLoading ? "Deleting..." : item.label}
                  </span>
                </DropdownMenuItem>
              ))}
              {groupIndex < actions.length - 1 && (
                <Separator className="my-1" />
              )}
            </DropdownMenuGroup>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <DeletePopup 
        isOpen={deleteDialog.isOpen}
        onOpenChange={(open: boolean) => 
          setDeleteDialog(prev => ({ ...prev, isOpen: open }))
        }
        onConfirm={handleDelete}
        title="Usuń konwersację"
        description="Czy jesteś pewien? Ta akcja jest nieodwracalna."
        isLoading={deleteDialog.isLoading}
      />
    </div>
  );
}
"use client"
import { useCallback, useEffect, useRef, useState } from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useTender } from "@/context/TenderContext";
import { Button } from "@/components/ui/button";
import { Check, Pencil, Settings2, Share2, X } from "lucide-react";
import { EditTenderAnalysisForm } from "./forms/EditTenderAnalysisForm";
import { useDashboard } from "@/hooks/useDashboard";

export default function TenderHeader() {
  const { selectedAnalysis, updateAnalysis, fetchAnalyses, setSelectedAnalysis } = useTender();
  const { user } = useDashboard();
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState(selectedAnalysis?.name || "");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
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
        setEditedTitle(selectedAnalysis?.name || "");
      }
    };

    if (isEditing) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isEditing, selectedAnalysis?.name]);

  const handleSubmitTitle = async () => {
    if (!selectedAnalysis || editedTitle.trim() === selectedAnalysis.name) {
      setIsEditing(false);
      return;
    }

    try {
      if (selectedAnalysis._id) {
        await updateAnalysis(selectedAnalysis._id, { name: editedTitle.trim() });
        setIsEditing(false);
      }
    } catch (error) {
      console.error('Failed to update analysis name:', error);
      setEditedTitle(selectedAnalysis.name);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSubmitTitle();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setEditedTitle(selectedAnalysis?.name || "");
    }
  };

  const handleSettingsSubmit = async (data: {
    name: string;
    company_description: string;
    search_phrase: string;
    criteria: Array<{ name: string; description: string; weight: number, is_disqualifying: boolean, exclude_from_score: boolean }>;
  }) => {
    if (!selectedAnalysis?._id) return;
    
    try {
      await updateAnalysis(selectedAnalysis._id, data);
      setIsSettingsOpen(false);
    } catch (error) {
      console.error('Failed to update analysis settings:', error);
    }
  };

  const handleShareToggle = async () => {
    if (!selectedAnalysis?._id) return;
    
    try {
      // If currently shared, set org_id to empty string; otherwise, set to user's org_id
      const newOrgId = selectedAnalysis.org_id ? "" : user?.org_id;
      await updateAnalysis(selectedAnalysis._id, { org_id: newOrgId });
      
      // Refresh the analyses list after sharing status update
      await fetchAnalyses();
      
      // Optimistically update the UI without waiting for the next fetch
      if (selectedAnalysis) {
        const updatedAnalysis = {
          ...selectedAnalysis,
          org_id: newOrgId
        };
        setSelectedAnalysis(updatedAnalysis);
      }
    } catch (error) {
      console.error('Failed to toggle sharing status:', error);
    }
  };
  
  return (
    <>
      <header className="flex w-full justify-between h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12 px-8">
        <div className="flex items-center gap-2 px-4">
          <SidebarTrigger className="-ml-6" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <div className="flex items-center gap-2">
            {isEditing ? (
              <div ref={editContainerRef} className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="border rounded px-2 py-1 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-black"
                  placeholder="Enter name..."
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
              <div className="flex items-center gap-2">
                <h2 className="font-semibold">
                  {selectedAnalysis ? selectedAnalysis.name : 'No analysis selected'}
                </h2>
                {selectedAnalysis && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 hover:bg-accent text-neutral-400 hover:text-foreground"
                    onClick={() => {
                      setIsEditing(true);
                      setEditedTitle(selectedAnalysis.name || "");
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>

        {selectedAnalysis && (
          <Button
            variant="secondary"
            size="sm"
            className="h-7 text-foreground hover:shadow-none border-2 hover:bg-secondary-hover border-secondary-border border bg-white/20 shadow"
            onClick={() => setIsSettingsOpen(true)}
          >
            <Settings2 className="h-4 w-4" />
            <span className="hidden sm:block">Ustawienia wyszukiwania</span>
          </Button>
        )}
      </header>

      {selectedAnalysis && isSettingsOpen && (
        <div className="fixed z-50 inset-0 bg-black/50 flex items-start justify-center overflow-y-auto scrollbar-hide">
          <div className="w-full max-w-2xl bg-background rounded-lg mt-10 mb-24 mx-4">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold">Edytuj wyszukiwarkę</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsSettingsOpen(false)}
                  className="h-7 w-7"
                >
                  ×
                </Button>
              </div>
              
              <EditTenderAnalysisForm
                analysis={selectedAnalysis}
                onSubmit={handleSettingsSubmit}
                isLoading={false}
                onShareToggle={handleShareToggle}
                showShareButton={!!user?.org_id}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
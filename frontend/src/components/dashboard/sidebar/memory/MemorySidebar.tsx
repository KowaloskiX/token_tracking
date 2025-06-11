import React, { useState, useEffect, useCallback } from 'react';
import { useDashboard } from "@/context/DashboardContext";
import ExpandableDrawer from "../../ExpandableDrawer";
import { Button } from "@/components/ui/button";
import { 
  ChevronLeft, 
  CloudUpload, 
  EllipsisVertical,
  FolderPlus,
  ArrowUpAZ,
  CalendarArrowUp,
  Loader2,
  Plus,
  X,
  Maximize2,
  Minimize2,
  Search
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MemoryBreadcrumb } from "./MemoryBreadcrumb";
import { MemoryItem } from "./MemoryItem";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyMemory } from './EmptyMemory';
import { useToast } from '@/hooks/use-toast';
import { FileData, FolderData } from '@/types';
import { createFolder, deleteFolder, getAssistantFolders, getDefaultFolder } from '@/utils/folderActions';
import { deleteFile, getFolderFiles } from '@/utils/fileActions';
import UploadMemoryPopup from '../../popup/UploadMemoryPopup';
import { FilePreview } from '../../FilePreview';
import { useTranslations } from 'next-intl';

/** 
 * If you don't already have this somewhere, define the serverUrl to build the download link. 
 * Adjust to match your actual environment variable or config.
 */
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

interface PathItem {
  id: string;
  name: string;
}

interface MemoryItemData {
  _id: string;
  name: string;
  type: string;
  size?: number;
  date?: string;
  preview?: boolean;
  blob_url?: string;
  url?: string;
  removeable?: boolean;
}

type SortType = 'name' | 'date' | null;
type SortDirection = 'asc' | 'desc';

interface SortConfig {
  type: SortType;
  direction: SortDirection;
}

const MemorySidebar = () => {
  const t = useTranslations('dashboard.memory');
  const tCommon = useTranslations('common');
  const { currentAssistant, user } = useDashboard();
  const [isMounted, setIsMounted] = useState(false);
  const [isMobileView, setIsMobileView] = useState<boolean | null>(null);
  const [currentPath, setCurrentPath] = useState<PathItem[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [folders, setFolders] = useState<FolderData[]>([]);
  const [files, setFiles] = useState<FileData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showUploadPopup, setShowUploadPopup] = useState(false);
  const [defaultFolderId, setDefaultFolderId] = useState<string | null>(null);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    type: null,
    direction: 'asc'
  });
  const [searchQuery, setSearchQuery] = useState('');

  // File preview state
  const [previewFile, setPreviewFile] = useState<{
    _id: string;
    name: string;
    type: string;
    url: string;
    blob_url?: string;
  } | null>(null);

  const { toast } = useToast();

  useEffect(() => {
    const checkMobileView = () => {
      const isMobile = window.innerWidth < 768;
      setIsMobileView(isMobile);
    };

    checkMobileView();
    
    setIsMounted(true);

    window.addEventListener('resize', checkMobileView);
    return () => {
      window.removeEventListener('resize', checkMobileView);
    };
  }, []);
  
  const fetchFoldersAndFiles = useCallback(async () => {
    if (!user?._id || !currentAssistant?._id) {
      setFolders([]);
      setFiles([]);
      setDefaultFolderId(null);
      setIsLoading(false);
      return;
    }
  
    try {
      setIsLoading(true);
      
      // For shared assistants we just fetch folders by assistant id.
      const defaultFolder = await getDefaultFolder(currentAssistant._id, user?._id);
      setDefaultFolderId(defaultFolder._id);
      
      // Get all folders for current assistant without filtering by user id
      const assistantFolders = await getAssistantFolders(currentAssistant._id, user?._id);
      setFolders(assistantFolders.filter(folder => folder._id !== defaultFolder._id));
      
      // Get files for current folder or default folder
      const targetFolderId = currentFolderId || defaultFolder._id;
      const targetFiles = await getFolderFiles(targetFolderId);
      setFiles(targetFiles);
      console.log(targetFiles);
      
    } catch (e) {
      console.error('Error in fetchFoldersAndFiles:', e);
      toast({
        title: tCommon('error'),
        description: t('error_fetching_memory') + `: ${e instanceof Error ? e.message : String(e)}`,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [currentAssistant?._id, user?._id, currentFolderId, toast, t, tCommon]);

  // Reset state when currentAssistant changes
  useEffect(() => {
    setCurrentPath([]);
    setCurrentFolderId(null);
    setFolders([]);
    setFiles([]);
    fetchFoldersAndFiles();
  }, [currentAssistant?._id, fetchFoldersAndFiles]);

  const handleUploadComplete = useCallback(() => {
    fetchFoldersAndFiles();
  }, [fetchFoldersAndFiles]);

  const handleCreateFolder = async () => {
    if (!user?._id || !currentAssistant?._id) return;
  
    // Generate unique name
    const baseName = tCommon('new_folder');
    const existingFolders = folders.filter(f => 
      f.parent_folder_id === (currentFolderId || defaultFolderId)
    );
    
    let folderName = baseName;
    let counter = 1;
    while (existingFolders.some(f => f.name === folderName)) {
      folderName = `${baseName} ${counter}`;
      counter++;
    }

    try {
      const newFolder = await createFolder({
        name: folderName,
        owner_id: user._id,
        assistant_id: currentAssistant._id,
        parent_folder_id: currentFolderId || defaultFolderId || undefined
      });

      // Add new folder to path and set as current
      setCurrentPath(prev => [...prev, { id: newFolder._id, name: newFolder.name }]);
      setCurrentFolderId(newFolder._id);
      
      await fetchFoldersAndFiles();
      return newFolder;
    } catch (e) {
      toast({
        title: tCommon('error'),
        description: t('error_creating_folder') + `: ${e instanceof Error ? e.message : String(e)}`,
        variant: "destructive",
      });
      return null;
    }
  };

  const handleNavigateBack = () => {
    if (currentPath.length === 0) return;
    const newPath = currentPath.slice(0, -1);
    setCurrentPath(newPath);
    if (newPath.length === 0) {
      setCurrentFolderId(null);
    } else {
      const parentFolder = newPath[newPath.length - 1];
      setCurrentFolderId(parentFolder.id);
    }
  };

  const handleNavigateToFolder = async (folderId: string, name: string) => {
    setCurrentPath(prev => [...prev, { id: folderId, name }]);
    setCurrentFolderId(folderId);
  };

  const handleFileClick = (item: MemoryItemData) => {
    if (item.type === 'folder') {
      // Navigate into folder
      handleNavigateToFolder(item._id, item.name);
    } else if (item.preview) {
      // Find the full file data from our files array
      const fileData = files.find(f => f._id === item._id);
      if (!fileData) return;
      
      // Use blob_url if available, otherwise fallback to server URL
      const fileUrl = fileData.blob_url || null;

      if (fileUrl === null) return;

      setPreviewFile({
        _id: item._id,
        name: item.name,
        type: item.type,
        url: fileUrl,
        blob_url: fileData.blob_url
      });
    }
  };

  const handleClosePreview = () => {
    setPreviewFile(null);
  };

  const getCurrentItems = (): MemoryItemData[] => {
    let currentFolderItems: MemoryItemData[] = [];
    
    // Add folders
    folders
      .filter(f => f.parent_folder_id === (currentFolderId || defaultFolderId))
      .forEach(folder => {
        currentFolderItems.push({
          _id: folder._id,
          name: folder.name,
          type: 'folder',
          date: folder.created_at,
          removeable: true
        });
      });

    // Add files
    files.forEach(file => {
      currentFolderItems.push({
        _id: file._id,
        name: file.filename,
        type: file.type || 'unknown',
        preview: !!file.blob_url,
        size: file.bytes,
        date: file.created_at,
        blob_url: file.blob_url,
        url: file.url,
        removeable: file.user_file || false
      });
    });

    // Filter by search query if present
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      currentFolderItems = currentFolderItems.filter(item => 
        item.name.toLowerCase().includes(query)
      );
    }

    // Sort items based on current configuration
    if (sortConfig.type) {
      return currentFolderItems.sort((a, b) => {
        // Always keep folders at the top regardless of sort
        if (a.type === 'folder' && b.type !== 'folder') return -1;
        if (a.type !== 'folder' && b.type === 'folder') return 1;

        let comparison = 0;
        
        if (sortConfig.type === 'name') {
          comparison = a.name.localeCompare(b.name);
        } else if (sortConfig.type === 'date' && a.date && b.date) {
          comparison = new Date(a.date).getTime() - new Date(b.date).getTime();
        }

        return sortConfig.direction === 'asc' ? comparison : -comparison;
      });
    }

    return currentFolderItems;
  };

  const handleSort = (type: SortType) => {
    setSortConfig(prevConfig => ({
      type,
      direction: 
        prevConfig.type === type 
          ? prevConfig.direction === 'asc' 
            ? 'desc' 
            : 'asc'
          : 'asc'
    }));
  };

  const handleDelete = async (itemId: string, itemType: string) => {
    try {
      if (itemType === 'folder') {
        if (currentFolderId === itemId) {
          handleNavigateBack();
        }
        await deleteFolder(itemId);
        setFolders(prev => prev.filter(folder => folder._id !== itemId));
        setCurrentPath(prev => prev.filter(item => item.id !== itemId));
      } else {
        await deleteFile(itemId);
        setFiles(prev => prev.filter(file => file._id !== itemId));
        // If the deleted file is currently previewed, close the preview
        if (previewFile && previewFile._id === itemId) {
          handleClosePreview();
        }
      }
      await fetchFoldersAndFiles();
      toast({
        title: tCommon('success'),
        description: `${itemType === 'folder' ? t('folder_deleted') : t('file_deleted')}`,
      });
    } catch (e) {
      console.error('Error deleting item:', e);
      toast({
        title: tCommon('error'),
        description: t('error_deleting_item', { type: itemType.toLowerCase() }) + `: ${e instanceof Error ? e.message : String(e)}`,
        variant: "destructive",
      });
    }
  };

  const handleRename = async (itemId: string, newName: string) => {
    // The actual rename is handled in the MemoryItem component; just refresh here
    await fetchFoldersAndFiles();

    // Update preview file name if it's being renamed
    if (previewFile && previewFile._id === itemId) {
      setPreviewFile(prev => prev ? { ...prev, name: newName } : null);
    }
  };

  if (!isMounted || isMobileView === null) {
    return null;
  }

  // ------------------ RENDERING FILE BROWSER TAB ------------------
  const filesBrowserContent = (
    <>
      <div className="flex flex-col space-y-3 w-full pb-3 border-b border-b-neutral-200 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex gap-2 items-center">
            {currentPath.length > 0 && (
              <Button 
                variant="outline" 
                className="rounded-full p-2 h-auto"
                onClick={handleNavigateBack}
              >
                <ChevronLeft className="h-5 w-5" />
              </Button>
            )}
            <h4 className="font-medium">{currentPath[currentPath.length - 1]?.name || tCommon('home')}</h4>
          </div>
          <div className="flex items-center gap-2">
            <MemoryBreadcrumb 
              path={currentPath}
              onNavigate={(newPath) => {
                setCurrentPath(newPath);
                if (newPath.length === 0) {
                  setCurrentFolderId(null);
                } else {
                  const lastFolder = newPath[newPath.length - 1];
                  setCurrentFolderId(lastFolder.id);
                }
              }}
            />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 p-0">
                  <EllipsisVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="px-2">
                <DropdownMenuItem 
                  className="flex items-center gap-3 cursor-pointer"
                  onClick={handleCreateFolder}
                >
                  <FolderPlus className="w-4 h-4" />
                  <span>{t('create_folder')}</span>
                </DropdownMenuItem>
                <DropdownMenuItem 
                  className="flex items-center gap-3 cursor-pointer"
                  onClick={() => handleSort('name')}
                >
                  <ArrowUpAZ className="w-4 h-4" />
                  <span className="flex-1">{tCommon('sort_by_name')}</span>
                  {sortConfig.type === 'name' && (
                    <span className="text-xs text-muted-foreground">
                      {sortConfig.direction === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem 
                  className="flex items-center gap-3 cursor-pointer"
                  onClick={() => handleSort('date')}
                >
                  <CalendarArrowUp className="w-4 h-4" />
                  <span className="flex-1">{tCommon('sort_by_date')}</span>
                  {sortConfig.type === 'date' && (
                    <span className="text-xs text-muted-foreground">
                      {sortConfig.direction === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-auto min-h-0 scrollbar-hide">
        {getCurrentItems().length > 0 ? (
          <div className="grid grid-cols-2 gap-3 px-2 py-4">
            {getCurrentItems().map((item) => (
              <MemoryItem 
                key={item._id}
                item={item}
                onNavigate={() => handleFileClick(item)}
                onRename={handleRename}
                onDelete={async (id) => await handleDelete(id, item.type)}
                refreshItems={fetchFoldersAndFiles}
              />
            ))}
            {/* + Button to prompt uploading */}
            <button
              onClick={() => setShowUploadPopup(true)}
              className="flex items-center justify-center h-20 border-2 border-dashed border-neutral-200 rounded-lg p-4 hover:border-neutral-300 transition-colors"
            >
              <Plus strokeWidth={1.5} className="w-6 h-6 text-neutral-300 hover:text-neutral-400 transition-colors" />
            </button>
          </div>
        ) : (
          <EmptyMemory 
            setOpenPopup={() => setShowUploadPopup(true)}
          />
        )}
      </div>
    </>
  );

  // ------------------ MAIN DRAWER CONTENT ------------------
  const drawerContent = (
    <div className="flex flex-col h-full py-4 px-4 sm:px-6">
      {/* Header section - Modified for better responsiveness */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 shrink-0">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-xl sm:text-lg mb-1 truncate">
            {currentAssistant 
              ? (currentAssistant.name.length > 32 
                  ? `${currentAssistant.name.slice(0, 32)}...` 
                  : currentAssistant.name
                ) 
              : "Assistant"
            }
            &apos;- {tCommon('resources')}
          </h3>
          <p className="text-sm text-muted-foreground">
            {tCommon('upload_files_websites')}
          </p>
        </div>
        <Button 
          className="w-full sm:w-auto whitespace-nowrap"
          onClick={() => setShowUploadPopup(true)}
        >
          <CloudUpload className="mr-2 flex-shrink-0" />
          {tCommon('upload')}
        </Button>
      </div>

      <Card className="flex flex-col flex-1 p-4 shrink-0 rounded-md border mt-6 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : (
          <div className="flex flex-col h-full">
            {filesBrowserContent}
          </div>
        )}
      </Card>
    </div>
  );

  return (
    <>
      {isMounted && (
        <ExpandableDrawer>
          {drawerContent}
        </ExpandableDrawer>
      )}

      {previewFile && (
        <FilePreview 
          file={previewFile}
          onClose={handleClosePreview}
        />
      )}

      {/* Upload Popup */}
      {showUploadPopup && user && (
        <div 
          className="fixed top-0 left-0 inset-0 bg-black/50 flex overflow-y-auto scrollbar-hide justify-center py-28 z-50"
          onClick={() => setShowUploadPopup(false)}
        >
          <div>
            <UploadMemoryPopup 
              closePopup={() => setShowUploadPopup(false)}
              currentFolderId={currentFolderId || defaultFolderId}
              onUploadComplete={handleUploadComplete}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default MemorySidebar;
import React, { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { 
  File, 
  Folder, 
  EllipsisVertical, 
  Pencil, 
  Trash2, 
  Globe, 
  FileText, 
  FileImage, 
  FileCode, 
  Eye,
  Database,
  Music,
  Film,
  Package,
  BookOpen,
  FileJson,
  Scroll,
  Loader2
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatBytes, formatDate, renameFile } from '@/utils/fileActions';
import { renameFolder } from '@/utils/folderActions';
import { DeleteItemDialog } from './DeleteItemDialog';
import { useToast } from '@/hooks/use-toast';
import { Card } from '@/components/ui/card';
import { Badge } from "@/components/ui/badge";
import { useTranslations } from 'next-intl';

interface MemoryItemData {
  _id: string;
  name: string;
  type: string;
  size?: number;
  date?: string;
  preview?: boolean;
  removeable?: boolean;
}

interface ExtendedMemoryItemProps {
  item: MemoryItemData;
  onNavigate?: (name: string) => void;
  onDelete?: (id: string) => Promise<void> | void;
  onRename?: (id: string, newName: string) => void;
  refreshItems?: () => void;
}

interface ItemDropdownProps { 
  id: string;
  name: string;
  type: string;
  preview: boolean;
  removeable: boolean;
  onStartRename: () => void;
  onDelete?: (id: string) => Promise<void> | void;
  onView?: () => void;
}

const MAX_TITLE_LENGTH = 20;

// Enhanced icon selection for different file types
const ItemIcon = ({ type, name }: { type: string, name: string }) => {
  // Get file extension for more specific icon selection
  const getExtension = (filename: string): string => {
    if (type === 'folder' || type === 'website') return type;
    const parts = filename.split('.');
    return parts.length > 1 ? parts.pop()?.toLowerCase() || '' : '';
  };
  
  const fileExt = getExtension(name);

  switch (type) {
    case 'folder':
      return <Folder className="w-5 h-5 shrink-0" />;
    case 'website':
      return <Globe className="w-5 h-5 shrink-0" />;
    default:
      // More specific file type icons
      switch (fileExt) {
        // Documents - distinct icons for the main document types
        case 'pdf':
          return <BookOpen className="w-5 h-5 shrink-0 text-red-500/50" />;
        case 'doc':
        case 'docx':
          return <Scroll className="w-5 h-5 shrink-0 text-blue-500/50" />;
        case 'txt':
          return <FileText className="w-5 h-5 shrink-0 text-stone-600" />;
        case 'rtf':
          return <FileText className="w-5 h-5 shrink-0 text-stone-500" />;
          
        // Spreadsheets
        case 'xls':
        case 'xlsx':
        case 'csv':
          return <Database className="w-5 h-5 shrink-0 text-green-600/50" />;
          
        // Images
        case 'jpg':
        case 'jpeg':
        case 'png':
        case 'gif':
        case 'svg':
        case 'webp':
          return <FileImage className="w-5 h-5 shrink-0 text-pink-500/50" />;
          
        // Code
        case 'js':
        case 'ts':
        case 'jsx':
        case 'tsx':
          return <FileCode className="w-5 h-5 shrink-0 text-yellow-500/50" />;
        case 'py':
          return <FileCode className="w-5 h-5 shrink-0 text-blue-500/50" />;
        case 'java':
        case 'cpp':
        case 'c':
          return <FileCode className="w-5 h-5 shrink-0 text-orange-600/50" />;
        case 'php':
        case 'rb':
        case 'go':
        case 'rs':
          return <FileCode className="w-5 h-5 shrink-0 text-purple-600/50" />;
          
        // Web
        case 'html':
          return <FileCode className="w-5 h-5 shrink-0 text-orange-500/50" />;
        case 'css':
          return <FileCode className="w-5 h-5 shrink-0 text-blue-400/50" />;
        case 'json':
          return <FileJson className="w-5 h-5 shrink-0 text-yellow-600/50" />;
        case 'xml':
          return <FileCode className="w-5 h-5 shrink-0 text-gray-500/50" />;
          
        // Archives
        case 'zip':
        case 'rar':
        case 'tar':
        case 'gz':
        case '7z':
          return <Package className="w-5 h-5 shrink-0 text-amber-600/50" />;
          
        // Media
        case 'mp3':
        case 'wav':
        case 'ogg':
        case 'flac':
          return <Music className="w-5 h-5 shrink-0 text-indigo-500/50" />;
        case 'mp4':
        case 'mov':
        case 'avi':
        case 'mkv':
        case 'webm':
          return <Film className="w-5 h-5 shrink-0 text-red-600/50" />;
          
        // Default for other file types
        default:
          return <File className="w-5 h-5 shrink-0 text-gray-500/50" />;
      }
  }
};

const truncateFileName = (name: string, type: string): string => {
  if (name.length <= MAX_TITLE_LENGTH) return name;
  
  // For websites, don't show extension in truncated view
  if (type === 'website') {
    return `${name.slice(0, MAX_TITLE_LENGTH)}...`;
  }
  
  const lastDotIndex = name.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return `${name.slice(0, MAX_TITLE_LENGTH)}...`;
  }
  
  const extension = name.slice(lastDotIndex);
  const nameWithoutExt = name.slice(0, lastDotIndex);
  const maxNameLength = Math.max(MAX_TITLE_LENGTH - extension.length - 3, 3); // -3 for the ellipsis
  return `${nameWithoutExt.slice(0, maxNameLength)}...${extension}`;
};

const EditableTitle = ({ 
  initialName, 
  isEditing, 
  onFinishEditing, 
  onCancel,
  itemType
}: { 
  initialName: string;
  isEditing: boolean;
  onFinishEditing: (newName: string) => void;
  onCancel: () => void;
  itemType: string;
}) => {
  const t = useTranslations('dashboard.memory');
  const tCommon = useTranslations('common');
  const inputRef = useRef<HTMLInputElement>(null);
  const [editedName, setEditedName] = useState(initialName);
  const { toast } = useToast();
  
  useEffect(() => {
    if (isEditing && inputRef.current) {
      const input = inputRef.current;
      input.focus();
      
      // For non-website files, select name without extension
      if (itemType !== 'website') {
        const lastDotIndex = initialName.lastIndexOf('.');
        if (lastDotIndex > 0) {
          input.setSelectionRange(0, lastDotIndex);
        } else {
          input.select();
        }
      } else {
        // For websites, select the entire name
        input.select();
      }
    }
  }, [isEditing, initialName, itemType]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation();
    if (e.key === 'Enter') {
      if (editedName.length > MAX_TITLE_LENGTH) {
        toast({
          title: tCommon('error'),
          description: t('name_too_long', { length: MAX_TITLE_LENGTH }),
          variant: "destructive",
        });
        return;
      }
      onFinishEditing(editedName);
    } else if (e.key === 'Escape') {
      onCancel();
    }
  };

  const handleBlur = () => {
    if (editedName.length > MAX_TITLE_LENGTH) {
      toast({
        title: tCommon('error'),
        description: t('name_too_long', { length: MAX_TITLE_LENGTH }),
        variant: "destructive",
      });
      return;
    }
    onFinishEditing(editedName);
  };

  if (!isEditing) {
    return (
      <p className="text-sm font-medium truncate">
        {truncateFileName(initialName, itemType)}
      </p>
    );
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={editedName}
      onChange={(e) => setEditedName(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleBlur}
      maxLength={MAX_TITLE_LENGTH}
      className="bg-transparent border-none p-0 m-0 text-sm font-medium focus:outline-none focus:ring-0 w-full"
    />
  );
};

const ItemDropdown = ({ 
  id,
  name,
  type,
  preview,
  removeable,
  onStartRename,
  onDelete,
  onView
}: ItemDropdownProps) => {
  const t = useTranslations('dashboard.memory');
  const tCommon = useTranslations('common');
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowDeleteDialog(true);
  };

  const handleConfirmDelete = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (onDelete) {
      await onDelete(id);
    }
    setShowDeleteDialog(false);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild onClick={handleClick}>
          <Button
            variant="ghost"
            size="icon"
            className="w-6 h-6 shrink-0"
          >
            <EllipsisVertical className="w-3 h-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" onClick={handleClick}>
          {type !== 'folder' && onView && preview && (
            <DropdownMenuItem 
              onClick={(e) => {
                e.stopPropagation();
                onView();
              }}
              className="gap-2"
            >
              <Eye className="w-4 h-4" />
              {t('open_preview')}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem 
            onClick={(e) => {
              e.stopPropagation();
              onStartRename();
            }}
            className="gap-2"
          >
            <Pencil className="w-4 h-4" />
            {tCommon('rename')}
          </DropdownMenuItem>
          {removeable && (
            <DropdownMenuItem 
              onClick={handleDeleteClick}
              className="gap-2 text-red-600"
            >
              <Trash2 className="w-4 h-4" />
              {tCommon('delete')}
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <DeleteItemDialog
        isOpen={showDeleteDialog}
        onClose={() => {
          setShowDeleteDialog(false);
        }}
        onConfirm={handleConfirmDelete}
        itemName={name}
        itemType={type === 'folder' ? 'folder' : 'file'}
      />
    </>
  );
};

export const MemoryItem = React.memo<ExtendedMemoryItemProps>(({ 
  item, 
  onNavigate,
  onDelete,
  onRename,
  refreshItems
}) => {
  const t = useTranslations('dashboard.memory');
  const tCommon = useTranslations('common');
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const { toast } = useToast();

  const handleRename = async (newName: string) => {
    if (newName === item.name || !newName.trim()) {
      setIsEditing(false);
      return;
    }

    if (newName.length > MAX_TITLE_LENGTH) {
      toast({
        title: tCommon('error'),
        description: t('name_too_long', { length: MAX_TITLE_LENGTH }),
        variant: "destructive",
      });
      return;
    }

    try {
      if (item.type === 'folder') {
        await renameFolder(item._id, newName);
      } else {
        await renameFile(item._id, newName);
      }
      
      onRename?.(item._id, newName);
      refreshItems?.();
      
      toast({
        title: tCommon('success'),
        description: `${item.type === 'folder' ? t('folder_renamed') : t('file_renamed')}`,
      });
    } catch (error) {
      toast({
        title: tCommon('error'),
        description: t('error_renaming_item', { type: item.type.toLowerCase() }) + `: ${error instanceof Error ? error.message : String(error)}`,
        variant: "destructive",
      });
    } finally {
      setIsEditing(false);
    }
  };

  const getFileExtension = (filename: string) => {
    if (item.type === 'folder' || item.type === 'website') return null;
    const parts = filename.split('.');
    return parts.length > 1 ? parts.pop()?.toUpperCase() : null;
  };

  const extension = getFileExtension(item.name);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
  
    // Try to get the file url (blob_url or url)
    const fileUrl = (item as any).blob_url || (item as any).url;

    if (!fileUrl) {
      toast({
        title: tCommon('error'),
        description: t('no_download_url'),
        variant: "destructive",
      });
      return;
    }
  
    setIsDownloading(true);
    try {
      const response = await fetch(fileUrl);
  
      if (!response.ok) {
        throw new Error(t('download_failed', { status: response.status }));
      }
  
      const blob = await response.blob();
  
      if (blob.size === 0) {
        throw new Error(t('file_empty'));
      }
      if (blob.type.startsWith("text/html")) {
        throw new Error(t('html_instead_of_file'));
      }
  
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = item.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error("MemoryItem handleDownload error:", err);
  
      toast({
        title: tCommon('error'),
        description: t('download_error') + `: ${err instanceof Error ? err.message : String(err)}`,
        variant: "destructive",
      });
    } finally {
      setIsDownloading(false);
    }
  };

  const handleItemClick = (e: React.MouseEvent) => {
    if (!isEditing && item.type === 'folder') {
      onNavigate?.(item.name);
    }
  };

  return (
    <div 
      className={`
        inline-flex relative w-full h-20 items-center gap-2 rounded-lg 
        transition-all duration-200 border-2 border-secondary-border bg-secondary 
        cursor-pointer hover:bg-secondary-hover relative
      `}
      onClick={item.type !== 'folder' ? handleDownload : undefined}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Preview button that appears on hover - positioned outside the card */}
      {item.type !== 'folder' && isHovered && item.preview && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm z-20"
          onClick={(e) => {
            e.stopPropagation();
            onNavigate?.(item.name);
          }}
        >
          <Eye className="h-3.5 w-3.5" />
        </Button>
      )}
      
      {/* Main item card */}
      <div 
        className={`
          flex items-center py-1 px-2 rounded-lg 
          transition-all duration-200 border border-secondary-border bg-secondary
          cursor-pointer hover:bg-secondary-hover
          w-full h-full overflow-hidden
        `}
        onClick={handleItemClick}
      >
        {/* Main content area - flexbox with even spacing */}
        <div className="flex items-center space-x-3 w-full overflow-hidden">
          {/* Icon Section */}
          <div className="flex-shrink-0">
            <Card className="bg-background p-2 w-10 h-10 flex items-center justify-center shadow-sm">
              {isDownloading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <ItemIcon type={item.type} name={item.name} />
              )}
            </Card>
          </div>
          
          {/* Content Section */}
          <div className="flex-grow min-w-0 overflow-hidden">
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="max-w-full">
                    <EditableTitle
                      initialName={item.name}
                      isEditing={isEditing}
                      onFinishEditing={handleRename}
                      onCancel={() => setIsEditing(false)}
                      itemType={item.type}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[300px] break-all">
                  <p>{item.name}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            {/* File details with improved layout */}
            <div className="flex items-center gap-2 text-xs text-neutral-500 mt-1 overflow-hidden">
              {extension && (
                <Badge variant="outline" className="h-4 px-1 text-xs flex-shrink-0">
                  {extension}
                </Badge>
              )}
              {item.type !== 'folder' && (
                <div className="flex items-center gap-1 overflow-hidden whitespace-nowrap">
                  {item.size && (
                    <span className="flex-shrink-0">{formatBytes(item.size)}</span>
                  )}
                  {item.date && (
                    <>
                      {item.size && (<span className="flex-shrink-0 mx-1">•</span>)}
                      <span className="flex-shrink-0">{formatDate(item.date)}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
          
          {/* Action buttons */}
          <div className="flex-shrink-0">
            <ItemDropdown 
              id={item._id}
              name={item.name}
              type={item.type}
              preview={item.preview ?? false}
              removeable={item.removeable ?? false}
              onStartRename={() => setIsEditing(true)}
              onDelete={onDelete}
              onView={item.type !== 'folder' ? () => onNavigate?.(item.name) : undefined}
            />
          </div>
        </div>
      </div>
    </div>
  );
});

MemoryItem.displayName = 'MemoryItem';

export default MemoryItem;
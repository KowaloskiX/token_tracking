import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

const FileComponent = ({ file, onRemove }: { file: File; onRemove: () => void }) => {
    const shortenedName = file.name.length > 20 ? file.name.slice(0, 12) + '...' : file.name;
  
    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B';
        else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        else return (bytes / 1048576).toFixed(1) + ' MB';
      };
      
    return (
      <div className="flex items-center gap-2 p-2 border rounded-lg bg-neutral-50">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{shortenedName}</p>
          <p className="text-xs text-neutral-500">{formatFileSize(file.size)}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="w-8 h-8 shrink-0"
          onClick={onRemove}
        >
          <X className="w-4 h-4" />
        </Button>
      </div>
    );
  };

  
  export default FileComponent;
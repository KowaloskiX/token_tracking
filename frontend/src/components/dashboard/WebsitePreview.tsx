import { Button } from "@/components/ui/button";
import { Globe, X } from "lucide-react";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

interface WebsitePreviewProps {
    title: string;
    url: string;
    favicon?: string;
    onRemove: () => void;
    onClick?: () => void;
    openInNewTab?: boolean;
    selected?: boolean;
}

const truncateText = (text: string, limit: number) => {
    if (text.length <= limit) return text;
    return text.substring(0, limit) + "...";
};

export const WebsitePreview = ({ 
    title, 
    url, 
    favicon, 
    onRemove, 
    onClick, 
    openInNewTab,
    selected = false
}: WebsitePreviewProps) => {
    const displayTitle = truncateText(title || url, 22);
    const displayUrl = truncateText(url, 28);

    const handleClick = (e: React.MouseEvent) => {
        if (openInNewTab) {
            e.preventDefault();
            window.open(url, '_blank');
        } else if (onClick) {
            onClick();
        }
    };

    return (
        <div 
            className={`
                inline-flex items-center gap-2 p-2 pr-1 rounded-lg 
                transition-all duration-200 
                ${selected ? 'border-2 border-black bg-neutral-100' : 'border border-neutral-200 bg-neutral-50'} 
                ${(onClick || openInNewTab) ? 'cursor-pointer hover:bg-neutral-100' : ''}
            `}
            onClick={handleClick}
        >
            <div className="flex items-center gap-4">
                {favicon ? (
                    <img 
                        src={favicon} 
                        alt="favicon" 
                        className="w-4 h-4 shrink-0" 
                        onError={(e) => {
                            e.currentTarget.onerror = null;
                            e.currentTarget.src = '/default-favicon.ico';
                        }} 
                    />
                ) : (
                    <Globe className="w-4 h-4 shrink-0" />
                )}
                <div className="min-w-0">
                    <TooltipProvider delayDuration={300}>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <p className="text-sm font-medium">
                                    {displayTitle}
                                </p>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-[300px] break-all">
                                <p>{title || url}</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                    
                    <TooltipProvider delayDuration={300}>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <p className="text-xs text-neutral-500">
                                    {displayUrl}
                                </p>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-[300px] break-all">
                                <p>{url}</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                </div>
            </div>
            <Button
                variant="ghost"
                size="icon"
                className="w-6 h-6 shrink-0"
                onClick={(e) => {
                    e.stopPropagation();
                    onRemove();
                }}
            >
                <X className="w-3 h-3" />
            </Button>
        </div>
    );
};
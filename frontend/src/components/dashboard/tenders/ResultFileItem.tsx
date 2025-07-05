import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FileData } from "@/types";
import { FileText } from "lucide-react";
import { useState } from "react";

const ResultFileItem = ({ file }: { file: FileData }) => {
    const [downloading, setDownloading] = useState(false);

    const downloadFile = async () => {
        const fileDownloadUrl = file.blob_url || file.url;
        if (!fileDownloadUrl) return;
        setDownloading(true);
        try {
            const response = await fetch(fileDownloadUrl);
            if (!response.ok) throw new Error("File not found");
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = file.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert("Nie można pobrać pliku.");
        } finally {
            setDownloading(false);
        }
    };

    const content = (
        <div className="inline-flex items-center gap-2 py-2 px-3 rounded-lg transition-all duration-200 border border-secondary-border bg-white/20 w-full hover:bg-secondary shadow-sm">
            <div className="flex items-center gap-2 w-full min-w-0">
                <Card className="bg-background p-1.5 shrink-0 rounded-md">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                </Card>
                <TooltipProvider delayDuration={300}>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <p className="text-sm font-medium truncate">
                                {file.filename}
                            </p>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-[300px] break-all">
                            <p>{file.filename}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>
        </div>
    );

    const fileDownloadUrl = file.blob_url || file.url;

    return fileDownloadUrl ? (
        <button
            type="button"
            className="text-left flex-grow basis-[calc(50%-0.5rem)] min-w-[200px]"
            onClick={downloadFile}
            disabled={downloading}
            style={{ opacity: downloading ? 0.6 : 1, cursor: downloading ? "not-allowed" : "pointer" }}
        >
            {content}
        </button>
    ) : (
        <div className="cursor-not-allowed flex-grow basis-[calc(50%-0.5rem)] min-w-[200px]">
            {content}
        </div>
    );
};

export default ResultFileItem;
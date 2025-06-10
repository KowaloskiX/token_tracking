"use client"
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import TenderHeader from "@/components/dashboard/tenders/TenderHeader";
import TendersList from "@/components/dashboard/tenders/TendersList";
import TenderResultSidebar from "@/components/dashboard/tenders/TenderResultSidebar";
import { FilePreview } from "@/components/dashboard/FilePreview";
import { useTender } from "@/context/TenderContext";
import { Loader2 } from "lucide-react";
import { TenderAnalysisResult } from "@/types/tenders";
import { FileData } from "@/types";

interface PreviewFile {
    _id: string;
    name: string;
    type: string;
    url: string;
    blob_url?: string;
    citations?: string[];
}

const TenderAnalysis = () => {
    const { tenderAnalysisId } = useParams();
    const { fetchAnalysisById, selectedResult } = useTender();
    const [fetching, setFetching] = useState(true);
    const drawerRef = useRef<{ setVisibility: (value: boolean) => void }>(null);
    const [allResults, setAllResults] = useState<TenderAnalysisResult[]>([]);
    
    // FilePreview state
    const [previewFile, setPreviewFile] = useState<PreviewFile | null>(null);
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);
    const [currentTenderBoardStatus, setCurrentTenderBoardStatus] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (tenderAnalysisId) {
                setFetching(true);
                await fetchAnalysisById(tenderAnalysisId as string);
                setFetching(false);
                // Ensure sidebar is hidden on initial load
                drawerRef.current?.setVisibility(false);
            }
        };
        
        fetchData();
    }, [tenderAnalysisId, fetchAnalysisById]);

    const openFilePreview = (file: FileData, citationsForFile: string[]) => {
        const previewFile: PreviewFile = {
            _id: file._id || file.filename,
            name: file.filename,
            type: file.type,
            url: file.url || '',
            blob_url: file.blob_url,
            citations: citationsForFile
        };
        
        setPreviewFile(previewFile);
        setIsPreviewOpen(true);
    };

    const closeFilePreview = () => {
        setIsPreviewOpen(false);
        setPreviewFile(null);
    };

    if (fetching) {
        return (
            <div className="flex w-full h-screen items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </div>
        );
    }

    return (
        <>
            <div className="w-full flex h-[100svh] overflow-hidden">
              <div className="flex-1 flex flex-col overflow-hidden min-w-0">
                <div className="flex-none">
                  <TenderHeader />
                </div>
                <div className="flex-1 overflow-auto scrollbar-hide">
                  <TendersList allResults={allResults} setAllResults={setAllResults} drawerRef={drawerRef} setCurrentTenderBoardStatus={setCurrentTenderBoardStatus}/>
                </div>
              </div>
              <TenderResultSidebar 
                result={selectedResult} 
                drawerRef={drawerRef}
                allResults={allResults} 
                setAllResults={setAllResults}
                onFilePreview={openFilePreview}
                tenderBoardStatus={currentTenderBoardStatus}
              />
            </div>
            
            {/* FilePreview Modal */}
            {isPreviewOpen && previewFile && (
                <FilePreview
                    file={previewFile}
                    onClose={closeFilePreview}
                />
            )}
        </>
    );
};

export default TenderAnalysis;
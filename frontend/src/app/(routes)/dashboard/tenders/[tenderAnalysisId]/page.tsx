"use client"
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import TenderHeader from "@/components/dashboard/tenders/TenderHeader";
import TendersList from "@/components/dashboard/tenders/TendersList";
import TenderResultSidebar from "@/components/dashboard/tenders/TenderResultSidebar";
import { useTender } from "@/context/TenderContext";
import { Loader2 } from "lucide-react";
import { TenderAnalysisResult } from "@/types/tenders";
const TenderAnalysis = () => {
    const { tenderAnalysisId } = useParams();
    const { fetchAnalysisById, selectedResult } = useTender();
    const [fetching, setFetching] = useState(true);
    const drawerRef = useRef<{ setVisibility: (value: boolean) => void }>(null);
    const [allResults, setAllResults] = useState<TenderAnalysisResult[]>([]);
    
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

    if (fetching) {
        return (
            <div className="flex w-full h-screen items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </div>
        );
    }

    return (
        <div className="w-full flex h-[100svh] overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            <div className="flex-none">
              <TenderHeader />
            </div>
            <div className="flex-1 overflow-auto scrollbar-hide">
              <TendersList allResults={allResults} setAllResults={setAllResults} drawerRef={drawerRef} />
            </div>
          </div>
          <TenderResultSidebar 
            result={selectedResult} 
            drawerRef={drawerRef}
            allResults={allResults} setAllResults={setAllResults}
          />
        </div>
    );
};

export default TenderAnalysis;
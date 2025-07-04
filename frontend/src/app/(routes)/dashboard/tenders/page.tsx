"use client"
import { SetStateAction, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import TendersList from "@/components/dashboard/tenders/TendersList";
import { Button } from "@/components/ui/button";
import { useTender } from "@/context/TenderContext";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TenderAnalysisCreateForm } from "@/components/dashboard/tenders/forms/TenderAnalysisCreationForm";
import { AnalysisCriteria, TenderAnalysisResult } from "@/types/tenders";
import { useTranslations } from 'next-intl';

const Tenders = () => {
    const { analyses, fetchAnalyses, setSelectedAnalysis, isLoading } = useTender();
    const [openForm, setOpenForm] = useState(false);
    const router = useRouter();
    const [initialized, setInitialized] = useState(false);
    const drawerRef = useRef<{ setVisibility: (value: boolean) => void }>(null);
    const { createAnalysis } = useTender();
    const [currentTenderBoardStatus, setCurrentTenderBoardStatus] = useState<string | null>(null);

    // Translation hooks
    const t = useTranslations('dashboard.tenders');
    const tCommon = useTranslations('common');

    useEffect(() => {
        if (!initialized) {
            const initializeAnalyses = async () => {
                await fetchAnalyses();
                setInitialized(true);
            };
            initializeAnalyses();
        }
    }, [fetchAnalyses, initialized]);

    const handleCreateAnalysis = async (values: {
        name: string;
        company_description: string;
        search_phrase: string;
        sources: string[];
        criteria: AnalysisCriteria[];
    }) => {
        const transformedData = {
            ...values,
            criteria: values.criteria.map(criterion => ({
              name: criterion.name,
              description: criterion.description || "",
              weight: criterion.weight,
              is_disqualifying: criterion.is_disqualifying || false,
              exclude_from_score: criterion.exclude_from_score || false,
              instruction: criterion.instruction || "",
              subcriteria: criterion.subcriteria || [],
              keywords: criterion.keywords || undefined,
            })),
        };
      
        await createAnalysis(transformedData);
        setOpenForm(false);
    };
    
    useEffect(() => {
        if (initialized && !isLoading && analyses.length > 0) {
            const firstAnalysis = analyses[0];
            setSelectedAnalysis(firstAnalysis);
            router.push(`/dashboard/tenders/${firstAnalysis._id}`);
        }
    }, [initialized, analyses.length]);

    if (isLoading || !initialized) {
        return (
            <div className="flex w-full h-screen items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </div>
        );
    }

    if (!isLoading && analyses.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-[calc(100vh-4rem)] w-full">
                <h2 className="text-xl font-semibold mb-4">{t('no_searches')}</h2>
                {openForm && (
                    <>
                        <div 
                            className="fixed inset-0 bg-foreground/50 z-50 overflow-y-auto scrollbar-hide py-20"
                            onClick={() => setOpenForm(false)}
                        >
                            <div 
                                className="bg-background rounded-lg w-full max-w-xl mx-auto my-auto"
                                onClick={e => e.stopPropagation()}
                            >
                                <div className="p-6 pb-0">
                                    <h2 className="text-lg font-semibold">
                                        {t('create_new_tender_search')}
                                    </h2>
                                </div>
                                <TenderAnalysisCreateForm 
                                    onSubmit={handleCreateAnalysis}
                                    onCancel={() => setOpenForm(false)}
                                    isLoading={isLoading}
                                />
                            </div>
                        </div>
                    </>
                )}
                <Button onClick={() => setOpenForm(true)}>
                    {t('create_new_search')}
                </Button>
            </div>
        );
    }

    return (
        <div>
            <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-auto scrollbar-hide">
                    <TendersList 
                        drawerRef={drawerRef} allResults={[]}
                        setAllResults={function (value: SetStateAction<TenderAnalysisResult[]>): void {
                            console.log("");
                        } }
                        setCurrentTenderBoardStatus={setCurrentTenderBoardStatus} isDrawerVisible={false} onDrawerVisibilityChange={function (visible: boolean): void {
                            throw new Error("Function not implemented.");
                        } } />
                </div>
            </div>
        </div>
    );
};

export default Tenders;
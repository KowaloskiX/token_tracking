"use client";

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Plus, ExternalLink } from 'lucide-react';
import { useTendersTranslations, useCommonTranslations } from '@/hooks/useTranslations';
import { TenderAnalysisResult } from '@/types/tenders';

interface SingleTenderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  analysisId: string;
  onAnalysisStart?: (pendingTender: TenderAnalysisResult) => void;
  onAnalysisComplete?: (completedTender: TenderAnalysisResult, pendingTenderId?: string) => void;
  onAnalysisError?: (pendingTenderId: string) => void;
  onRefreshData?: () => void; // ✅ NEW: Add refresh callback
}

interface SingleTenderAnalysisRequest {
  tender_url: string;
  analysis_id: string;
  save_to_db: boolean;
}

export function SingleTenderDialog({
  open,
  onOpenChange,
  analysisId,
  onAnalysisStart,
  onAnalysisComplete,
  onAnalysisError,
  onRefreshData // ✅ NEW: Accept refresh callback
}: SingleTenderDialogProps) {
  const [tenderUrl, setTenderUrl] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const t = useTendersTranslations();
  const commonT = useCommonTranslations();

  const validateUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const generatePendingTender = (url: string): TenderAnalysisResult => {
    const pendingId = `pending_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    return {
      _id: pendingId,
      user_id: "",
      tender_analysis_id: analysisId,
      tender_url: url,
      source: "unknown",
      tender_score: 0,
      tender_metadata: {
        name: "", // ✅ CHANGED: Empty for skeleton
        organization: "", // ✅ CHANGED: Empty for skeleton
        submission_deadline: "",
        procedure_type: ""
      },
      criteria_analysis: [],
      company_match_explanation: "",
      assistant_id: "",
      updates: [],
      uploaded_files: [],
      status: 'active',
      updated_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      opened_at: "",
      order_number: "000",
      isPending: true // ✅ This triggers skeleton rendering
    } as TenderAnalysisResult & { isPending: boolean };
  };

  const handleAnalyze = async () => {
    if (!tenderUrl.trim()) {
      setError(t('tenders.singleAnalysis.urlRequired'));
      return;
    }

    if (!validateUrl(tenderUrl.trim())) {
      setError(t('tenders.singleAnalysis.invalidUrl'));
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    // Create pending tender and add to list immediately
    const pendingTender = generatePendingTender(tenderUrl.trim());
    onAnalysisStart?.(pendingTender);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication token not found');
      }

      const requestBody: SingleTenderAnalysisRequest = {
        tender_url: tenderUrl.trim(),
        analysis_id: analysisId,
        save_to_db: true
      };

      console.log('Starting single tender analysis:', requestBody);

      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/analyze-single-tender`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      console.log('Single tender analysis result:', result);

      if (result.status === 'success' && result.result) {
        const completedTender: TenderAnalysisResult = {
          ...result.result,
          _id: result.result._id || result.result.id,
          isPending: undefined
        };

        // ✅ UPDATED: Replace pending tender first
        onAnalysisComplete?.(completedTender, pendingTender._id);
        
        // ✅ NEW: Trigger data refresh after a short delay to ensure DB persistence
        setTimeout(() => {
          console.log('Refreshing data to ensure persistence...');
          onRefreshData?.();
        }, 1000);
        
        // Close dialog and reset form
        onOpenChange(false);
        setTenderUrl('');
        setError(null);
      } else {
        throw new Error(result.message || 'Analysis failed');
      }

    } catch (err) {
      console.error('Error analyzing single tender:', err);
      setError(err instanceof Error ? err.message : t('tenders.singleAnalysis.analysisError'));
      
      // Remove pending tender from list on error
      onAnalysisError?.(pendingTender._id!);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleClose = () => {
    // ✅ FIXED: Allow closing even during analysis
    onOpenChange(false);
    setTenderUrl('');
    setError(null);
    
    // If analysis is running, we still close but let it complete in background
    if (isAnalyzing) {
      console.log('Dialog closed during analysis - analysis continues in background');
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" />
            {t('tenders.singleAnalysis.title')}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="tender-url">{t('tenders.singleAnalysis.urlLabel')}</Label>
            <Input
              id="tender-url"
              type="url"
              placeholder={t('tenders.singleAnalysis.urlPlaceholder')}
              value={tenderUrl}
              onChange={(e) => setTenderUrl(e.target.value)}
              disabled={isAnalyzing}
              className="w-full"
            />
            <p className="text-sm text-muted-foreground">
              {t('tenders.singleAnalysis.urlHelper')}
            </p>
          </div>

          {error && (
            <div className="p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
              {error}
            </div>
          )}

          {isAnalyzing && (
            <div className="p-3 text-sm text-primary bg-secondary border border-secondary-border rounded-md flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('tenders.singleAnalysis.analyzing')}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={handleClose}
            // ✅ FIXED: Can always close dialog
          >
            {commonT('cancel')}
          </Button>
          <Button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !tenderUrl.trim()}
            className="min-w-[120px]"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                {t('tenders.singleAnalysis.analyzing')}
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('tenders.singleAnalysis.analyze')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
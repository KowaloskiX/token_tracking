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
import { Loader2, Plus } from 'lucide-react';
import { useTendersTranslations, useCommonTranslations } from '@/hooks/useTranslations';
import { TenderAnalysisResult } from '@/types/tenders';

interface SingleTenderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  analysisId: string;
  onAnalysisStart?: (pendingTender: TenderAnalysisResult) => void;
  onAnalysisComplete?: (completedTender: TenderAnalysisResult, pendingTenderId?: string) => void;
  onAnalysisError?: (pendingTenderId: string) => void;
  onRefreshData?: () => void;
}

interface SingleTenderAnalysisRequest {
  tender_url: string;
  analysis_id: string;
  save_to_db: boolean;
}

// ✅ NEW: Track active analyses by URL to prevent duplicates
const activeAnalyses = new Set<string>();

export function SingleTenderDialog({
  open,
  onOpenChange,
  analysisId,
  onAnalysisStart,
  onAnalysisComplete,
  onAnalysisError,
  onRefreshData
}: SingleTenderDialogProps) {
  const [tenderUrl, setTenderUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false); // ✅ CHANGED: Renamed from isAnalyzing
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
        name: "",
        organization: "",
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
      isPending: true
    } as TenderAnalysisResult & { isPending: boolean };
  };

  const handleAnalyze = async () => {
    const trimmedUrl = tenderUrl.trim();
    
    if (!trimmedUrl) {
      setError(t('tenders.singleAnalysis.urlRequired'));
      return;
    }

    if (!validateUrl(trimmedUrl)) {
      setError(t('tenders.singleAnalysis.invalidUrl'));
      return;
    }

    // ✅ NEW: Check if this URL is already being analyzed
    if (activeAnalyses.has(trimmedUrl)) {
      setError(t('tenders.singleAnalysis.alreadyAnalyzing') || 'This tender is already being analyzed');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    // ✅ NEW: Add URL to active analyses
    activeAnalyses.add(trimmedUrl);

    // Create pending tender and add to list immediately
    const pendingTender = generatePendingTender(trimmedUrl);
    onAnalysisStart?.(pendingTender);

    // ✅ IMPORTANT: Reset form and close dialog immediately
    setTenderUrl('');
    setError(null);
    setIsSubmitting(false); // ✅ RESET: Allow immediate next submission
    onOpenChange(false);

    // ✅ START: Background analysis (no await - fire and forget)
    analyzeInBackground(trimmedUrl, pendingTender);
  };

  // ✅ NEW: Separate background analysis function
  const analyzeInBackground = async (url: string, pendingTender: TenderAnalysisResult) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication token not found');
      }

      const requestBody: SingleTenderAnalysisRequest = {
        tender_url: url,
        analysis_id: analysisId,
        save_to_db: true
      };

      console.log('Starting background tender analysis:', requestBody);

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

      console.log('Background tender analysis completed:', result);

      if (result.status === 'success' && result.result) {
        const completedTender: TenderAnalysisResult = {
          ...result.result,
          _id: result.result._id || result.result.id,
          isPending: undefined
        };

        // Replace pending tender with completed one
        onAnalysisComplete?.(completedTender, pendingTender._id);
        
        // Trigger data refresh after completion
        // setTimeout(() => {
        //   console.log('Refreshing data after background analysis...');
        //   onRefreshData?.();
        // }, 1000);
      } else {
        throw new Error(result.message || 'Analysis failed');
      }

    } catch (err) {
      console.error('Background tender analysis failed:', err);
      
      // Remove pending tender from list on error
      onAnalysisError?.(pendingTender._id!);
      
      // ✅ TODO: Show toast notification for error since dialog is closed
      // You might want to implement a toast system here
      
    } finally {
      // ✅ CLEANUP: Remove URL from active analyses
      activeAnalyses.delete(url);
    }
  };

  const handleClose = () => {
    onOpenChange(false);
    setTenderUrl('');
    setError(null);
    setIsSubmitting(false); // ✅ RESET: Clear any pending submission state
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
              disabled={isSubmitting} // ✅ CHANGED: Only disable during submission
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

          {/* ✅ UPDATED: Show active analyses count with translation */}
          {activeAnalyses.size > 0 && (
            <div className="p-3 text-sm text-primary bg-secondary border border-secondary-border rounded-md flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('tenders.singleAnalysis.analyzingInBackground', { count: activeAnalyses.size })}
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
            disabled={isSubmitting || !tenderUrl.trim()} // ✅ CHANGED: Only disable during submission
            className="min-w-[100px]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                {t('tenders.singleAnalysis.submitting') || 'Adding...'}
              </>
            ) : (
              t('tenders.singleAnalysis.analyze')
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
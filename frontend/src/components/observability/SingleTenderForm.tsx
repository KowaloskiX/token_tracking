"use client"
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Target, Play, Info } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface SingleTenderFormProps {
  tenderUrl: string;
  setTenderUrl: (value: string) => void;
  analysisId: string;
  setAnalysisId: (value: string) => void;
  loading: boolean;
  onRunAnalysis: () => void;
}

export function SingleTenderForm({
  tenderUrl,
  setTenderUrl,
  analysisId,
  setAnalysisId,
  loading,
  onRunAnalysis,
}: SingleTenderFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5" />
          Single Tender Analysis
        </CardTitle>
        <CardDescription>
          Analyze a specific tender using an existing analysis configuration
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label htmlFor="tender-url">Tender URL</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Direct URL to the tender detail page</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Textarea
            id="tender-url"
            placeholder="https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-..."
            value={tenderUrl}
            onChange={(e) => setTenderUrl(e.target.value)}
            className="min-h-[80px]"
            disabled={loading}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label htmlFor="analysis-id">Browser ID</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>
                <p>ID of the analysis configuration to use for evaluation</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Input
            id="analysis-id"
            placeholder="60f7c8e4a4b3f12d34567890"
            value={analysisId}
            onChange={(e) => setAnalysisId(e.target.value)}
            disabled={loading}
          />
        </div>

        <Button 
          onClick={onRunAnalysis} 
          disabled={loading || !tenderUrl.trim() || !analysisId.trim()}
          className="w-full"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          Analyze Tender
        </Button>

        <Button 
          onClick={() => {
            setTenderUrl('');
            setAnalysisId('');
          }}
          variant="outline"
          className="w-full"
          disabled={loading}
        >
          Clear Form
        </Button>
      </CardContent>
    </Card>
  );
}
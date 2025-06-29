"use client"
import { useState, useEffect } from 'react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { HistoryTable } from '@/components/observability/HistoryTable';
import { useToast } from '@/hooks/use-toast';

interface HistoryItem {
  id: string;
  timestamp: string;
  endpoint: 'search' | 'filter';
  status: 'success' | 'warning' | 'error';
  params: any;
  results?: any;
}

export default function HistoryPage() {
  const { toast } = useToast();
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Load history from localStorage on component mount
  useEffect(() => {
    const savedHistory = localStorage.getItem('observability-history');
    if (savedHistory) {
      try {
        const parsedHistory = JSON.parse(savedHistory);
        setHistory(parsedHistory);
      } catch (error) {
        console.error('Error parsing saved history:', error);
      }
    }
  }, []);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied",
      description: "ID has been copied to clipboard"
    });
  };

  return (
    <TooltipProvider>
      <HistoryTable history={history} onCopyId={copyToClipboard} />
    </TooltipProvider>
  );
}
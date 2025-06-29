"use client"
import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { FileText, Download, AlertCircle } from 'lucide-react';
import JSZip from 'jszip';
import { TenderAnalysisResult } from '@/types/tenders';
import { FileData } from '@/types';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderFilesCardProps {
  tender: TenderAnalysisResult;
}

export default function TenderFilesCard({ tender }: TenderFilesCardProps) {
  const t = useTendersTranslations();
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadAllFiles = async () => {
    if (!tender?.uploaded_files || tender.uploaded_files.length === 0) {
      return;
    }
    
    setIsDownloading(true);
    
    try {
      const files = tender.uploaded_files;
      const zip = new JSZip();
      
      for (const file of files) {
        const downloadUrl = file.blob_url || file.url;
        if (downloadUrl) {
          const response = await fetch(downloadUrl);
          const blob = await response.blob();
          zip.file(file.filename, blob);
        }
      }
      
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(zipBlob);
      a.download = `${tender.tender_metadata?.name || 'tender'}_pliki.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (error) {
      console.error('Błąd pobierania plików:', error);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownloadFile = async (file: FileData) => {
    try {
      const downloadUrl = file.blob_url || file.url;
      if (downloadUrl) {
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = file.filename;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Błąd pobierania pliku:', error);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('tenders.files.title')}
          </CardTitle>
          {tender.uploaded_files && tender.uploaded_files.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadAllFiles}
              disabled={isDownloading}
            >
              {isDownloading ? (
                <>
                  <span className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin mr-2" />
                  {t('tenders.files.downloading')}
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  {t('tenders.files.downloadAll')}
                </>
              )}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {tender.uploaded_files && tender.uploaded_files.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {tender.uploaded_files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-md bg-secondary/30 border border-neutral-200 hover:bg-secondary/50 transition-colors"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate" title={file.filename}>
                      {file.filename}
                    </p>
                    <Badge variant="outline" className="text-xs mt-1">
                      {file.filename.split('.').pop()?.toUpperCase() || "DOC"}
                    </Badge>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDownloadFile(file)}
                  className="h-7 w-7 p-0 flex-shrink-0 ml-2"
                >
                  <Download className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('tenders.files.noFiles')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
"use client"
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertCircle, CheckCircle2, Archive, Settings } from 'lucide-react';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderStatusCardProps {
  status: string;
  onStatusChange: (status: string) => void;
  tenderBoardStatus?: string | null;
}

export default function TenderStatusCard({ status, onStatusChange, tenderBoardStatus }: TenderStatusCardProps) {
  const t = useTendersTranslations();

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'inactive':
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
      case 'active':
        return <CheckCircle2 className="h-4 w-4 text-green-600/80" />;
      case 'archived':
        return <Archive className="h-4 w-4 text-gray-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    // Show kanban board name if tender is in a board
    if (tenderBoardStatus) {
      return <Badge variant="outline" className="border-transparent bg-secondary-hover text-primary shadow">{tenderBoardStatus}</Badge>;
    }

    switch (status) {
      case 'inactive':
        return <Badge variant="outline" className="border-gray-400 text-gray-600 font-normal">{t('tenders.status.inactive')}</Badge>;
      case 'active':
        return <Badge variant="default" className="bg-green-600/80 hover:bg-green-600 font-normal">{t('tenders.status.active')}</Badge>;
      case 'archived':
        return <Badge variant="secondary" className="bg-secondary text-primary/70 hover:bg-secondary font-normal">{t('tenders.status.archived')}</Badge>;
      default:
        return <Badge variant="outline">{t('tenders.status.unknown')}</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          {t('tenders.status.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {getStatusIcon(status)}
            <Label htmlFor="tender-status" className="text-sm font-normal">
              {t('tenders.status.status')}:
            </Label>
          </div>
          <div className="flex-grow">
            <Select 
              value={status} 
              onValueChange={onStatusChange}
            >
              <SelectTrigger id="tender-status" className="w-48">
                <SelectValue placeholder={t('tenders.status.selectStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inactive">{t('tenders.status.inactive')}</SelectItem>
                <SelectItem value="active">{t('tenders.status.active')}</SelectItem>
                <SelectItem value="archived">{t('tenders.status.archived')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            {getStatusBadge(status)}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
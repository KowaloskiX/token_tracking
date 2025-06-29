"use client"
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Building, Calendar, Percent, Globe, Flag, MapPin, Info } from 'lucide-react';
import { TenderAnalysisResult } from '@/types/tenders';
import { useTendersTranslations } from '@/hooks/useTranslations';

interface TenderInfoCardProps {
  tender: TenderAnalysisResult;
}

export default function TenderInfoCard({ tender }: TenderInfoCardProps) {
  const t = useTendersTranslations();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="h-5 w-5" />
          {t('info.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Building className="h-4 w-4 text-gray-500" />
              <h3 className="text-sm font-medium text-muted-foreground">{t('tenders.details.client')}</h3>
            </div>
            <p className="text-sm">
              {tender.tender_metadata?.organization || t('tenders.info.notSpecified')}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-gray-500" />
              <h3 className="text-sm font-medium text-muted-foreground">{t('tenders.details.submissionDeadline')}</h3>
            </div>
            <p className="text-sm">
              {tender.tender_metadata?.submission_deadline || t('tenders.info.notSpecified')}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Percent className="h-4 w-4 text-gray-500" />
              <h3 className="text-sm font-medium text-muted-foreground">{t('tenders.details.relevance')}</h3>
            </div>
            <p className="text-sm">
              {tender.tender_score !== undefined ? (
                `${(tender.tender_score * 100).toFixed(1)}%`
              ) : (
                t('tenders.info.notSpecified')
              )}
            </p>
          </div>
        </div>

        {tender.location && (
          <div className="mt-6 pt-6 border-t border-gray-100">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {tender.location.country && tender.location.country !== "UNKNOWN" && (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-gray-400" />
                    <span className="text-sm font-medium text-muted-foreground">{t('tenders.details.country')}</span>
                  </div>
                  <span className="text-sm">
                    {tender.location.country}
                  </span>
                </div>
              )}
              {tender.location.voivodeship && tender.location.voivodeship !== "UNKNOWN" && (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Flag className="h-4 w-4 text-gray-400" />
                    <span className="text-sm font-medium text-muted-foreground">{t('tenders.details.voivodeship')}</span>
                  </div>
                  <span className="text-sm">
                    {tender.location.voivodeship}
                  </span>
                </div>
              )}
              {tender.location.city && tender.location.city !== "UNKNOWN" && (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-gray-400" />
                    <span className="text-sm font-medium text-muted-foreground">{t('tenders.details.city')}</span>
                  </div>
                  <span className="text-sm">
                    {tender.location.city}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
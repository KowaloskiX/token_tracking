import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Card } from '@/components/ui/card';
import { Trophy, ChevronDown, CheckCircle2, CalendarCheck, Users, Link as LinkIcon } from 'lucide-react';
import Link from 'next/link';
import React from 'react';

interface HistoricalTenderData {
  id: string;
  score: number;
  metadata: {
    additional_cpv_codes?: string;
    completion_status?: string;
    contract_date?: string;
    contract_value?: string;
    highest_price?: string;
    initiation_date?: string;
    location?: string;
    lowest_price?: string;
    main_cpv_code?: string;
    name?: string;
    organization?: string;
    original_tender_url?: string;
    realization_period?: string;
    sme_offers?: number;
    submission_deadline?: string;
    total_offers?: number;
    total_parts?: number;
    winner_location?: string;
    winner_name?: string;
    winner_size?: string;
    winning_price?: string;
  };
}

interface TenderHistoricalDataCardProps {
  historicalTenderData: HistoricalTenderData | null;
  isLoadingHistoricalData: boolean;
  t: any;
}

export const TenderHistoricalDataCard: React.FC<TenderHistoricalDataCardProps> = ({ historicalTenderData, isLoadingHistoricalData, t }) => {
  if (!isLoadingHistoricalData && !historicalTenderData) return null;

  return (
    <div className="space-y-4">
      <Collapsible>
        <div className="group">
          <CollapsibleTrigger asChild>
            <div 
              data-state="closed"
              className="flex overflow-hidden items-center gap-2 py-3 px-4 transition-all duration-200 border border-secondary-border shadow-sm bg-secondary/50 w-full hover:bg-secondary-hover rounded-lg cursor-pointer"
            >
              <Card className="bg-primary/10 p-2 relative rounded-md flex-shrink-0 border border-primary/20">
                <Trophy className="w-5 h-5 shrink-0 text-primary" />
              </Card>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-primary">
                  {isLoadingHistoricalData 
                    ? t('tenders.completion.loadingData')
                    : t('tenders.completion.title')
                  }
                </p>
              </div>
              {!isLoadingHistoricalData && (
                <ChevronDown 
                  className="w-4 h-4 flex-shrink-0 text-primary transition-transform duration-200 group-data-[state=open]:rotate-180 ml-2" 
                />
              )}
              {isLoadingHistoricalData && (
                <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin ml-2" />
              )}
            </div>
          </CollapsibleTrigger>
        </div>
        {!isLoadingHistoricalData && historicalTenderData && (
          <CollapsibleContent>
            <div className="border border-t-0 border-secondary-border bg-secondary/30 px-4 py-4 rounded-b-xl space-y-4">
              {/* Completion Status */}
              {historicalTenderData.metadata.completion_status && (
                <div className="flex items-center gap-3 p-3 bg-background rounded-lg border border-secondary-border">
                  <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-primary mb-1">{t('tenders.completion.completionStatus')}</p>
                    <p className="text-sm text-foreground">{historicalTenderData.metadata.completion_status}</p>
                  </div>
                </div>
              )}
              {/* Winner Information */}
              {historicalTenderData.metadata.winner_name && (
                <div className="space-y-3">
                  <h4 className="font-medium text-primary flex items-center gap-2">
                    <Trophy className="h-4 w-4" />
                    {t('tenders.completion.winnerInformation')}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 bg-background rounded-lg border border-secondary-border">
                      <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.winner')}</p>
                      <p className="text-sm text-foreground">{historicalTenderData.metadata.winner_name}</p>
                    </div>
                    {historicalTenderData.metadata.winner_location && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.location')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.winner_location}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.winner_size && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.companySize')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.winner_size}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.winning_price && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.winningPrice')}</p>
                        <p className="text-sm font-medium text-foreground">{historicalTenderData.metadata.winning_price}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* Contract Information */}
              {(historicalTenderData.metadata.contract_value || historicalTenderData.metadata.contract_date || historicalTenderData.metadata.realization_period) && (
                <div className="space-y-3">
                  <h4 className="font-medium text-primary flex items-center gap-2">
                    <CalendarCheck className="h-4 w-4" />
                    {t('tenders.completion.contractDetails')}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {historicalTenderData.metadata.contract_value && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.contractValue')}</p>
                        <p className="text-sm font-medium text-foreground">{historicalTenderData.metadata.contract_value}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.contract_date && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.contractDate')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.contract_date}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.realization_period && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border sm:col-span-2">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.realizationPeriod')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.realization_period}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* Bidding Information */}
              {(historicalTenderData.metadata.total_offers || historicalTenderData.metadata.sme_offers || historicalTenderData.metadata.highest_price || historicalTenderData.metadata.lowest_price) && (
                <div className="space-y-3">
                  <h4 className="font-medium text-primary flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    {t('tenders.completion.biddingStatistics')}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {historicalTenderData.metadata.total_offers && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.totalOffers')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.total_offers}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.sme_offers && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.smeOffers')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.sme_offers}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.highest_price && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.highestPrice')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.highest_price}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.lowest_price && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.lowestPrice')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.lowest_price}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* Additional Information */}
              {(historicalTenderData.metadata.main_cpv_code || historicalTenderData.metadata.additional_cpv_codes) && (
                <div className="space-y-3">
                  <h4 className="font-medium text-primary">{t('tenders.completion.cpvCodes')}</h4>
                  <div className="space-y-2">
                    {historicalTenderData.metadata.main_cpv_code && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.mainCpv')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.main_cpv_code}</p>
                      </div>
                    )}
                    {historicalTenderData.metadata.additional_cpv_codes && (
                      <div className="p-3 bg-background rounded-lg border border-secondary-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">{t('tenders.completion.additionalCpv')}</p>
                        <p className="text-sm text-foreground">{historicalTenderData.metadata.additional_cpv_codes}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* Link to original tender */}
              {historicalTenderData.metadata.original_tender_url && (
                <div className="pt-3 border-t border-secondary-border">
                  <Link
                    href={historicalTenderData.metadata.original_tender_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary-hover font-medium transition-colors"
                  >
                    <LinkIcon className="h-4 w-4" />
                    {t('tenders.completion.viewOriginalTender')}
                  </Link>
                </div>
              )}
            </div>
          </CollapsibleContent>
        )}
      </Collapsible>
    </div>
  );
};

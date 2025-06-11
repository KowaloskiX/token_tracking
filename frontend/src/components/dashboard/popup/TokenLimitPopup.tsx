import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertCircle, ChevronsUp } from "lucide-react";
import { createCheckoutSession } from '@/utils/stripe';
import { Icons } from "@/components/ui/icons";
import { useTranslations } from 'next-intl';

const TokenLimitDialog = ({setTokenLimitError, tokenLimitError}: any) => {
    const [isLoading, setIsLoading] = useState(false);
    
    // Translation hooks
    const t = useTranslations('errors.token_limit');
    const tCommon = useTranslations('common');

    const formatResetTime = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            hour12: true
        });
    };

    const handleUpgrade = async () => {
        try {
            setIsLoading(true);
            
            // Fetch price IDs from your backend
            const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/prices`);
            if (!response.ok) {
                throw new Error('Failed to fetch price IDs');
            }
            const priceIds = await response.json();
            
            const origin = window.location.origin;
            
            // Create checkout session for monthly plan
            await createCheckoutSession(
                priceIds.monthly,
                'monthly',
                `${origin}/dashboard/tenders/chat`,
                `${origin}/dashboard/tenders/chat?error=payment`
            );
        } catch (error) {
            console.error('Checkout error:', error);
            // You might want to show an error toast here
        } finally {
            setIsLoading(false);
        }
    };
    
    return (
        <Dialog open={!!tokenLimitError} onOpenChange={() => setTokenLimitError(null)}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="flex items-center gap-2">
                        <AlertCircle className="h-5 w-5" />
                        <DialogTitle>{t('title')}</DialogTitle>
                    </div>
                </DialogHeader>
                <div className="flex flex-col gap-4">
                    <div className="space-y-2">
                        <div className="text-base">
                            {t('description')}
                        </div>
                        <div className="mt-2 space-y-1">
                            <p className="text-sm text-muted-foreground">
                                {t('reset_time')} {tokenLimitError?.next_reset ? formatResetTime(tokenLimitError.next_reset) : t('unknown_reset')}
                            </p>
                        </div>
                    </div>
                </div>
                <Button 
                    onClick={handleUpgrade}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                            {tCommon('loading')}
                        </>
                    ) : (
                        <>
                            <ChevronsUp className="mr-2 h-4 w-4" />
                            {t('upgrade_plan')}
                        </>
                    )}
                </Button>
                <Button 
                    variant="outline" 
                    onClick={() => window.location.href = '/oferta'}
                    disabled={isLoading}
                >
                    {t('check_pricing')}
                </Button>
            </DialogContent>
        </Dialog>
    );
};

export default TokenLimitDialog;
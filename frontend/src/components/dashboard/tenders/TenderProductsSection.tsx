import React, { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { 
    FileText, 
    ChevronDown,
    Box
} from "lucide-react";
import { Card } from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { useTendersTranslations } from '@/hooks/useTranslations';

interface Product {
    name: string;
    citations: Array<{
        text: string;
        filename: string;
    }>;
}

interface TenderProductsSectionProps {
    products?: Product[];
    onCitationClick?: (citation: { text: string; filename: string }) => void;
}

const TenderProductsSection: React.FC<TenderProductsSectionProps> = ({ 
    products, 
    onCitationClick 
}) => {
    const t = useTendersTranslations();
    const [scrollState, setScrollState] = useState({
        canScrollUp: false,
        canScrollDown: false
    });
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Hardcoded data for now - will be replaced with real data later
    const defaultProducts: Product[] = [
        {
            name: "Software Development Services",
            citations: [
                { text: "The contractor shall provide comprehensive software development services including web applications, mobile applications, and desktop solutions.", filename: "Document_1.pdf" },
                { text: "All software development must follow industry best practices and include proper documentation, testing, and deployment procedures.", filename: "Requirements_Spec.docx" }
            ]
        },
        {
            name: "Cloud Infrastructure Solutions",
            citations: [
                { text: "The solution must include scalable cloud infrastructure with automated deployment, monitoring, and backup capabilities.", filename: "Technical_Requirements.pdf" }
            ]
        },
        {
            name: "Database Management Systems",
            citations: [
                { text: "Database systems must support high availability, automatic failover, and real-time replication across multiple geographic locations.", filename: "Database_Specs.pdf" },
                { text: "The database solution should include advanced security features, encryption at rest and in transit, and comprehensive audit logging.", filename: "Technical_Requirements.pdf" }
            ]
        },
        {
            name: "IT Consulting Services",
            citations: [
                { text: "IT consulting services shall include strategic planning, technology roadmap development, and change management support.", filename: "Project_Overview.pdf" }
            ]
        },
        {
            name: "Cybersecurity Solutions",
            citations: [
                { text: "Cybersecurity implementation must include threat detection, incident response, vulnerability management, and security awareness training.", filename: "Security_Requirements.pdf" },
                { text: "The security solution should provide 24/7 monitoring, automated threat response, and compliance reporting for industry standards.", filename: "Technical_Requirements.pdf" }
            ]
        },
        {
            name: "Data Analytics Platform",
            citations: [
                { text: "The analytics platform must support real-time data processing, machine learning capabilities, and interactive dashboard creation.", filename: "Analytics_Spec.pdf" }
            ]
        }
    ];

    const productsToShow = products || defaultProducts;
    const productCount = productsToShow.length;

    const handleCitationClick = (citation: { text: string; filename: string }) => {
        if (onCitationClick) {
            onCitationClick(citation);
        } else {
            console.log('Open citation:', citation);
        }
    };

    const handleScroll = () => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const canScrollUp = scrollTop > 0;
        const canScrollDown = scrollTop < scrollHeight - clientHeight;

        setScrollState({ canScrollUp, canScrollDown });
    };

    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        // Initial check
        handleScroll();

        container.addEventListener('scroll', handleScroll);
        
        // Also check after a short delay to ensure content is rendered
        const timeoutId = setTimeout(() => {
            handleScroll();
        }, 100);

        return () => {
            container.removeEventListener('scroll', handleScroll);
            clearTimeout(timeoutId);
        };
    }, []);

    const truncateText = (text: string, maxWords: number = 8): string => {
        const words = text.split(' ');
        if (words.length <= maxWords) return text;
        return words.slice(0, maxWords).join(' ') + '...';
    };

    if (!productsToShow.length) {
        return (
            <div className="space-y-4">
                <div className="p-4 text-center text-muted-foreground">
                    <p className="text-sm">{t('tenders.products.noProducts')}</p>
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-4">
            <Collapsible>
                <CollapsibleTrigger asChild>
                    <div 
                        className="group flex overflow-hidden items-center gap-2 py-3 px-4 transition-all duration-200 border border-secondary-border shadow-sm bg-white/10 w-full hover:bg-background rounded-lg cursor-pointer"
                    >
                        <Card className="bg-background p-2 relative rounded-md flex-shrink-0 border border-secondary-border">
                            <div className="absolute w-2 h-2 rounded-full bg-green-600 right-0 top-0 transform translate-x-1 -translate-y-1" />
                            <Box className="w-4 h-4 shrink-0 text-muted-foreground" />
                        </Card>
                        
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-primary">
                                {t('tenders.products.title')}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                {t('tenders.products.subtitle')}
                            </p>
                        </div>
                        
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs font-medium bg-background">
                                {productCount}
                            </Badge>
                            <ChevronDown 
                                className="w-4 h-4 flex-shrink-0 text-primary transition-transform duration-200 group-data-[state=open]:rotate-180" 
                            />
                        </div>
                    </div>
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <div className="border border-t-0 border-secondary-border bg-background px-4 py-4 rounded-b-xl">
                        <div className="relative">
                            {/* Top gradient fade */}
                            <div 
                                className={`absolute top-0 left-0 right-0 h-12 z-10 pointer-events-none transition-opacity duration-300 ${
                                    scrollState.canScrollUp ? 'opacity-100' : 'opacity-0'
                                }`}
                                style={{
                                    background: 'linear-gradient(to bottom, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 50%, transparent 100%)'
                                }}
                            />
                            
                            {/* Bottom gradient fade */}
                            <div 
                                className={`absolute bottom-0 left-0 right-0 h-12 z-10 pointer-events-none transition-opacity duration-300 ${
                                    scrollState.canScrollDown ? 'opacity-100' : 'opacity-0'
                                }`}
                                style={{
                                    background: 'linear-gradient(to top, hsl(var(--background)) 0%, hsl(var(--background) / 0.8) 50%, transparent 100%)'
                                }}
                            />
                            
                            <div 
                                ref={scrollContainerRef}
                                className="space-y-3 max-h-96 overflow-y-auto scrollbar-brown-visible"
                            >
                                {productsToShow.map((product, index) => (
                                    <Collapsible key={index}>
                                        <CollapsibleTrigger asChild>
                                            <div className="group bg-background rounded-lg border border-secondary-border p-4 hover:bg-secondary/20 transition-colors cursor-pointer">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-start gap-3">
                                                        <div className="w-2 h-2 rounded-full bg-green-600 mt-2 flex-shrink-0" />
                                                        <div className="flex-1 min-w-0">
                                                            <h4 className="font-medium text-sm text-primary">
                                                                {product.name}
                                                            </h4>
                                                            <p className="text-xs text-muted-foreground mt-1">
                                                                {product.citations.length} {product.citations.length === 1 ? t('tenders.products.citation') : t('tenders.products.citationPlural')}
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <ChevronDown className="w-4 h-4 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180" />
                                                </div>
                                            </div>
                                        </CollapsibleTrigger>
                                        <CollapsibleContent>
                                            <div className="bg-secondary/20 border border-t-0 border-secondary-border rounded-b-lg p-4">
                                                {product.citations.length > 0 && (
                                                    <div className="space-y-2">
                                                        <div className="space-y-2">
                                                            {product.citations.map((citation, citationIndex) => (
                                                                <TooltipProvider key={citationIndex} delayDuration={300}>
                                                                    <Tooltip>
                                                                        <TooltipTrigger asChild>
                                                                            <Button
                                                                                variant="ghost"
                                                                                size="sm"
                                                                                className="h-auto p-3 text-xs hover:bg-background border border-secondary-border text-left justify-start w-full bg-background/50"
                                                                                onClick={() => handleCitationClick(citation)}
                                                                            >
                                                                                <FileText className="w-3 h-3 mr-2 flex-shrink-0" />
                                                                                <div className="flex-1 min-w-0">
                                                                                    <div className="text-xs text-muted-foreground mb-1">
                                                                                        {citation.filename}
                                                                                    </div>
                                                                                    <div className="text-xs text-foreground">
                                                                                        {truncateText(citation.text)}
                                                                                    </div>
                                                                                </div>
                                                                            </Button>
                                                                        </TooltipTrigger>
                                                                        <TooltipContent side="top" className="max-w-[400px] p-3">
                                                                            <div className="space-y-1">
                                                                                <p className="font-medium text-xs">{citation.filename}</p>
                                                                                <p className="text-xs">{citation.text}</p>
                                                                            </div>
                                                                        </TooltipContent>
                                                                    </Tooltip>
                                                                </TooltipProvider>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </CollapsibleContent>
                                    </Collapsible>
                                ))}
                            </div>
                        </div>
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </div>
    );
};

export default TenderProductsSection; 
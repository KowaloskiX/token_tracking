import { SUPPORTED_EXTENSIONS } from "@/app/constants";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsTrigger } from "@/components/ui/tabs";
import { TabsList } from "@radix-ui/react-tabs";
import { CloudUpload, Globe, InfoIcon, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import FileComponent from "../FileComponent";
import { ScrapedLink, ScrapedResult } from "@/types/scraping";
import { useToast } from "@/hooks/use-toast";
import { scrapeSite } from "@/utils/scrapeSite";
import { WebsitePreview } from "../WebsitePreview";
import { useDashboard } from "@/context/DashboardContext";
import { getFileType, uploadFile } from "@/utils/fileActions";
import { Alert } from "@/components/ui/alert";
import { ExcelFileStats } from "@/utils/excelAnalysis";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslations } from 'next-intl';

interface UploadMemoryPopupProps {
    closePopup: () => void;
    currentFolderId: string | null;
    onUploadComplete?: () => void;
}

const UploadMemoryPopup = ({ 
    closePopup, 
    currentFolderId, 
    onUploadComplete 
}: UploadMemoryPopupProps) => {
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [websiteUrl, setWebsiteUrl] = useState('');
    const [isScrapingWebsite, setIsScrapingWebsite] = useState(false);
    const [scrapedSites, setScrapedSites] = useState<ScrapedResult[]>([]);
    const [suggestedLinks, setSuggestedLinks] = useState<ScrapedLink[]>([]);
    const [selectedLinks, setSelectedLinks] = useState<Set<string>>(new Set());
    const { toast } = useToast();
    const { user, currentAssistant } = useDashboard();
    const [fileStats, setFileStats] = useState<ExcelFileStats[]>([]);
    const dragCounterRef = useRef(0);

    // Translation hooks
    const t = useTranslations('dashboard.file_upload');
    const tCommon = useTranslations('common');
    const tErrors = useTranslations('errors.general');

    const handleClickUpload = () => {
        fileInputRef.current?.click();
    };

    const isFileSupported = (file: File) => {
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (!extension) return false;
        return extension in SUPPORTED_EXTENSIONS;
    };

    const handleFilesAdded = async (files: File[]) => {
        const supportedFiles = files.filter(file => isFileSupported(file));
        
        if (files.length !== supportedFiles.length) {
            toast({
                title: t('unsupported_files'),
                description: t('unsupported_files_desc'),
                variant: "destructive",
            });
        }
        
        setSelectedFiles(prevFiles => [...prevFiles, ...supportedFiles]);
        setFileStats([]);
        
        try {
            const excelFiles = supportedFiles.filter(file => 
                file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
            );

            if (excelFiles.length > 0) {
                const { analyzeExcelFile } = await import('@/utils/excelAnalysis');
                const statsPromises = excelFiles.map(file => analyzeExcelFile(file));
                const stats = await Promise.all(statsPromises);
                setFileStats(stats);
            }
        } catch (error) {
            console.error('Error analyzing Excel files:', error);
            toast({
                title: t('analysis_error'),
                description: t('failed_analyze_excel'),
                variant: "destructive",
            });
        }
    };

    const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files || []);
        handleFilesAdded(files);
    };

    const handleDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current++;
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current--;
        if (dragCounterRef.current === 0) {
            setIsDragging(false);
        }
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current = 0;
        setIsDragging(false);

        const droppedFiles = Array.from(e.dataTransfer.files);
        handleFilesAdded(droppedFiles);
    }, []);

    const handleUploadFiles = async () => {
        if (selectedFiles.length === 0 || !user || !currentAssistant) return;

        setIsUploading(true);
        const uploadedFiles = [];
        const failedFiles = [];

        try {
            if (!currentFolderId) {
                toast({
                    title: t('upload_failed'),
                    description: t('error_target_folder'),
                    variant: "destructive",
                });
                return;
            }

            const uploadPromises = selectedFiles.map(async (file) => {
                try {
                    const fileType = getFileType(file.name);
                    
                    const createdFiles = await uploadFile(
                        file,
                        'assistants',
                        user._id!,
                        currentFolderId,
                        fileType,
                        currentAssistant._id
                    );

                    uploadedFiles.push(...createdFiles.map(f => f.filename));
                    
                } catch (error) {
                    console.error(`Error uploading ${file.name}:`, error);
                    failedFiles.push(file.name);
                }
            });

            await Promise.all(uploadPromises);

            if (uploadedFiles.length > 0) {
                toast({
                    title: t('files_uploaded'),
                    description: `${tCommon('success')} - ${uploadedFiles.length} ${tCommon('files')}`,
                });
                await onUploadComplete?.();
                closePopup();
            }

            if (failedFiles.length > 0) {
                toast({
                    title: t('upload_failed'),
                    description: `${tErrors('something_went_wrong')} - ${failedFiles.length} ${tCommon('files')}`,
                    variant: "destructive",
                });
            }
        } catch (error) {
            console.error('Upload error:', error);
            toast({
                title: t('upload_failed'),
                description: tErrors('something_went_wrong'),
                variant: "destructive",
            });
        } finally {
            setIsUploading(false);
        }
    };

    const handleRemoveFile = (indexToRemove: number) => {
        setSelectedFiles(prevFiles =>
            prevFiles.filter((_, index) => index !== indexToRemove)
        );
    };

    const validateUrl = (url: string) => {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    };

    const handleWebsiteScrape = async (urls: string[]) => {
        if (urls.length === 0) return;

        const invalidUrls = urls.filter(url => !validateUrl(url));
        if (invalidUrls.length > 0) {
            toast({
                title: t('invalid_urls'),
                description: t('invalid_urls_desc'),
                variant: "destructive",
            });
            return;
        }

        setIsScrapingWebsite(true);
        try {
            const response = await scrapeSite({
                urls,
                wait_for_dynamic: true
            });

            if (response.results.length > 0) {
                const newResults = response.results;
                setScrapedSites(prev => [...prev, ...newResults]);
                
                const allNewLinks = newResults.flatMap(result => result.links)
                    .filter((link: ScrapedLink) => 
                        !scrapedSites.some(site => site.url === link.url) &&
                        !urls.includes(link.url)
                    );
                
                const uniqueLinks = Array.from(
                    new Map(allNewLinks.map(link => [link.url, link])).values()
                );
                
                setSuggestedLinks(uniqueLinks);
                setWebsiteUrl('');
                setSelectedLinks(new Set());
            }
        } catch (error) {
            console.error('Error scraping websites:', error);
            toast({
                title: t('error_scraping'),
                description: t('error_scraping_desc'),
                variant: "destructive",
            });
        } finally {
            setIsScrapingWebsite(false);
        }
    };

    const toggleLinkSelection = (url: string) => {
        const newSelected = new Set(selectedLinks);
        if (newSelected.has(url)) {
            newSelected.delete(url);
        } else {
            newSelected.add(url);
        }
        setSelectedLinks(newSelected);
    };

    const handleScrapeSelected = () => {
        const urlsToScrape = Array.from(selectedLinks);
        if (urlsToScrape.length > 0) {
            handleWebsiteScrape(urlsToScrape);
        }
    };

    const handleWebsiteUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setWebsiteUrl(e.target.value);
    };

    const handleRemoveScrapedSite = (indexToRemove: number) => {
        setScrapedSites(prev => prev.filter((_, index) => index !== indexToRemove));
    };

    const handleRemoveSuggestedLink = (indexToRemove: number) => {
        const removedLink = suggestedLinks[indexToRemove];
        setSuggestedLinks(prev => prev.filter((_, index) => index !== indexToRemove));
        if (removedLink) {
            const newSelected = new Set(selectedLinks);
            newSelected.delete(removedLink.url);
            setSelectedLinks(newSelected);
        }
    };

    const handleSaveWebsites = async () => {
        if (scrapedSites.length === 0 || !user || !currentAssistant) return;

        setIsUploading(true);
        const savedSites = [];
        const failedSites = [];

        try {
            if (!currentFolderId) {
                toast({
                    title: t('save_pages_failed'),
                    description: t('error_target_folder'),
                    variant: "destructive",
                });
                return;
            }

            const savePromises = scrapedSites.map(async (site) => {
                try {
                    const content = `Title: ${site.title || 'Untitled'}\nURL: ${site.url}\n\n${site.text}`;
                    const blob = new Blob([content], { type: 'text/plain' });
                    
                    const filename = site.title 
                        ? `${site.title}.txt`
                        : `${new URL(site.url).hostname.replace('www.', '')}.txt`;

                    const file = new File([blob], filename, { type: 'text/plain' });

                    await uploadFile(
                        file,
                        'assistants',
                        user._id!,
                        currentFolderId,
                        'website',
                        currentAssistant._id
                    );
                    savedSites.push(site.url);
                } catch (error) {
                    console.error(`Error saving ${site.url}:`, error);
                    failedSites.push(site.url);
                }
            });

            await Promise.all(savePromises);

            if (savedSites.length > 0) {
                toast({
                    title: t('pages_saved'),
                    description: `${tCommon('success')} - ${savedSites.length}`,
                });
                await onUploadComplete?.();
                closePopup();
            }

            if (failedSites.length > 0) {
                toast({
                    title: t('save_pages_failed'),
                    description: `${tErrors('something_went_wrong')} - ${failedSites.length}`,
                    variant: "destructive",
                });
            }
        } catch (error) {
            console.error('Save error:', error);
            toast({
                title: t('save_pages_failed'),
                description: tErrors('something_went_wrong'),
                variant: "destructive",
            });
        } finally {
            setIsUploading(false);
        }
    };

    const renderLargeFileInfo = () => {
        if (fileStats.length === 0) return null;

        const hasLargeDataset = fileStats.some(stats => stats.isLargeDataset);
        
        if (!hasLargeDataset) return null;

        return (
            <AnimatePresence>
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 20 }}
                    transition={{
                        type: "spring",
                        stiffness: 300,
                        damping: 30,
                        duration: 2
                    }}
                    className="mt-4"
                >
                    <Alert className="bg-background overflow-hidden flex gap-4">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.5 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.1 }}
                        >
                            <InfoIcon className="h-4 w-4" />
                        </motion.div>
                        <div className="mt-0 p-0">
                            <motion.p
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.4 }}
                            >
                                {t('large_dataset_detected')}
                            </motion.p>
                            <motion.p
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.45 }}
                                className="mt-1"
                            >
                                {t('contact_enterprise')}
                            </motion.p>
                        </div>
                    </Alert>
                </motion.div>
            </AnimatePresence>
        );
    };

    return (
        <Card className="w-[600px] bg-background p-6 relative text-left" onClick={(e) => e.stopPropagation()}>
            <Button
                variant="ghost"
                size="icon"
                className="w-6 h-6 shrink-0 absolute top-3 right-3"
                onClick={(e) => {
                    e.stopPropagation();
                    closePopup();
                }}
            >
                <X className="w-3 h-3" />
            </Button>
            <Tabs defaultValue="file">
                <TabsList className="grid w-[95%] grid-cols-2 bg-background mt-2">
                    <TabsTrigger value="file">{tCommon('file')}</TabsTrigger>
                    <TabsTrigger value="website">{t('upload_website')}</TabsTrigger>
                </TabsList>

                <TabsContent value="file">
                    <Card className="border-none">
                        <CardHeader>
                            <h3 className="text-lg font-semibold leading-none tracking-tight">{t('upload_files')}</h3>
                            <p className="text-sm text-muted-foreground">
                                {t('upload_description')}
                            </p>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                onChange={handleFileUpload}
                                multiple
                                accept={Object.entries(SUPPORTED_EXTENSIONS)
                                    .map(([ext]) => `.${ext}`)
                                    .join(',')}
                            />
                            <div>
                                <button
                                    className={`w-full flex items-center justify-center gap-4 py-6 border-2 ${
                                        isDragging 
                                            ? "border-primary bg-primary/5" 
                                            : "border-neutral-200 hover:border-neutral-400"
                                    } border-dashed rounded-lg transition-colors duration-200`}
                                    onClick={handleClickUpload}
                                    onDragEnter={handleDragEnter}
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                    onDrop={handleDrop}
                                >
                                    <div className="flex flex-col items-center">
                                        <CloudUpload className={`w-6 h-6 ${isDragging ? "text-primary" : ""}`} />
                                        <p className="mt-2">
                                            {isDragging ? t('drag_drop_here') : t('upload_files')}
                                        </p>
                                        <p className="text-sm text-muted-foreground">
                                            {isDragging ? t('drop_to_upload') : t('max_100mb')}
                                        </p>
                                    </div>
                                </button>
                                <div className="flex w-full flex-wrap gap-2 mt-2">
                                    {selectedFiles.length > 0 && (
                                        selectedFiles.map((file, index) => (
                                            <FileComponent
                                                key={`${file.name}-${index}`}
                                                file={file}
                                                onRemove={() => handleRemoveFile(index)}
                                            />
                                        ))
                                    )}
                                </div>
                                {renderLargeFileInfo()}
                                <Button 
                                    disabled={selectedFiles.length < 1 || isUploading} 
                                    className="w-full mt-6"
                                    onClick={handleUploadFiles}
                                >
                                    {isUploading ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <CloudUpload className="w-4 h-4 mr-2" />
                                    )}
                                    {isUploading ? tCommon('uploading') : t('upload_files')}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="website">
                    <Card className="border-none">
                        <CardHeader>
                            <h3 className="text-lg font-semibold leading-none tracking-tight">{t('upload_website')}</h3>
                            <p className="text-sm text-muted-foreground">
                                {t('website_description')}
                            </p>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-1">
                                <Label htmlFor="website-input" className="text-xs">{t('website_url')}</Label>
                                <div className="flex gap-2">
                                    <Input
                                        id="website-input"
                                        type="url"
                                        placeholder={t('website_placeholder')}
                                        value={websiteUrl}
                                        onChange={handleWebsiteUrlChange}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                handleWebsiteScrape([websiteUrl]);
                                            }
                                        }}
                                    />
                                    <Button
                                        onClick={() => handleWebsiteScrape([websiteUrl])}
                                        disabled={!websiteUrl || isScrapingWebsite}
                                    >
                                        {isScrapingWebsite ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <Globe className="w-4 h-4" />
                                        )}
                                        {isScrapingWebsite ? t('scraping') : t('scrape')}
                                    </Button>
                                </div>
                            </div>

                            {scrapedSites.length > 0 && (
                                <div className="space-y-2">
                                    <Label>{t('analyzed_pages')}</Label>
                                    <div className="flex flex-wrap gap-2">
                                        {scrapedSites.map((site, index) => (
                                            <WebsitePreview
                                                key={`${site.url}-${index}`}
                                                title={site.title}
                                                url={site.url}
                                                favicon={site.favicon}
                                                onRemove={() => handleRemoveScrapedSite(index)}
                                                openInNewTab={true}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {suggestedLinks.length > 0 && (
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <Label>{t('you_can_also_scan')}</Label>
                                        {selectedLinks.size > 0 && (
                                            <Button
                                                size="sm"
                                                onClick={handleScrapeSelected}
                                                disabled={isScrapingWebsite}
                                            >
                                                {isScrapingWebsite ? (
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Globe className="w-4 h-4" />
                                                )}
                                                {t('scrape_selected')} ({selectedLinks.size})
                                            </Button>
                                        )}
                                    </div>
                                    <div className="flex flex-wrap gap-2 max-h-60 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-neutral-200 scrollbar-track-transparent">
                                        {suggestedLinks.map((link, index) => (
                                            <WebsitePreview
                                                key={`${link.url}-${index}`}
                                                title={link.text}
                                                url={link.url}
                                                onClick={() => toggleLinkSelection(link.url)}
                                                onRemove={() => handleRemoveSuggestedLink(index)}
                                                selected={selectedLinks.has(link.url)}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            <Button
                                className="w-full"
                                disabled={scrapedSites.length === 0 || isUploading}
                                onClick={handleSaveWebsites}
                            >
                                {isUploading ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <CloudUpload className="w-4 h-4 mr-2" />
                                )}
                                {isUploading ? tCommon('saving') : `${t('save_pages')} (${scrapedSites.length})`}
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </Card>
    );
};

export default UploadMemoryPopup;
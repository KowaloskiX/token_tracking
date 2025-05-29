import { Skeleton } from "@/components/ui/skeleton";

const TenderDetailsSkeleton = () => (
    <div className="p-4 sm:p-6 pb-24 overflow-y-auto overflow-x-hidden scrollbar-hide flex-grow space-y-4 sm:space-y-6">
        <div className='border-b pb-4'>
            <div className="flex flex-wrap sm:flex-nowrap justify-between gap-4 sm:gap-8 mb-4">
                <div className="flex items-start gap-4">
                    <div className="border border-neutral-200 p-2 rounded-lg mt-0.5">
                        <Skeleton className="w-5 h-5" />
                    </div>
                    <Skeleton className="h-6 w-60" />
                </div>
            </div>
            
            <div className='text-sm tracking-tight text-muted-foreground'>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-[90%] mb-2" />
                <Skeleton className="h-4 w-[85%]" />
            </div>
            
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-6 mt-6">
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-4 w-4" />
                        <Skeleton className="h-4 w-20" />
                    </div>
                    <Skeleton className="h-4 w-32" />
                </div>
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-4 w-4" />
                        <Skeleton className="h-4 w-28" />
                    </div>
                    <Skeleton className="h-4 w-24" />
                </div>
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-4 w-4" />
                        <Skeleton className="h-4 w-24" />
                    </div>
                    <Skeleton className="h-4 w-16" />
                </div>
            </div>
        </div>

        {/* Status section */}
        <div className="flex items-center gap-2 mb-4 bg-secondary/30 p-3 rounded-lg border border-neutral-200">
            <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-4" />
                <Skeleton className="h-4 w-16" />
            </div>
            <div className="flex-grow ml-2">
                <Skeleton className="h-8 w-48" />
            </div>
            <Skeleton className="h-6 w-24" />
        </div>

        {/* Criteria section */}
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <Skeleton className="h-6 w-24" />
            </div>
            <div className="space-y-2">
                {[1, 2, 3].map(i => (
                    <div key={i} className="border border-secondary-border rounded-lg p-3">
                        <div className="flex justify-between items-center">
                            <div className="flex items-center gap-2">
                                <Skeleton className="h-8 w-8" />
                                <Skeleton className="h-5 w-40" />
                            </div>
                            <Skeleton className="h-5 w-20" />
                        </div>
                    </div>
                ))}
            </div>
        </div>

        {/* Files section */}
        <div className="space-y-4">
            <Skeleton className="h-6 w-16" />
            <div className="flex flex-wrap gap-2">
                {[1, 2, 3].map(i => (
                    <Skeleton key={i} className="h-10 w-40" />
                ))}
            </div>
        </div>

        {/* Comments section */}
        <div className="space-y-4">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-24 w-full" />
        </div>
    </div>
);


export default TenderDetailsSkeleton
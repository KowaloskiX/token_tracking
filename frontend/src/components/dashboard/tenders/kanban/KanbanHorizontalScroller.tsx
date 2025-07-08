import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface KanbanHorizontalScrollerProps {
  containerRef: React.RefObject<HTMLDivElement>;
  totalColumns: number;
  columnWidth: number;
  className?: string;
}

export function KanbanHorizontalScroller({ 
  containerRef, 
  totalColumns, 
  columnWidth,
  className = "" 
}: KanbanHorizontalScrollerProps) {
  const [scrollPosition, setScrollPosition] = useState(0);
  const [maxScroll, setMaxScroll] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const sliderRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // HARDCODED: Always show scroller if we have more than 1 column
  const showScroller = totalColumns > 1;

  // Calculate dimensions
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const container = containerRef.current;
        const containerRect = container.getBoundingClientRect();
        
        // HARDCODED: Force calculate dimensions
        const totalContentWidth = totalColumns * (columnWidth + 16); // 16px gap
        const visibleWidth = containerRect.width;
        
        setContainerWidth(visibleWidth);
        setMaxScroll(Math.max(0, totalContentWidth - visibleWidth));
      }
    };

    updateDimensions();
    
    // Update on resize
    const timer = setInterval(updateDimensions, 100); // Check every 100ms
    
    return () => clearInterval(timer);
  }, [containerRef, totalColumns, columnWidth]);

  // Sync scroll position with container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      setScrollPosition(container.scrollLeft);
    };

    container.addEventListener('scroll', handleScroll);
    
    // Also poll for scroll position
    const scrollTimer = setInterval(() => {
      setScrollPosition(container.scrollLeft);
    }, 50);
    
    return () => {
      container.removeEventListener('scroll', handleScroll);
      clearInterval(scrollTimer);
    };
  }, [containerRef]);

  // Calculate slider thumb position and width
  const getSliderMetrics = useCallback(() => {
    if (maxScroll === 0 || containerWidth === 0) return { left: 0, width: 100 };
    
    const totalContentWidth = totalColumns * (columnWidth + 16);
    const thumbWidth = Math.max(20, (containerWidth / totalContentWidth) * 100);
    const thumbLeft = maxScroll > 0 ? (scrollPosition / maxScroll) * (100 - thumbWidth) : 0;
    
    return { 
      left: Math.min(Math.max(0, thumbLeft), 100 - thumbWidth), 
      width: Math.min(Math.max(20, thumbWidth), 100) 
    };
  }, [maxScroll, containerWidth, scrollPosition, totalColumns, columnWidth]);

  // Handle slider interaction
  const handleSliderMouseDown = useCallback((e: React.MouseEvent) => {
    if (!sliderRef.current || !containerRef.current) return;
    
    e.preventDefault();
    isDragging.current = true;
    
    const sliderRect = sliderRef.current.getBoundingClientRect();
    const startX = e.clientX;
    const startScrollLeft = containerRef.current.scrollLeft;
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDragging.current || !containerRef.current || !sliderRef.current) return;
      
      const deltaX = moveEvent.clientX - startX;
      const sliderWidth = sliderRect.width;
      const scrollRatio = deltaX / sliderWidth;
      const newScrollLeft = startScrollLeft + (scrollRatio * maxScroll);
      
      containerRef.current.scrollLeft = Math.max(0, Math.min(maxScroll, newScrollLeft));
    };
    
    const handleMouseUp = () => {
      isDragging.current = false;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [maxScroll, containerRef]);

  // Handle slider track click
  const handleTrackClick = useCallback((e: React.MouseEvent) => {
    if (!sliderRef.current || !containerRef.current || isDragging.current) return;
    
    const sliderRect = sliderRef.current.getBoundingClientRect();
    const clickX = e.clientX - sliderRect.left;
    const clickRatio = clickX / sliderRect.width;
    const newScrollLeft = clickRatio * maxScroll;
    
    containerRef.current.scrollLeft = Math.max(0, Math.min(maxScroll, newScrollLeft));
  }, [maxScroll, containerRef]);

  // Arrow button handlers
  const scrollLeft = useCallback(() => {
    if (!containerRef.current) return;
    const scrollAmount = columnWidth + 16;
    containerRef.current.scrollLeft = Math.max(0, containerRef.current.scrollLeft - scrollAmount);
  }, [containerRef, columnWidth]);

  const scrollRight = useCallback(() => {
    if (!containerRef.current) return;
    const scrollAmount = columnWidth + 16;
    containerRef.current.scrollLeft = Math.min(maxScroll, containerRef.current.scrollLeft + scrollAmount);
  }, [containerRef, columnWidth, maxScroll]);

  // HARDCODED: Always show if more than 1 column, even if dimensions aren't calculated yet
  if (!showScroller) return null;

  const { left, width } = getSliderMetrics();

  return (
    <div className={`flex items-center gap-2 px-4 py-2 bg-secondary/50 rounded-md border ${className}`}>
      {/* Left arrow button */}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 flex-shrink-0"
        onClick={scrollLeft}
        disabled={scrollPosition <= 0}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      {/* Slider track */}
      <div 
        ref={sliderRef}
        className="flex-1 h-3 bg-secondary rounded-full relative cursor-pointer border"
        onClick={handleTrackClick}
      >
        {/* Slider thumb */}
        <div
          className="absolute top-0 h-full bg-primary rounded-full cursor-grab active:cursor-grabbing transition-all duration-150 ease-out hover:bg-primary-hover shadow-sm"
          style={{
            left: `${left}%`,
            width: `${width}%`,
            minWidth: '30px'
          }}
          onMouseDown={handleSliderMouseDown}
        />
      </div>

      {/* Right arrow button */}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 flex-shrink-0"
        onClick={scrollRight}
        disabled={scrollPosition >= maxScroll}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>

      {/* Position indicator */}
      <div className="text-xs text-muted-foreground font-mono min-w-fit bg-background/50 px-2 py-1 rounded">
        {Math.round((scrollPosition / Math.max(1, maxScroll)) * 100)}%
      </div>
      
      {/* Debug info - remove this later */}
      <div className="text-xs text-red-500 font-mono min-w-fit bg-red-50 px-1 rounded">
        {totalColumns}c {Math.round(maxScroll)}px
      </div>
    </div>
  );
}
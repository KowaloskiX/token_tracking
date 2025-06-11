import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { ChevronLeft, ChevronRight, FolderOpen, GripVertical } from 'lucide-react';
import { useTranslations } from 'next-intl';

interface MagicDrawerProps {
  children: React.ReactNode;
  defaultWidth?: number;
  maxWidth?: number;
  minWidth?: number;
  forceExpanded?: boolean;
  onVisibilityChange?: (isVisible: boolean) => void;
}

const MagicDrawer = forwardRef<{ setVisibility: (value: boolean) => void }, MagicDrawerProps>(({
  children,
  defaultWidth = 580,
  maxWidth = 1200,
  minWidth = 480,
  forceExpanded = false,
  onVisibilityChange
}, ref) => {
  const t = useTranslations('common');
  const [mounted, setMounted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [width, setWidth] = useState(defaultWidth);
  const [isDragging, setIsDragging] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const dragHandleRef = useRef<HTMLDivElement>(null);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(defaultWidth);

  useImperativeHandle(ref, () => ({
    setVisibility: (value: boolean) => {
      setIsVisible(value);
      onVisibilityChange?.(value);
    }
  }));

  // Handle initial device check and mounting
  useEffect(() => {
    const isMobileView = window.innerWidth < 768;
    setIsMobile(isMobileView);
    setIsVisible(forceExpanded || !isMobileView);
    setMounted(true);

    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [forceExpanded]);

  // Handle dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      
      const delta = startXRef.current - e.clientX;
      const newWidth = Math.min(Math.max(startWidthRef.current + delta, minWidth), maxWidth);
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      if (!isDragging) return;
      setIsDragging(false);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };
  }, [isDragging, maxWidth, minWidth]);

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>): void => {
    if (isMobile) return;
    e.preventDefault();
    const target = e.target as HTMLElement;
    if (dragHandleRef.current?.contains(target)) {
      setIsDragging(true);
      startXRef.current = e.clientX;
      startWidthRef.current = width;
    }
  };

  const toggleVisibility = (): void => {
    const newValue = !isVisible;
    setIsVisible(newValue);
    onVisibilityChange?.(newValue);
  };

  if (!mounted) {
    return null;
  }

  return (
    <>
      <div
        ref={sidebarRef}
        style={{
          width: isMobile ? '100%' : (isVisible ? width : 0),
          transition: isDragging ? 'none' : 'width 300ms ease-in-out, transform 300ms ease-in-out',
          opacity: isTransitioning ? 0.5 : 1,
          position: isMobile ? 'fixed' : 'relative',
          right: 0,
          top: 0,
          bottom: 0,
          transform: !isVisible ? 'translateX(100%)' : 'translateX(0)',
          zIndex: 1
        }}
        className="flex h-full"
      >
        <div className="absolute left-0 top-1/2 -translate-x-full transform hidden md:block">
          <div className="relative flex flex-col border-l border-t border-b border-r-transparent bg-background rounded-l-md overflow-hidden">
            <button
              onClick={toggleVisibility}
              className="p-1 hover:bg-secondary transition-colors"
              aria-label={isVisible ? t('collapse_sidebar') : t('expand_sidebar')}
            >
              {isVisible ? (
                <ChevronRight className="size-6 text-neutral-600" />
              ) : (
                <ChevronLeft className="size-6 text-neutral-600" />
              )}
            </button>

            <div
              ref={dragHandleRef}
              onMouseDown={handleMouseDown}
              className="p-1 hover:bg-secondary cursor-ew-resize"
              role="button"
              tabIndex={0}
              aria-label={t('resize_sidebar')}
            >
              <GripVertical className="size-6 text-neutral-600" />
            </div>
          </div>
        </div>

        <div className="flex-1 bg-background border-l overflow-auto scrollbar-hide w-full">
          {children}
        </div>
      </div>

      {isMobile && (
        <>
          {!isVisible && (
            <button
              onClick={toggleVisibility}
              className="md:hidden fixed right-0 top-1/2 -translate-y-1/2 z-50 p-2 bg-background rounded-l-md border shadow-lg"
              aria-label={t('expand_sidebar')}
            >
              <FolderOpen className="size-4 text-neutral-600" />
            </button>
          )}

          {isVisible && (
            <button
              onClick={toggleVisibility}
              className="md:hidden fixed top-4 right-4 z-50 p-2 bg-background rounded-full shadow-lg"
              aria-label={t('close')}
            >
              <ChevronRight className="size-6 text-neutral-600" />
            </button>
          )}
        </>
      )}
    </>
  );
});

MagicDrawer.displayName = 'MagicDrawer';

export default MagicDrawer;
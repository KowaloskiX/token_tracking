"use client";

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Bell, Check } from 'lucide-react';
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useNotificationsTranslations } from '@/hooks/useTranslations';

interface NotificationHeaderProps {
  unreadCount: number;
  onMarkAllAsRead: () => void;
}

export function NotificationHeader({ unreadCount, onMarkAllAsRead }: NotificationHeaderProps) {
  const t = useNotificationsTranslations();

  return (
    <header className="flex w-full justify-between h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12 px-8">
      <div className="flex items-center gap-2 px-4">
        <SidebarTrigger className="-ml-6" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <div className="flex items-center gap-3">
          <Bell className="h-5 w-5" />
          <h2 className="font-semibold">{t('title')}</h2>
          {unreadCount > 0 && (
            <Badge variant="secondary">
              {t('new_count', { count: unreadCount })}
            </Badge>
          )}
        </div>
      </div>

      <Button onClick={onMarkAllAsRead} variant="secondary" size="sm" className="h-7 text-foreground hover:shadow-none border-2 hover:bg-secondary-hover border-secondary-border border bg-white/20 shadow">
        <Check className="h-4 w-4 mr-2" />
        <span className="hidden sm:block">{t('mark_all_read')}</span>
      </Button>
    </header>
  );
}
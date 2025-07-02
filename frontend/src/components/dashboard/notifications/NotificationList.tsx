"use client";

import { useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Mail, Filter, Check, ChevronDown } from 'lucide-react';
import { NotificationItem } from './NotificationItem';
import { Notification } from '@/types/notification';
import { useNotificationsTranslations } from '@/hooks/useTranslations';
import { useNotifications } from '@/hooks/useNotifications';

interface NotificationListProps {
  notifications: Notification[];
  selectedNotification: Notification | null;
  onSelect: (notification: Notification) => void;
  onDelete: (id: string) => void;
}

type FilterType = 'all' | 'info' | 'warning' | 'success' | 'error' | 'update' | 'results';

export function NotificationList({ 
  notifications, 
  selectedNotification, 
  onSelect, 
  onDelete
}: NotificationListProps) {
  const t = useNotificationsTranslations();
  const { markAsRead, markAsUnread } = useNotifications();
  const [filter, setFilter] = useState<FilterType>('all');

  // Filter notifications based on selected filter
  const filteredNotifications = notifications.filter((notification) => {
    switch (filter) {
      case 'all':
        return true;
      case 'info':
      case 'warning':
      case 'success':
      case 'error':
      case 'update':
      case 'results':
        return notification.type.toLowerCase() === filter;
      default:
        return true;
    }
  });

  const getFilterLabel = (filterType: FilterType) => {
    switch (filterType) {
      case 'all':
        return t('filters.all');
      default:
        return t(`types.${filterType}`);
    }
  };

  const filterOptions: FilterType[] = ['all', 'info', 'warning', 'success', 'error', 'update', 'results'];

  return (
    <div className="w-96 border-r flex-shrink-0">
      <div className="p-4 h-full flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">{t('sidebar_title')}</h2>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 px-3 gap-1">
                <Filter className="h-4 w-4" />
                <span className="hidden sm:inline">{getFilterLabel(filter)}</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {filterOptions.map((option) => (
                <DropdownMenuItem
                  key={option}
                  onClick={() => setFilter(option)}
                  className="flex items-center justify-between"
                >
                  <span>{getFilterLabel(option)}</span>
                  {filter === option && <Check className="h-4 w-4" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <ScrollArea className="flex-1">
          <div className="space-y-2 pr-4">
            {filteredNotifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                isSelected={selectedNotification?.id === notification.id}
                onSelect={onSelect}
                onDelete={onDelete}
                onMarkAsRead={markAsRead}
                onMarkAsUnread={markAsUnread}
              />
            ))}
            {filteredNotifications.length === 0 && notifications.length > 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Filter className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>{t('no_filtered_notifications')}</p>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => setFilter('all')}
                  className="mt-2"
                >
                  {t('clear_filter')}
                </Button>
              </div>
            )}
            {notifications.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Mail className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>{t('no_notifications')}</p>
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
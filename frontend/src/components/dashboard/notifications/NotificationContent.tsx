"use client";

import { useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Bell, Users } from 'lucide-react';
import { Notification } from '@/types/notification';
import { useNotificationsTranslations } from '@/hooks/useTranslations';
import { formatDate, getNotificationTypeText } from '@/utils/notifications';
import { NotificationActions } from './NotificationActions';

interface NotificationContentProps {
  notification: Notification | null;
  onDelete: (id: string) => void;
  onMarkAsRead?: (id: string) => void;
  onMarkAsUnread?: (id: string) => void;
  onMarkAsReadWhenDisplayed?: (notification: Notification) => void;
}


const getNotificationTypeColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'success': return 'bg-green-600/10 text-green-800 border-green-500/20 font-medium';
    case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200 font-medium';
    case 'error': return 'bg-red-100 text-red-800 border-red-200 font-medium';
    case 'info': return 'bg-primary-900/10 text-primary border-primary-900/20 font-medium';
    case 'update': return 'bg-amber-500/10 text-amber-800 border-amber-300 font-medium';
    case 'outcome': return 'bg-secondary-border text-body-text border-secondary-border font-medium';
    default: return 'bg-primary-900/10 text-primary border-primary-900/20 font-medium';
  }
};

export function NotificationContent({ 
  notification, 
  onDelete,
  onMarkAsRead,
  onMarkAsUnread,
  onMarkAsReadWhenDisplayed 
}: NotificationContentProps) {
  const t = useNotificationsTranslations();

  // Mark notification as read when it's displayed
  useEffect(() => {
    if (notification && onMarkAsReadWhenDisplayed) {
      // Small delay to ensure the user sees the notification
      const timer = setTimeout(() => {
        onMarkAsReadWhenDisplayed(notification);
      }, 300);

      return () => clearTimeout(timer);
    }
  }, [notification, onMarkAsReadWhenDisplayed]);

  if (!notification) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="text-center">
          <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg">{t('select_to_view')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0 mr-4">
          <h1 className="text-xl font-medium break-words">
              {notification.title}
            </h1>
            <div className="flex items-center gap-2 mt-2">
              <Badge 
                variant="outline" 
                className={getNotificationTypeColor(notification.type)}
              >
                {getNotificationTypeText(notification.type, t)}
              </Badge>
              {/* {notification.org_id && (
                <Badge variant="outline" className="bg-[hsl(var(--secondary))] text-[hsl(var(--primary))] border-[hsl(var(--border))]">
                  <Users className="h-3 w-3 mr-1" />
                  {t('org_badge')}
                </Badge>
              )} */}
              <span className="text-sm text-muted-foreground">
                {formatDate(notification.created_at)}
              </span>
            </div>
          </div>
          
          <NotificationActions
            notification={notification}
            onDelete={onDelete}
            onMarkAsRead={onMarkAsRead}
            onMarkAsUnread={onMarkAsUnread}
            size="default"
            variant="outline"
          />
        </div>
      </div>
      
      <ScrollArea className="flex-1 p-6">
        <div className="max-w-none">
          <div 
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: notification.content }}
          />
        </div>
      </ScrollArea>
    </div>
  );
}
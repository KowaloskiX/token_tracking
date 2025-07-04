"use client";

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Users } from 'lucide-react';
import { Notification } from '@/types/notification';
import { useNotificationsTranslations } from '@/hooks/useTranslations';
import { formatDate, getNotificationTypeText } from '@/utils/notifications';
import { NotificationActions } from './NotificationActions';

interface NotificationItemProps {
  notification: Notification;
  isSelected: boolean;
  onSelect: (notification: Notification) => void;
  onDelete: (id: string) => void;
  onMarkAsRead?: (id: string) => void;
  onMarkAsUnread?: (id: string) => void;
}

const getNotificationTypeColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'success': return 'bg-green-600/10 text-green-800 border-green-500/20';
    case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'error': return 'bg-red-100 text-red-800 border-red-200';
    case 'info': return 'bg-primary-900/10 text-primary border-primary-900/20';
    case 'update': return 'bg-amber-500/10 text-amber-800 border-amber-300';
    case 'outcome': return 'bg-secondary-border text-body-text border-secondary-border';
    default: return 'bg-primary-900/10 text-primary border-primary-900/20';
  }
};

// Function to extract text from HTML content and normalize whitespace
const extractTextFromHtml = (html: string): string => {
  if (typeof window === 'undefined') return html; // SSR safety
  
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html;
  
  const blockElements = ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ul', 'ol', 'br'];
  
  blockElements.forEach(tag => {
    const elements = tempDiv.getElementsByTagName(tag);
    for (let i = elements.length - 1; i >= 0; i--) {
      const element = elements[i];
      element.insertAdjacentText('beforebegin', ' ');
      element.insertAdjacentText('afterend', ' ');
    }
  });
  
  const textContent = tempDiv.textContent || tempDiv.innerText || '';
  return textContent.replace(/\s+/g, ' ').trim();
};

export function NotificationItem({ 
  notification, 
  isSelected, 
  onSelect, 
  onDelete,
  onMarkAsRead,
  onMarkAsUnread
}: NotificationItemProps) {
  const t = useNotificationsTranslations();

  const handleClick = () => {
    onSelect(notification);
  };

  const plainTextContent = extractTextFromHtml(notification.content);

  return (
    <Card 
      className={`cursor-pointer transition-colors hover:bg-secondary/70 ${
        isSelected 
          ? 'bg-secondary-hover !border-l-2 !border-l-primary shadow-sm' 
          : !notification.is_read
            ? 'bg-green-600/5 font-semibold !border-l-2 !border-l-green-600/70 shadow-sm' 
            : 'bg-white/20'
      }`}
      onClick={handleClick}
    >
      <CardContent className="p-4 relative">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-sm mb-1 line-clamp-2">
              {notification.title}
            </h3>
            <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
              {plainTextContent}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDate(notification.created_at)}
            </p>
          </div>
          
          <NotificationActions
            notification={notification}
            onDelete={onDelete}
            onMarkAsRead={onMarkAsRead}
            onMarkAsUnread={onMarkAsUnread}
            size="sm"
            variant="ghost"
            className="opacity-60 hover:opacity-100"
          />
        </div>
        
        <Badge 
          variant="outline" 
          className={`absolute bottom-2 right-2 text-[0.6rem] font-normal ${getNotificationTypeColor(notification.type)}`}
        >
          {getNotificationTypeText(notification.type, t)}
        </Badge>
      </CardContent>
    </Card>
  );
}
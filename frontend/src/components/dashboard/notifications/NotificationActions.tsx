"use client";

import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { MoreVertical, Trash2, Eye, EyeOff } from 'lucide-react';
import { Notification } from '@/types/notification';
import { useNotificationsTranslations } from '@/hooks/useTranslations';

interface NotificationActionsProps {
  notification: Notification;
  onDelete: (id: string) => void;
  onMarkAsRead?: (id: string) => void;
  onMarkAsUnread?: (id: string) => void;
  size?: 'sm' | 'default';
  variant?: 'ghost' | 'outline';
  className?: string;
}

export function NotificationActions({ 
  notification,
  onDelete,
  onMarkAsRead,
  onMarkAsUnread,
  size = 'sm',
  variant = 'ghost',
  className = ''
}: NotificationActionsProps) {
  const t = useNotificationsTranslations();

  const handleMarkAsRead = (e: React.MouseEvent) => {
    e.stopPropagation();
    onMarkAsRead?.(notification.id);
  };

  const handleMarkAsUnread = (e: React.MouseEvent) => {
    e.stopPropagation();
    onMarkAsUnread?.(notification.id);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(notification.id);
  };

  const buttonSize = size === 'sm' ? 'h-6 w-6 p-0' : 'h-8 w-8 p-0';
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={variant}
          size={size}
          className={`${buttonSize} flex-shrink-0 ${className}`}
          onClick={(e) => e.stopPropagation()}
        >
          <MoreVertical className={iconSize} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {notification.is_read ? (
          <DropdownMenuItem onClick={handleMarkAsUnread}>
            <EyeOff className="h-4 w-4 mr-2" />
            {t('actions.mark_as_unread')}
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onClick={handleMarkAsRead}>
            <Eye className="h-4 w-4 mr-2" />
            {t('actions.mark_as_read')}
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={handleDelete} className="text-destructive focus:text-destructive">
          <Trash2 className="h-4 w-4 mr-2" />
          {t('actions.delete')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
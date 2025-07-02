"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { Notification } from '@/types/notification';
import { notificationApi } from '@/utils/notificationApi';
import { useToast } from '@/hooks/use-toast';
import { useDashboard } from '@/hooks/useDashboard';
import { useNotificationsTranslations, useCommonTranslations } from '@/hooks/useTranslations';

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  error: string | null;
  fetchNotifications: (unreadOnly?: boolean) => Promise<void>;
  markAsRead: (id: string, silent?: boolean) => Promise<void>;
  markAsUnread: (id: string, silent?: boolean) => Promise<void>;
  markAsReadWhenDisplayed: (notification: Notification) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (id: string) => Promise<void>;
  createNotification: (data: {
    user_id: string;
    title: string;
    content: string;
    type?: string;
    org_id?: string;
  }) => Promise<any>;
  refetch: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const { user } = useDashboard();
  const t = useNotificationsTranslations();
  const common = useCommonTranslations();
  const lastNotificationIds = useRef<Set<string>>(new Set());
  const isInitialLoad = useRef(true);

  // Fetch notifications from API
  const fetchNotifications = useCallback(async (unreadOnly: boolean = false, silent: boolean = false) => {
    if (!user) {
      if (!silent) {
        setLoading(false);
        setError(t('toast.not_authenticated'));
      }
      return;
    }

    try {
      if (!silent) {
        setLoading(true);
        setError(null);
      }
      const data = await notificationApi.getNotifications(unreadOnly);
      
      // Set lastNotificationIds on initial load to prevent toasts
      if (isInitialLoad.current) {
        lastNotificationIds.current = new Set(data.map(n => n.id));
        isInitialLoad.current = false;
      }
      
      setNotifications(data);
      if (!silent) {
        setError(null);
      }
    } catch (err: any) {
      const errorMessage = err.message || t('toast.failed_to_load');
      if (!silent) {
        setError(errorMessage);
        toast({
          title: common('error'),
          description: t('toast.failed_to_load'),
          variant: 'destructive',
        });
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, [toast, user, t, common]);

  // Silent fetch for background updates, with toast for new notifications
  const fetchNotificationsSilent = useCallback(async () => {
    if (!user) return;
    try {
      const data = await notificationApi.getNotifications(false);
      
      // Find new notifications (only if not initial load)
      if (!isInitialLoad.current) {
        const newNotifs = data.filter(n => !lastNotificationIds.current.has(n.id));
        if (newNotifs.length > 0) {
          newNotifs.forEach(n => {
            // Strip HTML and truncate for toast
            const plainContent = n.content.replace(/<[^>]+>/g, '').substring(0, 100);
            toast({
              title: n.title,
              description: plainContent + (n.content.length > 100 ? '...' : ''),
              variant: 'default',
            });
          });
        }
      }
      
      // Update state and last seen IDs
      setNotifications(data);
      lastNotificationIds.current = new Set(data.map(n => n.id));
    } catch (err: any) {
      // Silent error handling - no toast for background failures
      console.warn('Silent notification fetch failed:', err);
    }
  }, [toast, user]);

  // Mark notification as read
  const markAsRead = useCallback(async (id: string, silent: boolean = false) => {
    if (!user) return;

    try {
      await notificationApi.markAsRead(id);
      setNotifications(prev =>
        prev.map(notif => 
          notif.id === id ? { ...notif, is_read: true } : notif
        )
      );
      if (!silent) {
        toast({
          title: common('success'),
          description: t('toast.marked_as_read'),
        });
      }
    } catch (err: any) {
      if (!silent) {
        toast({
          title: common('error'),
          description: t('toast.failed_to_mark_read'),
          variant: 'destructive',
        });
      }
    }
  }, [toast, user, t, common]);

  // Mark notification as unread
  const markAsUnread = useCallback(async (id: string, silent: boolean = false) => {
    if (!user) return;

    try {
      await notificationApi.markAsUnread(id);
      setNotifications(prev =>
        prev.map(notif => 
          notif.id === id ? { ...notif, is_read: false } : notif
        )
      );
      if (!silent) {
        toast({
          title: common('success'),
          description: t('toast.marked_as_unread'),
        });
      }
    } catch (err: any) {
      if (!silent) {
        toast({
          title: common('error'),
          description: t('toast.failed_to_mark_unread'),
          variant: 'destructive',
        });
      }
    }
  }, [toast, user, t, common]);

  // Mark notification as read when displayed in detail pane
  const markAsReadWhenDisplayed = useCallback(async (notification: Notification) => {
    if (!notification.is_read) {
      await markAsRead(notification.id, true); // Silent mark as read
    }
  }, [markAsRead]);

  // Mark all notifications as read
  const markAllAsRead = useCallback(async () => {
    if (!user) return;

    try {
      const result = await notificationApi.markAllAsRead();
      setNotifications(prev =>
        prev.map(notif => ({ ...notif, is_read: true }))
      );
      toast({
        title: common('success'),
        description: result.message,
      });
    } catch (err: any) {
      toast({
        title: common('error'),
        description: t('toast.failed_to_mark_all_read'),
        variant: 'destructive',
      });
    }
  }, [toast, user, t, common]);

  // Delete notification
  const deleteNotification = useCallback(async (id: string) => {
    if (!user) return;

    try {
      await notificationApi.deleteNotification(id);
      setNotifications(prev => prev.filter(notif => notif.id !== id));
      // Remove from lastNotificationIds as well
      lastNotificationIds.current.delete(id);
      toast({
        title: common('success'),
        description: t('toast.notification_deleted'),
      });
    } catch (err: any) {
      toast({
        title: common('error'),
        description: t('toast.failed_to_delete'),
        variant: 'destructive',
      });
    }
  }, [toast, user, t, common]);

  // Create notification (for testing)
  const createNotification = useCallback(async (data: {
    user_id: string;
    title: string;
    content: string;
    type?: string;
    org_id?: string;
  }) => {
    if (!user) return;

    try {
      const result = await notificationApi.createNotification(data);
      await fetchNotifications(); // Refresh the list (with loading state)
      toast({
        title: common('success'),
        description: t('toast.notification_created'),
      });
      return result;
    } catch (err: any) {
      toast({
        title: common('error'),
        description: t('toast.failed_to_create'),
        variant: 'destructive',
      });
      throw err;
    }
  }, [fetchNotifications, toast, user, t, common]);

  // Auto-fetch notifications on mount when user is available
  useEffect(() => {
    if (user) {
      fetchNotifications(); // Initial load with loading state
    } else {
      setLoading(false);
      setError(t('toast.not_authenticated'));
    }
  }, [fetchNotifications, user, t]);

  // Auto-refresh notifications every 2 minutes in background (SILENT)
  useEffect(() => {
    if (!user) return;

    const interval = setInterval(() => {
      fetchNotificationsSilent(); // Silent background refresh
    }, 120000); // 2 minutes (120,000 ms)

    return () => clearInterval(interval);
  }, [fetchNotificationsSilent, user]);

  // Calculate unread count
  const unreadCount = notifications.filter(n => !n.is_read).length;

  const value: NotificationContextType = {
    notifications,
    unreadCount,
    loading,
    error,
    fetchNotifications: (unreadOnly) => fetchNotifications(unreadOnly, false), // Expose non-silent version
    markAsRead,
    markAsUnread,
    markAsReadWhenDisplayed,
    markAllAsRead,
    deleteNotification,
    createNotification,
    refetch: () => fetchNotifications(false, false), // Non-silent refetch
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotificationContext() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotificationContext must be used within a NotificationProvider');
  }
  return context;
}
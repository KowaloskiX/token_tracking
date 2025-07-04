"use client";

import React, { useState, useEffect } from 'react';
import { NotificationList } from '@/components/dashboard/notifications/NotificationList';
import { NotificationContent } from '@/components/dashboard/notifications/NotificationContent';
import { useNotifications } from '@/hooks/useNotifications';
import { useNotificationsTranslations } from '@/hooks/useTranslations';
import { Notification } from '@/types/notification';

export default function NotificationsPage() {
    const {
        notifications,
        loading,
        error,
        unreadCount,
        markAsRead,
        markAsUnread,
        markAsReadWhenDisplayed,
        markAllAsRead,
        deleteNotification,
    } = useNotifications();

    const t = useNotificationsTranslations();
    const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);

    // Update selected notification when notifications change
    useEffect(() => {
        if (notifications.length > 0) {
            if (!selectedNotification) {
                setSelectedNotification(notifications[0]);
            } else {
                const stillExists = notifications.find(n => n.id === selectedNotification.id);
                if (!stillExists) {
                    setSelectedNotification(notifications[0]);
                }
            }
        } else {
            setSelectedNotification(null);
        }
    }, [notifications, selectedNotification]);

    const handleDelete = async (id: string) => {
        try {
            await deleteNotification(id);
        } catch (error) {
            console.error('Failed to delete notification:', error);
        }
    };

    const handleMarkAllAsRead = async () => {
        try {
            await markAllAsRead();
        } catch (error) {
            console.error('Failed to mark all notifications as read:', error);
        }
    };

    // Render different content based on state
    const renderContent = () => {
        if (loading) {
            return (
                <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                        <p className="text-muted-foreground">{t('loading')}</p>
                    </div>
                </div>
            );
        }

        if (error) {
            return (
                <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                        <p className="text-red-500 mb-2">{t('error_loading')}</p>
                        <p className="text-sm text-muted-foreground">{error}</p>
                    </div>
                </div>
            );
        }

        return (
            <div className="flex h-full">
                <NotificationList
                    notifications={notifications}
                    selectedNotification={selectedNotification}
                    onSelect={setSelectedNotification}
                    onDelete={handleDelete}
                />
                <div className="flex-1 min-w-0">
                    <NotificationContent 
                        notification={selectedNotification} 
                        onDelete={handleDelete}
                        onMarkAsRead={markAsRead}
                        onMarkAsUnread={markAsUnread}
                        onMarkAsReadWhenDisplayed={markAsReadWhenDisplayed}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className="w-full flex h-[100svh] overflow-hidden">
            <div className="flex-1 flex flex-col overflow-hidden min-w-0">
                {/* <div className="flex-none">
                    <NotificationHeader 
                        unreadCount={loading ? 0 : unreadCount} 
                        onMarkAllAsRead={loading ? () => {} : handleMarkAllAsRead} 
                    />
                </div> */}
                <div className="flex-1 overflow-auto scrollbar-hide">
                    <div className="sm:px-8 sm:py-3 py-2 h-full">
                        <div className="rounded-none sm:rounded-lg shadow border bg-background h-full">
                            {renderContent()}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
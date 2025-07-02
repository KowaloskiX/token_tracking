import { handleResponse } from './api';
import { Notification } from '@/types/notification';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const NOTIFICATIONS_ENDPOINT = `${API_BASE}/notifications`;

// Get auth token from localStorage
function getAuthHeaders() {
  // Check common token storage locations in localStorage
  const token = localStorage.getItem('access_token') || 
                localStorage.getItem('token') || 
                localStorage.getItem('authToken');
  
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
}

export const notificationApi = {
  // Get all notifications for current user
  async getNotifications(unreadOnly: boolean = false): Promise<Notification[]> {
    const url = unreadOnly 
      ? `${NOTIFICATIONS_ENDPOINT}/?unread_only=true`
      : `${NOTIFICATIONS_ENDPOINT}/`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });

    const data = await handleResponse<any[]>(response);
    
    // Convert _id to id for frontend compatibility
    return data.map(notification => ({
      ...notification,
      id: notification._id || notification.id
    }));
  },

  // Mark a notification as read
  async markAsRead(notificationId: string): Promise<{ message: string }> {
    const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/mark-read/${notificationId}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    return handleResponse<{ message: string }>(response);
  },

  // Mark a notification as unread
  async markAsUnread(notificationId: string): Promise<{ message: string }> {
    const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/mark-unread/${notificationId}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    return handleResponse<{ message: string }>(response);
  },

  // Mark all notifications as read
  async markAllAsRead(): Promise<{ message: string }> {
    const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/mark-all-read`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    return handleResponse<{ message: string }>(response);
  },

  // Delete a notification
  async deleteNotification(notificationId: string): Promise<{ message: string }> {
    const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/${notificationId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    return handleResponse<{ message: string }>(response);
  },

  // Create a notification (for testing - only works with test user)
  async createNotification(data: {
    user_id: string;
    title: string;
    content: string;
    type?: string;
    org_id?: string;
  }): Promise<{ id: string }> {
    const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });

    return handleResponse<{ id: string }>(response);
  },
};
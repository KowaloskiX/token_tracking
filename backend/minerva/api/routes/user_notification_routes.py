from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from bson import ObjectId
from minerva.core.models.notification import Notification
from minerva.core.models.user import User
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.database.database import db
from datetime import datetime
from pydantic import BaseModel
from minerva.core.utils.notification_utils import send_notification
from zoneinfo import ZoneInfo

router = APIRouter()

class NotificationCreateRequest(BaseModel):
    user_id: str
    title: str
    content: str
    type: str = "info"
    org_id: str = None

@router.get("/", response_model=List[Notification])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    unread_only: bool = False,
):
    """
    Get a list of notifications for the current user.
    Optionally filter to only unread notifications.
    """
    query = {"user_id": current_user.id}
    if unread_only:
        query["is_read"] = False
    # Fetch notifications from the database, sorted by creation date (newest first)
    notifications = await db["notifications"].find(query).sort("created_at", -1).to_list(length=100)
    # Convert created_at to Europe/Warsaw timezone
    for n in notifications:
        if n.get("created_at"):
            n["created_at"] = n["created_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))
    return [Notification.parse_obj(n) for n in notifications]

@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Mark a specific notification as read for the current user.
    """
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID.")
    # Update the notification's is_read field to True
    result = await db["notifications"].update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user.id},
        {"$set": {"is_read": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found or not yours.")
    return {"message": "Notification marked as read."}

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific notification for the current user.
    """
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID.")
    # Delete the notification from the database
    result = await db["notifications"].delete_one(
        {"_id": ObjectId(notification_id), "user_id": current_user.id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found or not yours.")
    return {"message": "Notification deleted."}

@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
):
    """
    Mark all unread notifications as read for the current user.
    """
    # Update all unread notifications for the user to is_read=True
    result = await db["notifications"].update_many(
        {"user_id": current_user.id, "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": f"Marked {result.modified_count} notifications as read."}

@router.post("/", response_model=dict)
async def create_notification(
    req: NotificationCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a notification for a user (for testing/admin purposes).
    Only allowed for Asystent AI test user (id: 67b4831ce1bf3b16f923e890).
    """
    if str(current_user.id) != "67b4831ce1bf3b16f923e890":
        raise HTTPException(status_code=403, detail="Not authorized to create notifications.")

    notif_id = await send_notification(
        user_id=req.user_id,
        title=req.title,
        content=req.content,
        notif_type=req.type,
        org_id=req.org_id,
    )
    return {"id": notif_id}

@router.post("/mark-unread/{notification_id}")
async def mark_notification_unread(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Mark a specific notification as unread for the current user.
    """
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID.")
    # Update the notification's is_read field to False
    result = await db["notifications"].update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user.id},
        {"$set": {"is_read": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found or not yours.")
    return {"message": "Notification marked as unread."}
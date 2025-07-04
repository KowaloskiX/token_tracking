from minerva.core.models.notification import Notification
from minerva.core.database.database import db
from datetime import datetime
from bson import ObjectId

async def send_notification(
    user_id: str,
    title: str,
    content: str,
    notif_type: str = "info",
    org_id: str = None,
):
    """
    Store a notification for a user in the database.
    Notification types:
        - info
        - warning
        - success
        - error
        - tender_update
        - tender_outcome
    """
    # Create a Notification object with the provided details
    notification = Notification(
        user_id=ObjectId(user_id),
        org_id=org_id,
        title=title,
        content=content,
        type=notif_type,
        is_read=False,
        created_at=datetime.utcnow(),
    )
    # Insert the notification into the 'notifications' collection in the database
    result = await db["notifications"].insert_one(notification.dict(by_alias=True))
    # Return the inserted notification's ID as a string
    return str(result.inserted_id)
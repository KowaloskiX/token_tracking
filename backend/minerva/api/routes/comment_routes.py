from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from zoneinfo import ZoneInfo  # <-- New import
from pydantic import BaseModel

from minerva.core.models.comment import Comment
from minerva.core.models.user import User  # User model for authentication and authorization
from minerva.core.middleware.auth.jwt import get_current_user  # Middleware to get the current user
from minerva.core.database.database import db  # Database connection

router = APIRouter()

# Extended model that includes the user information.
class CommentOut(Comment):
    user_info: Optional[dict] = None  # Additional field to include user details

    class Config:
        arbitrary_types_allowed = True  # Allow arbitrary types like ObjectId

# ---------------------------------------------------------
# GET: Fetch comments for a given tender (analysis result)
# ---------------------------------------------------------
@router.get("/", response_model=List[CommentOut])
async def get_comments(
    tender_id: str = Query(..., description="ID of the tender analysis result"),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch all comments associated with a specific tender analysis result.
    The comments are filtered based on the user's organization or user ID.
    """
    # Validate the tender ID
    if not ObjectId.is_valid(tender_id):
        raise HTTPException(status_code=400, detail="Invalid tender ID.")

    # Check if user belongs to an organization
    if current_user.org_id and current_user.org_id.strip():
        # User is in an organization: fetch only comments attached to that org.
        query = {
            "tender_id": ObjectId(tender_id),
            "org_id": current_user.org_id
        }
    else:
        # User is not in an organization: fetch only private comments (without org_id)
        # that were created by them.
        query = {
            "tender_id": ObjectId(tender_id),
            "$or": [
                {"org_id": None},
                {"org_id": ""}
            ],
            "user_id": current_user.id
        }
    
    # MongoDB aggregation pipeline to fetch comments and join user information
    pipeline = [
        {"$match": query},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "tender_id": 1,
            "user_id": 1,
            "org_id": 1,
            "text": 1,
            "created_at": 1,
            "updated_at": 1,
            "user_info.name": 1,
            "user_info.avatar_img": 1
        }},
        {"$sort": {"created_at": -1}}
    ]
    comments = await db["comments"].aggregate(pipeline).to_list(length=None)  # Execute the pipeline

    # Convert UTC timestamps to the Polish timezone (Europe/Warsaw)
    for comment in comments:
        if comment.get("created_at"):
            comment["created_at"] = comment["created_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))
        if comment.get("updated_at"):
            comment["updated_at"] = comment["updated_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))
            
    return [CommentOut.parse_obj(comment) for comment in comments]  # Parse and return the results

# ---------------------------------------------------------
# POST: Create a new comment
# ---------------------------------------------------------
class CommentCreate(BaseModel):
    tender_id: str  # tender or tender_analysis_result id as string.
    text: str  # The content of the comment

@router.post("/", response_model=Comment)
async def create_comment(
    data: CommentCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new comment for a specific tender analysis result.
    The comment is associated with the current user and their organization.
    """
    # Validate the tender ID
    if not ObjectId.is_valid(data.tender_id):
        raise HTTPException(status_code=400, detail="Invalid tender ID.")
    
    # Create a new comment object
    comment = Comment(
        tender_id=ObjectId(data.tender_id),
        user_id=current_user.id,
        org_id=current_user.org_id or "",  # Use an empty string if org_id is not present
        text=data.text,
        created_at=datetime.utcnow(),  # Set the creation timestamp
        updated_at=None  # No updates initially
    )
    
    # Insert the comment into the database
    result = await db["comments"].insert_one(comment.dict(by_alias=True))
    created = await db["comments"].find_one({"_id": result.inserted_id})
    
    # Convert the created_at timestamp from UTC to Polish timezone (Europe/Warsaw)
    if created.get("created_at"):
        created["created_at"] = created["created_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))
    
    return Comment.parse_obj(created)  # Parse and return the created comment

# ---------------------------------------------------------
# PUT: Update an existing comment
# ---------------------------------------------------------
class CommentUpdate(BaseModel):
    text: str  # The updated text of the comment

@router.put("/{comment_id}", response_model=Comment)
async def update_comment(
    comment_id: str,
    update_data: CommentUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update the text of an existing comment.
    Only the user who created the comment can update it.
    """
    # Validate the comment ID
    if not ObjectId.is_valid(comment_id):
        raise HTTPException(status_code=400, detail="Invalid comment ID.")
    
    # Fetch the comment from the database
    comment = await db["comments"].find_one({"_id": ObjectId(comment_id)})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    
    # Ensure the current user is the owner of the comment
    if str(comment["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to update this comment.")
    
    # Update the comment's text and timestamp
    update_fields = {
        "text": update_data.text,
        "updated_at": datetime.utcnow()  # Set the update timestamp
    }
    await db["comments"].update_one({"_id": ObjectId(comment_id)}, {"$set": update_fields})
    updated = await db["comments"].find_one({"_id": ObjectId(comment_id)})  # Fetch the updated comment

    # Convert the creadet_at and updated_at timestamp from UTC to Polish timezone (Europe/Warsaw)
    if updated.get("created_at"):
        updated["created_at"] = updated["created_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))
    if updated.get("updated_at"):
        updated["updated_at"] = updated["updated_at"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Warsaw"))

    return Comment.parse_obj(updated)  # Parse and return the updated comment

# ---------------------------------------------------------
# DELETE: Remove a comment
# ---------------------------------------------------------
@router.delete("/{comment_id}", response_model=dict)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an existing comment.
    Only the user who created the comment can delete it.
    """
    # Validate the comment ID
    if not ObjectId.is_valid(comment_id):
        raise HTTPException(status_code=400, detail="Invalid comment ID.")
    
    # Fetch the comment from the database
    comment = await db["comments"].find_one({"_id": ObjectId(comment_id)})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    
    # Ensure the current user is the owner of the comment
    if str(comment["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment.")
    
    # Delete the comment from the database
    result = await db["comments"].delete_one({"_id": ObjectId(comment_id)})
    if result.deleted_count == 1:
        return {"message": "Comment deleted successfully."}  # Return success message
    
    # Handle unexpected deletion failure
    raise HTTPException(status_code=500, detail="Failed to delete comment.")
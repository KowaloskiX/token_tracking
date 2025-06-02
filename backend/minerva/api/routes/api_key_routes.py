# backend/minerva/api/routes/api_key_routes.py
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.middleware.auth.api_key import generate_api_key, hash_api_key
from minerva.core.models.user import User
from minerva.core.database.database import db

router = APIRouter()

class ApiKeyResponse(BaseModel):
    api_key: str
    created_at: datetime
    last_used: Optional[datetime] = None

class ApiKeyInfo(BaseModel):
    has_api_key: bool
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    # Note: We don't return the actual key for security

@router.get("/info", response_model=ApiKeyInfo)
async def get_api_key_info(current_user: User = Depends(get_current_user)):
    """Get information about user's API key without revealing the key itself"""
    try:
        user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
        
        has_api_key = bool(user.get("api_key_hash"))
        api_key_created = user.get("api_key_created_at")
        api_key_last_used = user.get("api_key_last_used")
        
        return ApiKeyInfo(
            has_api_key=has_api_key,
            created_at=api_key_created,
            last_used=api_key_last_used
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching API key info: {str(e)}")

@router.post("/generate", response_model=ApiKeyResponse)
async def generate_user_api_key(current_user: User = Depends(get_current_user)):
    """Generate a new API key for the user (overwrites existing key if any)"""
    try:
        # Generate new API key
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)
        
        # Update user with new API key
        now = datetime.utcnow()
        update_result = await db["users"].update_one(
            {"_id": ObjectId(current_user.id)},
            {
                "$set": {
                    "api_key_hash": api_key_hash,
                    "api_key_created_at": now,
                    "api_key_last_used": None  # Reset last used
                }
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save API key")
        
        return ApiKeyResponse(
            api_key=api_key,
            created_at=now
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating API key: {str(e)}")

@router.delete("/revoke")
async def revoke_api_key(current_user: User = Depends(get_current_user)):
    """Revoke the user's API key"""
    try:
        update_result = await db["users"].update_one(
            {"_id": ObjectId(current_user.id)},
            {
                "$unset": {
                    "api_key_hash": "",
                    "api_key_created_at": "",
                    "api_key_last_used": ""
                }
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="No API key found to revoke")
        
        return {"message": "API key revoked successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error revoking API key: {str(e)}")

# Middleware to update last_used timestamp when API key is used
async def update_api_key_last_used(api_key_hash: str):
    """Update the last_used timestamp for an API key"""
    try:
        await db["users"].update_one(
            {"api_key_hash": api_key_hash},
            {"$set": {"api_key_last_used": datetime.utcnow()}}
        )
    except Exception:
        pass  # Don't fail the request if we can't update the timestamp
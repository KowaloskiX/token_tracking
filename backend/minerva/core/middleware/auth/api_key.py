# backend/minerva/core/middleware/auth/api_key.py (updated)
import secrets
import hashlib
from typing import Optional, Union
from datetime import datetime
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from minerva.core.models.user import User
from minerva.core.database.database import db
from bson import ObjectId

security = HTTPBearer(auto_error=False)

def generate_api_key() -> str:
    """Generate a new API key"""
    return f"ak_{secrets.token_urlsafe(32)}"

def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

async def get_user_by_api_key(api_key: str) -> Optional[User]:
    """Get user by API key and update last_used timestamp"""
    if not api_key or not api_key.startswith("ak_"):
        return None
    
    hashed_key = hash_api_key(api_key)
    user_doc = await db["users"].find_one({"api_key_hash": hashed_key, "active": True})
    
    if user_doc:
        # Update last_used timestamp asynchronously
        try:
            await db["users"].update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"api_key_last_used": datetime.utcnow()}}
            )
        except Exception:
            pass  # Don't fail if we can't update timestamp
        
        return User(**user_doc)
    return None

async def get_current_user_or_api_key(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None)
) -> User:
    """Get current user either from JWT token or API key"""
    from minerva.core.middleware.auth.jwt import get_current_user_from_token
    
    # Try API key first
    if x_api_key:
        user = await get_user_by_api_key(x_api_key)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Try JWT token
    if authorization:
        try:
            return await get_current_user_from_token(authorization.credentials)
        except:
            pass
    
    raise HTTPException(status_code=401, detail="Authentication required")

# Optional: Create a dependency that only accepts API key auth
async def require_api_key_auth(x_api_key: Optional[str] = Header(None)) -> User:
    """Require API key authentication only"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    user = await get_user_by_api_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return user
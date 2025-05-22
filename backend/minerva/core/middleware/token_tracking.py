from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Tuple, Optional

from minerva.config.constants import PLAN_TYPES
from minerva.core.database.database import db
from minerva.core.models.user import User

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_user_token_limit(user: User) -> int:
    """
    Get the daily token limit for a user based on their plan or organization membership.
    Enterprise (org_id != None) is unlimited or some very high limit
    by default in PLAN_TYPES, but you can customize as needed.
    """
    if user.org_id:
        return PLAN_TYPES["enterprise"]["max_daily_tokens"]
    return PLAN_TYPES[user.subscription.plan_type]["max_daily_tokens"]


async def check_and_reset_tokens(user: User) -> User:
    """
    Check if tokens need to be reset (once a day at midnight UTC).
    If user.last_token_reset < today's midnight UTC, reset daily_tokens to 0.
    Returns the updated User object.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        # This is 'today' at 00:00:00 UTC
        today_midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        user_reset_time = user.last_token_reset
        # Ensure we have a datetime object, possibly converting from string
        if isinstance(user_reset_time, str):
            # Force parse as UTC if there's a 'Z' or no timezone info
            user_reset_time = datetime.fromisoformat(user_reset_time.replace('Z', '+00:00'))

        # If last_token_reset is naive, assume UTC
        if user_reset_time.tzinfo is None:
            user_reset_time = user_reset_time.replace(tzinfo=timezone.utc)

        # Compare the user's reset time to midnight UTC today
        if user_reset_time < today_midnight_utc:
            # It's a new day, so reset the daily token count
            result = await db['users'].find_one_and_update(
                {"_id": user.id},
                {
                    "$set": {
                        "daily_tokens": 0,
                        "last_token_reset": today_midnight_utc
                    }
                },
                return_document=True
            )
            return User(**result)
        
        return user

    except Exception as e:
        logger.error(f"Error in check_and_reset_tokens: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking tokens: {str(e)}")


async def check_token_limit(user: User) -> Tuple[Optional[User], Optional[JSONResponse]]:
    """
    Check if user has exceeded their daily token limit.
    - Calls check_and_reset_tokens(user) to reset daily_tokens if needed.
    - If limit is exceeded, returns (None, JSONResponse).
    - If okay, returns (updated_user, None).
    """
    try:
        updated_user = await check_and_reset_tokens(user)
        daily_limit = await get_user_token_limit(updated_user)
        
        if updated_user.daily_tokens >= daily_limit:
            # Calculate the next reset time (midnight UTC of the *next* day)
            next_reset = updated_user.last_token_reset.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            
            plan_name = PLAN_TYPES[
                "enterprise" if updated_user.org_id else updated_user.subscription.plan_type
            ]["name"]
            
            return None, JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "message": f"Daily token limit exceeded for {plan_name} plan",
                        "current_usage": updated_user.daily_tokens,
                        "limit": daily_limit,
                        "next_reset": next_reset.isoformat(),
                        "plan": plan_name
                    }
                }
            )
        
        return updated_user, None

    except Exception as e:
        logger.error(f"Error checking token limit: {str(e)}", exc_info=True)
        return None, JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


async def update_user_token_usage(user_id: str, tokens_used: int):
    """
    Increment both total_tokens and daily_tokens by tokens_used.
    This is typically called *after* a request completes successfully.
    """
    try:
        result = await db['users'].find_one_and_update(
            {"_id": ObjectId(user_id)},
            {
                "$inc": {
                    "total_tokens": tokens_used,
                    "daily_tokens": tokens_used
                }
            },
            return_document=True
        )
        
        if result:
            logger.info(
                f"Updated token usage for user {user_id}: "
                f"+{tokens_used} tokens (daily: {result['daily_tokens']}, "
                f"total: {result['total_tokens']})"
            )
        else:
            logger.error(f"User {user_id} not found when updating token usage")
    except Exception as e:
        logger.error(f"Error updating token usage: {str(e)}", exc_info=True)


# Example usage in a FastAPI endpoint or route
# (You can adapt this pattern in your actual route functions)
async def token_protected_endpoint(user: User, tokens_needed: int):
    updated_user, error_response = await check_token_limit(user)
    if error_response:
        return error_response
    
    daily_limit = await get_user_token_limit(updated_user)
    
    # Make sure we won't exceed daily limit by using 'tokens_needed'
    if updated_user.daily_tokens + tokens_needed > daily_limit:
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "message": "This request would exceed your daily token limit",
                    "current_usage": updated_user.daily_tokens,
                    "requested_tokens": tokens_needed,
                    "limit": daily_limit,
                    "available_tokens": daily_limit - updated_user.daily_tokens
                }
            }
        )
    
    # If we get here, user has capacity to consume these tokens.
    # Do your main logic here (LLM call, data processing, etc.).
    # For example:
    # output = some_llm_call(...)
    
    # After successful processing, update usage:
    await update_user_token_usage(str(updated_user.id), tokens_needed)
    
    # Return response or processed data
    return {"detail": "Success", "tokens_used": tokens_needed}

import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from minerva.core.database.database import client
from minerva.core.models.user import User
from minerva.core.models.password_reset_token import PasswordResetToken
from minerva.core.utils.email_utils import send_email

router = APIRouter()

# Use the same database connection as other endpoints.
db = client.Main

# Schema for requesting a password reset.
class PasswordResetRequest(BaseModel):
    email: EmailStr

@router.post("/forgot-password", status_code=200)
async def forgot_password(request: PasswordResetRequest, background_tasks: BackgroundTasks):
    """
    Request a password reset.
    If the provided email belongs to an existing user and there is no active reset request,
    generates a reset token that expires after 1 hour, stores it using our PasswordResetToken model,
    and schedules an email. For security reasons, the response is always the same.
    For users that use Google to log in, no reset token or email is sent.
    """
    user = await db["users"].find_one({"email": request.email})
    # Always return a success message, even if the user is not found.
    if not user:
        return {"message": "If an account exists for that email, a password reset link will be sent."}

    # Do not send a reset email or create a token for Google-authenticated users.
    if user.get("google_id"):
        return {"message": "If an account exists for that email, a password reset link will be sent."}

    # Check if there is already an active (not expired) reset request for this email that hasn't been used.
    const_active = await db["password_reset_tokens"].find_one({
        "email": request.email,
        "expires_at": {"$gt": datetime.utcnow()},
        "changed": False
    })
    if const_active:
        # Return the same generic message without creating a new token.
        return {"message": "If an account exists for that email, a password reset link will be sent."}

    # Generate a secure token and expiration time if no active reset exists.
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Create a token model instance.
    reset_token = PasswordResetToken(
        email=request.email,
        token=token,
        expires_at=expires_at
    )

    # Save the token to the dedicated collection.
    await db["password_reset_tokens"].insert_one(reset_token.dict(by_alias=True))

    # Build the password reset link.
    frontend_url = os.getenv("FRONTEND_URL", "https://www.asystent.ai")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    # Use send_email with the action_url and action_text for a button.
    subject = "Resetowanie hasła"
    message = "Kliknij przycisk poniżej, aby zresetować swoje hasło."
    background_tasks.add_task(send_email, 
        request.email,
        subject,
        message,
        action_url=reset_link,
        action_text="Resetuj hasło"
    )

    return {"message": "If an account exists for that email, a password reset link will be sent."}

# Schema for resetting the password.
class PasswordReset(BaseModel):
    token: str
    password: str

@router.post("/reset-password", status_code=200)
async def reset_password(data: PasswordReset, background_tasks: BackgroundTasks):
    """
    Reset the user's password.
    Validates the provided token, updates the user's password if valid (using the same hashing as User.hash_password),
    marks the token as used by setting `changed` to True, and then sends a notification email.
    """
    record = await db["password_reset_tokens"].find_one({"token": data.token})
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # Check if token has already been used.
    if record["changed"] == True:
        raise HTTPException(status_code=400, detail="Reset token has already been used.")

    # Check token expiration.
    if record["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    # New password length check.
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    # Update the user's password using the same hash function in User.
    new_hashed_password = User.hash_password(data.password)
    update_result = await db["users"].update_one(
        {"email": record["email"]},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update password.")

    # Mark the reset token as used by setting changed to True.
    await db["password_reset_tokens"].update_one(
        {"token": data.token},
        {"$set": {"changed": True}}
    )

    # Schedule a notification email to the user.
    subject = "Twoje hasło zostało zresetowane"
    message = ("Twoje hasło na platformie Asystent AI zostało pomyślnie zresetowane. "
               "Jeśli nie dokonałeś tej zmiany, skontaktuj się z naszym działem wsparcia.")
    background_tasks.add_task(send_email,
                              record["email"],
                              subject,
                              message)

    return {"message": "Password has been reset successfully."}
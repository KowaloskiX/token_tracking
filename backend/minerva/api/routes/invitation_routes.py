# This file is still under construction. Please check back later.

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from minerva.config.constants import UserRole
from minerva.core.models.invitation import Invitation
from minerva.core.models.user import User
from minerva.core.middleware.auth.jwt import get_current_user, create_access_token
from bson import ObjectId
import secrets
from minerva.core.database.database import client
from fastapi.encoders import jsonable_encoder
from passlib.context import CryptContext
import os
from minerva.core.utils.email_utils import send_email   # updated import

db = client.Main

router = APIRouter(prefix="/invitations", tags=["invitations"])

# Schema for creating an invitation
class InvitationCreate(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER

@router.post("/", status_code=201)
async def create_invitation(
    invitation_data: InvitationCreate, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new invitation.
    """
    
    # Require admin role
    if current_user.org_id and current_user.role and current_user.role != "admin" and current_user.org_id != "":
        raise HTTPException(status_code=403, detail="Only admins can invite new members")
    
    # Prevent self-invitation
    if invitation_data.email == current_user.email:
        raise HTTPException(status_code=400, detail="You cannot invite yourself.")
        
    # Only check if the current user already belongs to an organization
    if current_user.org_id and current_user.org_id != "":
        existing_user_member = await db["users"].find_one({
            "email": invitation_data.email,
            "org_id": current_user.org_id
        })
        if existing_user_member:
            raise HTTPException(status_code=400, detail="This user is already a member of your organization.")
    
    # Check if an invitation already exists for this email in the same organization
    existing_invitation = await db["invitations"].find_one({
        "email": invitation_data.email, 
        "org_id": current_user.org_id,  # limit to the same organization
        "accepted": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    if existing_invitation:
        raise HTTPException(status_code=400, detail="An active invitation for this email already exists.")

    # If the current user does not have an org_id, generate one and update the user record.
    if not current_user.org_id:
        new_org_id = str(ObjectId())
        current_user.org_id = new_org_id
        # Set the current user's role to "admin" because they're creating a new organization.
        await db["users"].update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"org_id": new_org_id, "role": "admin"}}
        )
    else:
        new_org_id = current_user.org_id

    # Generate a unique token
    token = secrets.token_hex(16)
    while await db["invitations"].find_one({"token": token}):
        token = secrets.token_hex(16)

    # Prepare the invitation data
    invitation_dict = invitation_data.dict()
    invitation_dict["org_id"] = new_org_id
    invitation_dict["invited_by"] = ObjectId(current_user.id)
    invitation_dict["token"] = token
    invitation_dict["created_at"] = datetime.utcnow()
    invitation_dict["accepted"] = False
    invitation_dict["expires_at"] = datetime.utcnow() + timedelta(days=7)

    # Save the invitation to the database
    await db["invitations"].insert_one(invitation_dict)

    # Prepare invitation link for the email.
    frontend_url = os.getenv("FRONTEND_URL", "https://www.asystent.ai")  # adjust default if needed
    invitation_link = f"{frontend_url}/accept-invitation?token={token}"
    
    # Schedule the email to be sent in the background.
    background_tasks.add_task(
        send_email,
        to_email=invitation_data.email,
        subject="Zaproszenie do dołączenia do organizacji",  # subject (will be prefixed automatically)
        title="Zaproszenie do organizacji",
        message="Zostałeś zaproszony do dołączenia do naszej platformy. Kliknij przycisk poniżej, aby zaakceptować zaproszenie.",
        action_url=invitation_link,
        action_text="Akceptuj zaproszenie"
    )

    # Convert ObjectId values to strings for the response
    return {
        "message": "Invitation created successfully",
        "invitation": jsonable_encoder(invitation_dict, custom_encoder={ObjectId: str})
    }

# Schema for accepting an invitation
class InvitationAccept(BaseModel):
    token: str       # The invitation token to validate
    email: EmailStr  # The email address of the user accepting the invitation
    password: str    # The password for the account
    name: str        # The user's name

@router.post("/accept", status_code=200)
async def accept_invitation(invitation: InvitationAccept):
    """
    Accept an invitation and join the organization.
    
    - If a user with the provided email exists, update their organization and role.
    - Otherwise, create a new user account using the provided email and password.
    """
    # Look up the invitation by token
    invitation_db = await db["invitations"].find_one({"token": invitation.token})
    if not invitation_db:
        raise HTTPException(status_code=400, detail="Invalid invitation token.")
    
    # Validate expiration
    if invitation_db["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation has expired.")
    
    # Ensure invitation hasn't already been accepted
    if invitation_db.get("accepted"):
        raise HTTPException(status_code=400, detail="Invitation has already been accepted.")
    
    # Verify the invitation email matches the provided email
    if invitation_db["email"] != invitation.email:
        raise HTTPException(status_code=400, detail="Invitation email does not match.")
    
    # Prepare password context for hashing
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Check if a user with this email already exists
    existing_user = await db["users"].find_one({"email": invitation.email})

    if existing_user:
        # Allow organization switching if user is the only member of their current org
        # or if they have no organization
        current_org_id = existing_user.get("org_id")
        can_switch_org = True
        
        if current_org_id and current_org_id != "":
            # Count the number of users in the current organization
            member_count = await db["users"].count_documents({"org_id": current_org_id})
            
            # If user is the only member, they can switch (their org will become empty)
            # If there are multiple members, check if user is admin and if there are other admins
            if member_count > 1:
                user_role = existing_user.get("role", "member")
                if user_role == "admin":
                    # Check if there are other admins in the organization
                    admin_count = await db["users"].count_documents({
                        "org_id": current_org_id,
                        "role": "admin",
                        "_id": {"$ne": existing_user["_id"]}  # Exclude current user
                    })
                    if admin_count == 0:
                        # User is the only admin, cannot leave without transferring admin role
                        raise HTTPException(
                            status_code=400, 
                            detail="Cannot join another organization as you are the only admin of your current organization. Please assign another admin first."
                        )
        
        # Verify the provided password matches the stored hashed password
        if not pwd_context.verify(invitation.password, existing_user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Incorrect password.")
        
        # Update their organization and role based on the invitation
        update_fields = {
            "org_id": invitation_db["org_id"],
            "role": invitation_db["role"]
        }
        await db["users"].update_one({"_id": existing_user["_id"]}, {"$set": update_fields})
        user_id = str(existing_user["_id"])
        
        # If the user was the only member of their previous organization, we could optionally delete it
        # For now, we'll leave empty organizations in the database
        if current_org_id and current_org_id != "":
            remaining_members = await db["users"].count_documents({"org_id": current_org_id})
            if remaining_members == 0:
                # Optional: Delete the empty organization
                await db["organizations"].delete_one({"_id": ObjectId(current_org_id)})
    else:
        # Check password length
        if len(invitation.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        
        # Create a new user: hash the provided password and create a new record.
        hashed_password = pwd_context.hash(invitation.password)
        new_user = {
            "email": invitation.email,
            "hashed_password": hashed_password,
            "org_id": invitation_db["org_id"],
            "role": invitation_db["role"],
            "name": invitation.name,  # Use the provided name directly
            "created_at": datetime.utcnow(),
            # Include any other fields that are required by your User model.
        }
        result = await db["users"].insert_one(new_user)
        user_id = str(result.inserted_id)

    # Mark the invitation as accepted
    await db["invitations"].update_one(
        {"token": invitation.token},
        {"$set": {"accepted": True}}
    )

    # Generate JWT access token (make sure create_access_token is imported from your jwt module)
    access_token = create_access_token(data={"sub": user_id, "email": invitation.email})

    return {
        "message": "Invitation accepted successfully",
        "user_email": invitation.email,
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/by-token/{token}", status_code=200)
async def get_invitation_by_token(token: str):
    """
    Get an invitation by its token.
    Returns basic information about the invitation.
    """
    # Look up the invitation in the database using the provided token
    invitation = await db["invitations"].find_one({"token": token})
    
    # If no invitation is found, raise a 404 error
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Check if the invitation has expired
    if invitation["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation has expired")
    
    # Check if the invitation has already been accepted
    if invitation.get("accepted"):
        raise HTTPException(status_code=400, detail="Invitation has already been accepted")
    
    # Return only non-sensitive information about the invitation
    return {
        "email": invitation["email"],  # The email address associated with the invitation
        "expires_at": invitation["expires_at"].isoformat(),  # Expiration date in ISO format
        "accepted": invitation.get("accepted", False)  # Whether the invitation has been accepted
    }
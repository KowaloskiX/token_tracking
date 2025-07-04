from datetime import datetime
from typing import List, Optional
from minerva.config.constants import UserRole
from minerva.core.models.subscription import UserSubscription
from minerva.core.middleware.auth.jwt import create_access_token, get_current_user
from minerva.core.models.conversation import Conversation
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from minerva.core.database.database import db
from minerva.core.models.user import User
from bson import ObjectId
from fastapi import Query
from pydantic import BaseModel, Field
import requests
import os
from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv
from minerva.core.utils.email_utils import send_email
from minerva.core.models.organization import Organization

load_dotenv()

router = APIRouter()


class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    org_id: Optional[str] = None
    role: Optional[str] = "member"

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str = Field(..., alias="_id")
    email: str
    name: str
    org_id: Optional[str] = None
    google_id: Optional[str] = None
    avatar_img: Optional[str] = None
    role: str
    subscription: Optional[UserSubscription] = None
    created_at: datetime
    preferred_language: Optional[str] = None  # User's preferred language (pl, en, de)
    marketing_consent: dict[str, bool] = Field(
        default_factory=lambda: {
            "communication_emails": False,
            "marketing_emails": False,
            "social_emails": True,
            "security_emails": True
        }
    )
    total_tokens: Optional[int] = 0
    daily_tokens: Optional[int] = 0
    last_token_reset: Optional[datetime] = None
    # Login tracking fields (optional for backward compatibility)
    last_login: Optional[datetime] = None
    login_count: Optional[int] = 0

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class PasswordVerificationRequest(BaseModel):
    password: str

@router.post("/register", response_model=dict)
async def register(user_data: UserCreate):
    if await db["users"].find_one({"email": user_data.email}):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # If no org_id is provided, create a new organization for the user
    if not user_data.org_id:
        # Create a new organization for this user
        org_name = f"{user_data.name}'s Org"
        new_organization = Organization(name=org_name)
        
        # Insert the organization into the database
        org_result = await db["organizations"].insert_one(new_organization.dict(by_alias=True))
        user_org_id = str(org_result.inserted_id)
        
        # Set user as admin since they're creating their own organization
        user_role = UserRole.ADMIN
    else:
        user_org_id = user_data.org_id
        user_role = user_data.role
    
    user = User(
        email=user_data.email,
        name=user_data.name,
        org_id=user_org_id,
        role=user_role,
        hashed_password=User.hash_password(user_data.password)
    )
    
    user_dict = user.dict(by_alias=True)
    result = await db["users"].insert_one(user_dict)
    user.id = result.inserted_id
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    user_response_dict = {
        "_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "org_id": user.org_id,
        "role": user.role,
        "subscription": user.subscription.dict() if user.subscription else None,
        "created_at": user.created_at
    }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user_response_dict)
    }


@router.post("/login")
async def login(user_data: UserLogin, request: Request):
    user_doc = await db["users"].find_one({"email": user_data.email})
    if not user_doc:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    user = User(**user_doc)
    if not user.verify_password(user_data.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    # Check if user account is active
    if not user.active:
        raise HTTPException(
            status_code=403,
            detail="Account is deactivated. Please contact support for assistance."
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    # Record login event for analytics tracking
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    await user.record_login("email_password", ip_address, user_agent)
    
    # Create response dict explicitly with the ID
    user_response_dict = {
        "_id": str(user.id),  # Explicitly include the ID
        "email": user.email,
        "name": user.name,
        "org_id": user.org_id,
        "role": user.role,
        "subscription": user.subscription.dict() if user.subscription else None,
        "created_at": user.created_at
    }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user_response_dict)
    }


# Example protected route
@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    # Convert the User model to dict and handle ObjectId conversion
    user_dict = current_user.model_dump()
    # Convert ObjectId to string explicitly
    user_dict["id"] = str(user_dict["id"])
    return UserResponse(**user_dict)

@router.post("/", response_model=User)
async def create_user(user: User):
    user_data = user.dict(by_alias=True)
    user_data["created_at"] = datetime.utcnow()
    result = await db["users"].insert_one(user_data)
    user.id = str(result.inserted_id)
    user.created_at = user_data["created_at"]
    return user

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str):
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[str] = None
    role: Optional[str] = None
    preferred_language: Optional[str] = None  # User's preferred language (pl, en, de)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, 
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    # Check if the user exists
    existing_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the user is updating their own profile
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this user")

    # Prepare update data (only include non-None values)
    update_data = {
        k: v for k, v in user_update.dict(exclude_unset=True).items()
        if v is not None
    }

    if not update_data:
        return UserResponse(**existing_user)

    # Update the user
    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="User update failed")

    # Get the updated user and convert ObjectId to string
    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])  # Convert ObjectId to string
    
    return UserResponse(**updated_user)

@router.delete("/{user_id}")
async def delete_user(user_id: str):
    result = await db["users"].delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}


@router.get("/", response_model=List[User])
async def get_all_users():
    users = await db["users"].find().to_list(length=None)
    return [User(**user) for user in users]


class PaginatedConversationsResponse(BaseModel):
    conversations: List[Conversation]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

@router.get("/{user_id}/conversations", response_model=PaginatedConversationsResponse)
async def get_user_conversations(
    user_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page")
):
    try:
        # Calculate skip and limit for pagination
        skip = (page - 1) * page_size
        
        # Get total count of conversations for this user
        total_conversations = await db["conversations"].count_documents({"user_id": user_id})
        
        # Calculate total pages
        total_pages = (total_conversations + page_size - 1) // page_size
        
        # Get paginated conversations, sorted by last_updated
        cursor = db["conversations"].find(
            {"user_id": user_id}
        ).sort(
            "last_updated", -1  # Sort by last_updated in descending order
        ).skip(skip).limit(page_size)
        
        # Convert cursor to list of conversations
        conversations = [
            Conversation.parse_obj(conv) 
            async for conv in cursor
        ]
        
        return PaginatedConversationsResponse(
            conversations=conversations,
            total=total_conversations,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversations: {str(e)}"
        )

@router.put("/{user_id}/consent", response_model=UserResponse)
async def update_marketing_consent(
    user_id: str,
    consent_data: dict[str, bool],
    current_user: User = Depends(get_current_user)
):
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this user's consent")

    # Ensure security_emails can't be disabled
    if "security_emails" in consent_data:
        consent_data["security_emails"] = True

    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"marketing_consent": consent_data}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Consent update failed")

    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])
    
    return UserResponse(**updated_user)


class GoogleAuthRequest(BaseModel):
    credential: str

@router.post("/auth/google")
async def google_auth(request: GoogleAuthRequest, http_request: Request):
    try:
        request_obj = google_requests.Request()
        idinfo = id_token.verify_oauth2_token(
            request.credential,
            request_obj,
            os.getenv("GOOGLE_CLIENT_ID"),
            clock_skew_in_seconds=10
        )

        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        # Get user profile picture from Google People API
        google_id = idinfo['sub']
        profile_pic_url = f"https://www.googleapis.com/oauth2/v1/userinfo?alt=json&access_token={request.credential}"
        
        try:
            profile_response = requests.get(profile_pic_url)  # Use requests here
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                picture_url = profile_data.get('picture')
            else:
                picture_url = None
        except:
            picture_url = None

        user_data = {
            "email": idinfo['email'],
            "name": idinfo['name'],
            "avatar_img": picture_url,
            "google_id": google_id
        }

        # Check if user exists
        existing_user = await db["users"].find_one({"email": user_data["email"]})
        
        if existing_user:
            # Check if user is active
            if not existing_user.get("active", True):
                raise HTTPException(
                    status_code=403,
                    detail="Account is deactivated. Please contact support for assistance."
                )
                
            # Always update Google info including avatar
            update_data = {
                "google_id": user_data["google_id"],
                "avatar_img": user_data["avatar_img"]
            }
            
            await db["users"].update_one(
                {"_id": existing_user["_id"]},
                {"$set": update_data}
            )
            
            user_response_dict = {
                "_id": str(existing_user["_id"]),
                "email": existing_user["email"],
                "name": existing_user["name"],
                "org_id": existing_user.get("org_id"),
                "role": existing_user.get("role", "member"),
                "google_id": user_data["google_id"],
                "avatar_img": user_data["avatar_img"],  # Use the new avatar from Google
                "subscription": existing_user.get("subscription"),
                "created_at": existing_user.get("created_at", datetime.utcnow()),
                "marketing_consent": existing_user.get("marketing_consent", {
                    "communication_emails": False,
                    "marketing_emails": False,
                    "social_emails": True,
                    "security_emails": True
                }),
                "total_tokens": existing_user.get("total_tokens", 0),
                "daily_tokens": existing_user.get("daily_tokens", 0),
                "last_token_reset": existing_user.get("last_token_reset")
            }
        else:
            # Create new user
            new_user_dict = {
                "email": user_data["email"],
                "name": user_data["name"],
                "google_id": user_data["google_id"],
                "avatar_img": user_data["avatar_img"],
                "role": "member",
                "created_at": datetime.utcnow(),
                "active": True,
                "marketing_consent": {
                    "communication_emails": False,
                    "marketing_emails": False,
                    "social_emails": True,
                    "security_emails": True
                },
                "total_tokens": 0,
                "daily_tokens": 0
            }
            
            result = await db["users"].insert_one(new_user_dict)
            new_user_dict["_id"] = str(result.inserted_id)
            user_response_dict = new_user_dict

        # Record login event for analytics tracking
        if existing_user:
            # For existing users, get the User object to call record_login
            user_obj = User(**existing_user)
            ip_address = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("User-Agent")
            await user_obj.record_login("google_oauth", ip_address, user_agent)
        else:
            # For new users, we'll record the login after creation
            # Create a User object from the new user dict
            user_obj = User(**{**new_user_dict, "_id": ObjectId(new_user_dict["_id"])})
            ip_address = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("User-Agent")
            await user_obj.record_login("google_oauth", ip_address, user_agent)

        # Create access token
        access_token = create_access_token(
            data={"sub": str(user_response_dict["_id"]), "email": user_response_dict["email"]}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse(**user_response_dict)
        }

    except ValueError as e:
        print(f"Google auth error: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Google auth error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Add this schema for the password change request
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password", status_code=200)
async def change_password(
    data: PasswordChangeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    # Verify the current password
    if not current_user.verify_password(data.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    
    # Validate new password length
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    
    # Hash the new password and update the record
    new_hashed_password = User.hash_password(data.new_password)
    update_result = await db["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update password.")
    
    # Schedule a notification email to the user after password change
    subject = "Twoje hasło zostało zmienione"
    message = (
        "Twoje hasło na platformie Asystent AI zostało pomyślnie zmienione. "
        "Jeśli nie dokonałeś tej zmiany, skontaktuj się z naszym działem wsparcia."
    )
    background_tasks.add_task(send_email, current_user.email, subject, message)
    
    return {"message": "Password changed successfully."}

@router.get("/fetch/enterprise", response_model=List[UserResponse])
async def get_enterprise_users(current_user: User = Depends(get_current_user)):
    # Query for users that have org_id (which makes them enterprise users per the effective_plan property)
    # or explicitly have enterprise subscription type
    enterprise_users = await db["users"].find({
        "$or": [
            {"org_id": {"$ne": None, "$exists": True}},  # Users with org_id are enterprise users
            {"subscription.plan_type": "enterprise"}     # Users with explicit enterprise plan
        ]
    }).to_list(length=None)
    
    # Filter to ensure only enterprise users are returned (double-check)
    filtered_users = []
    for user in enterprise_users:
        # Apply the same logic as in User.effective_plan property
        if user.get("org_id") or user.get("subscription", {}).get("plan_type") == "enterprise":
            filtered_users.append(user)
    
    # Convert to UserResponse objects
    return [UserResponse(**{**user, "_id": str(user["_id"])}) for user in filtered_users]

@router.post("/send-test-email", status_code=200)
async def send_test_email(current_user: User = Depends(get_current_user)):
    # Verify the user has admin role
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admin users can send test emails"
        )
    
    # Send a test email
    test_email = "peter@yepp.ai"
    subject = "Dezaktywacja konta"
    message = (
            "Dzień dobry,<br><br>"
            f"Pragniemy poinformować, że <b>Asystent AI</b> wchodzi w nowy, ekscytujący etap rozwoju.<br>"
            f"Zamykamy wersję Standard, aby skupić się w pełni na nowej, profesjonalnej odsłonie platformy – <b>Asystent AI Przetargi</b>, czyli inteligentnym agencie AI, który automatycznie wyszukuje i analizuje przetargi z wielu źródeł.<br><br>"
            f"<b>Co to oznacza dla Ciebie?</b><br>"
            f"Twoje dotychczasowe konto zostało dezaktywowane, a wszystkie plany – wyłączone. Żadne opłaty nie będą już pobierane.<br><br>"
            f"<b>Ale każdy koniec może być nowym początkiem!</b><br>"
            f"Jeśli świat przetargów publicznych i zamówień nie jest Ci obcy – mamy coś, co może zrewolucjonizować Twój sposób pracy.<br>"
            f"Chętnie pokażemy Ci, jak nasz nowy Asystent może oszczędzać czas, zwiększać skuteczność i dostarczać tylko najbardziej dopasowane okazje.<br>"
        )
    title = "Nowy wymiar Asystenta AI"
    action_url = "https://asystent.ai"
    action_text = "Sprawdź Asystenta Przetargowego"
    
    try:
        await send_email(
            to_email=test_email,
            subject=subject,
            message=message,
            title=title,
            action_url=action_url,
            action_text=action_text
        )
        return {"message": f"Test email sent successfully to {test_email}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test email: {str(e)}"
        )
    
@router.put("/{user_id}/set-active-status")
async def set_user_active_status(
    user_id: str,
    active_status: bool,
    current_user: User = Depends(get_current_user)
):
    # Ensure the user has admin privileges
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can change account active status"
        )
    
    # Update the user's active status
    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active": active_status}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found or no changes were made"
        )
    
    # Get the updated user
    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare notification if account was deactivated
    if not active_status:
        # Schedule email notification about account deactivation
        subject = "Dezaktywacja konta"
        message = (
            f"Dzień dobry,<br><br>"
            f"Pragniemy poinformować, że Twoje konto w serwisie <b>Asystent AI</b> zostało dezaktywowane.<br><br>"
            f"Jeśli masz pytania lub uważasz, że to pomyłka, prosimy o kontakt z naszym działem obsługi klienta.<br><br>"
            f"Pozdrawiam,<br>Asystent AI :)"
        )
        try:
            await send_email(
                to_email=updated_user["email"],
                subject=subject,
                message=message,
                title="Informacja o koncie"
            )
        except Exception as e:
            print(f"Error sending deactivation email: {str(e)}")
    
    return {"message": f"User active status set to {active_status}", "user_id": user_id}

@router.post("/activate-all-users", status_code=200)
async def activate_all_users(current_user: User = Depends(get_current_user)):
    # Update all users to set active status to True
    result = await db["users"].update_many(
        {}, 
        {"$set": {"active": True}}
    )
    
    return {
        "message": "All users have been activated",
        "modified_count": result.modified_count,
        "matched_count": result.matched_count
    }

@router.post("/deactivate-free-users", status_code=200)
async def deactivate_free_users(current_user: User = Depends(get_current_user)):
    # Update all non-enterprise users to set active status to False
    # A user is considered non-enterprise if:
    # 1. They don't have an org_id AND
    # 2. Their subscription plan type is not "enterprise"
    result = await db["users"].update_many(
        {
            "$and": [
                {"org_id": {"$in": [None, ""]}},
                {"subscription.plan_type": {"$ne": "enterprise"}}
            ]
        }, 
        {"$set": {"active": False}}
    )
    
    # Get emails of affected users
    deactivated_users = await db["users"].find(
        {
            "$and": [
                {"org_id": {"$in": [None, ""]}},
                {"subscription.plan_type": {"$ne": "enterprise"}},
                {"active": False}
            ]
        }
    ).to_list(length=None)
    
    # Send notification emails
    sent_count = 0
    for user in deactivated_users:
        try:
            subject = "Dezaktywacja konta"
            message = (
                f"Dzień dobry,<br><br>"
                f"Pragniemy poinformować, że <b>Asystent AI</b> wchodzi w nowy, ekscytujący etap rozwoju.<br>"
                f"Zamykamy wersję Standard, aby skupić się w pełni na nowej, profesjonalnej odsłonie platformy – <b>Asystent AI Przetargi</b>, czyli inteligentnym agencie AI, który automatycznie wyszukuje i analizuje przetargi z wielu źródeł.<br><br>"
                f"<b>Co to oznacza dla Ciebie?</b><br>"
                f"Twoje dotychczasowe konto zostało dezaktywowane, a wszystkie plany – wyłączone. Żadne opłaty nie będą już pobierane.<br><br>"
                f"<b>Ale każdy koniec może być nowym początkiem!</b><br>"
                f"Jeśli świat przetargów publicznych i zamówień nie jest Ci obcy – mamy coś, co może zrewolucjonizować Twój sposób pracy.<br>"
                f"Chętnie pokażemy Ci, jak nasz nowy Asystent może oszczędzać czas, zwiększać skuteczność i dostarczać tylko najbardziej dopasowane okazje.<br>"
            )
            await send_email(
                to_email=user["email"],
                subject=subject,
                message=message,
                title="Nowy wymiar Asystenta AI",
                action_url="https://asystent.ai",
                action_text="Sprawdź Asystenta Przetargowego"
            )
            sent_count += 1
        except Exception as e:
            print(f"Error sending email to {user['email']}: {str(e)}")
    
    return {
        "message": "Free users have been deactivated",
        "modified_count": result.modified_count,
        "matched_count": result.matched_count,
        "emails_sent": sent_count
    }


@router.post("/deactivate-users-after-email", status_code=200)
async def deactivate_users_after_email(
    reference_email: str,
    batch_size: int = 5,
    email_delay_seconds: int = 2,
    current_user: User = Depends(get_current_user)
):
    """
    Send emails to all free users created after the specified reference user.
    
    Args:
        reference_email: Email of the reference user
        batch_size: Number of emails to send in a batch before waiting
        email_delay_seconds: Seconds to wait between emails
    """
    import asyncio
    
    # First, find the reference user
    reference_user = await db["users"].find_one({"email": reference_email})
    if not reference_user:
        raise HTTPException(status_code=404, detail=f"Reference user with email {reference_email} not found")
    
    reference_date = reference_user.get("created_at")
    if not reference_date:
        raise HTTPException(status_code=400, detail=f"Reference user has no creation date")
    
    # Build a more flexible query:
    #   • Users created after reference user (by ObjectId for reliability)
    #   • Users without org_id (null/empty/missing)
    #   • Users whose subscription.plan_type is not "enterprise" OR subscription field missing
    #   • Do NOT filter by active status - include inactive users
    #   • Exclude the reference user
    query = {
        "$and": [
            {"_id": {"$gt": reference_user["_id"]}},
            {"$or": [
                {"org_id": {"$exists": False}},
                {"org_id": None},
                {"org_id": ""}
            ]},
            {"$or": [
                {"subscription.plan_type": {"$exists": False}},
                {"subscription.plan_type": {"$ne": "enterprise"}}
            ]},
            {"email": {"$ne": reference_email}}
        ]
    }
    
    # Get users to send emails to
    users_to_process = await db["users"].find(query).to_list(length=None)
    
    # Set all these users as inactive (even if they're already inactive)
    update_result = await db["users"].update_many(
        query, 
        {"$set": {"active": False}}
    )
    
    # Send notification emails with rate limiting
    sent_count = 0
    error_count = 0
    rate_limited_count = 0
    processed_emails = []
    error_emails = []
    
    # Group users into batches
    user_batches = [users_to_process[i:i + batch_size] for i in range(0, len(users_to_process), batch_size)]
    
    for batch_index, batch in enumerate(user_batches):
        print(f"Processing batch {batch_index+1}/{len(user_batches)}")
        # Process each user in the batch
        for user in batch:
            try:
                user_email = user["email"]
                subject = "Dezaktywacja konta"
                message = (
                    f"Dzień dobry,<br><br>"
                    f"Pragniemy poinformować, że <b>Asystent AI</b> wchodzi w nowy, ekscytujący etap rozwoju.<br>"
                    f"Zamykamy wersję Standard, aby skupić się w pełni na nowej, profesjonalnej odsłonie platformy – <b>Asystent AI Przetargi</b>, czyli inteligentnym agencie AI, który automatycznie wyszukuje i analizuje przetargi z wielu źródeł.<br><br>"
                    f"<b>Co to oznacza dla Ciebie?</b><br>"
                    f"Twoje dotychczasowe konto zostało dezaktywowane, a wszystkie plany – wyłączone. Żadne opłaty nie będą już pobierane.<br><br>"
                    f"<b>Ale każdy koniec może być nowym początkiem!</b><br>"
                    f"Jeśli świat przetargów publicznych i zamówień nie jest Ci obcy – mamy coś, co może zrewolucjonizować Twój sposób pracy.<br>"
                    f"Chętnie pokażemy Ci, jak nasz nowy Asystent może oszczędzać czas, zwiększać skuteczność i dostarczać tylko najbardziej dopasowane okazje.<br>"
                )
                
                await send_email(
                    to_email=user_email,
                    subject=subject,
                    message=message,
                    title="Nowy wymiar Asystenta AI",
                    action_url="https://asystent.ai",
                    action_text="Sprawdź Asystenta Przetargowego"
                )
                sent_count += 1
                processed_emails.append(user_email)
                print(f"Email sent to {user_email} ({sent_count}/{len(users_to_process)})")
                
                # Add delay between each email in the batch
                await asyncio.sleep(email_delay_seconds)
                
            except Exception as e:
                error_message = str(e)
                error_emails.append(user["email"])
                print(f"Error sending email to {user['email']}: {error_message}")
                if "429 Too Many Requests" in error_message:
                    rate_limited_count += 1
                    print(f"Rate limited, waiting {email_delay_seconds * 5} seconds")
                    # If rate limited, wait longer before continuing
                    await asyncio.sleep(email_delay_seconds * 5)
                error_count += 1
        
        # Wait a bit longer between batches
        if batch_index < len(user_batches) - 1:  # Don't wait after the last batch
            print(f"Batch {batch_index+1} complete. Waiting {email_delay_seconds * 3} seconds before next batch")
            await asyncio.sleep(email_delay_seconds * 3)
    
    return {
        "message": "Emails sent to free users created after the reference user",
        "reference_email": reference_email,
        "reference_date": reference_date.isoformat(),
        "users_processed": len(users_to_process),
        "modified_count": update_result.modified_count,
        "matched_count": update_result.matched_count,
        "emails_sent": sent_count,
        "email_errors": error_count,
        "rate_limited_count": rate_limited_count,
        "processed_emails": processed_emails,
        "error_emails": error_emails
    }

@router.post("/verify-password", status_code=200)
async def verify_password(
    data: PasswordVerificationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Verify if the provided password matches the current user's password.
    Used for sensitive operations like API key generation.
    """
    if not current_user.hashed_password:
        raise HTTPException(status_code=400, detail="No password set for this account.")
    
    if not current_user.verify_password(data.password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    
    return {"message": "Password verified successfully."}

@router.post("/migrate-login-tracking", status_code=200)
async def migrate_login_tracking(current_user: User = Depends(get_current_user)):
    """
    Initialize login tracking fields for existing users.
    This should be run once after deploying the login tracking feature.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admin users can run migrations"
        )
    
    try:
        # Update all users to have login tracking fields if they don't exist
        result = await db["users"].update_many(
            {
                "$or": [
                    {"last_login": {"$exists": False}},
                    {"login_history": {"$exists": False}},
                    {"login_count": {"$exists": False}}
                ]
            },
            {
                "$set": {
                    "last_login": None,
                    "login_count": 0,
                    "login_history": []
                }
            }
        )
        
        return {
            "message": "Login tracking migration completed",
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )

@router.get("/test-login-tracking", response_model=dict)
async def test_login_tracking(current_user: User = Depends(get_current_user)):
    """
    Test endpoint to verify login tracking is working for the current user.
    """
    # Get the user from database to see current login tracking data
    user_doc = await db["users"].find_one({"_id": ObjectId(current_user.id)})
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_email": user_doc.get("email"),
        "has_login_tracking_fields": {
            "last_login": "last_login" in user_doc,
            "login_history": "login_history" in user_doc,
            "login_count": "login_count" in user_doc
        },
        "login_data": {
            "last_login": user_doc.get("last_login"),
            "login_count": user_doc.get("login_count", 0),
            "login_history_length": len(user_doc.get("login_history", [])),
            "recent_logins": user_doc.get("login_history", [])[-3:] if user_doc.get("login_history") else []
        }
    }
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from minerva.core.models.organization import Organization
from minerva.core.models.user import User, UserRole
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.database.database import client

# Initialize the API router with a prefix and tags
router = APIRouter()
db = client.Main  # Reference to the database

# Endpoint to create a new organization
@router.post("/", response_model=Organization)
async def create_organization(organization: Organization):
    # Insert the organization into the database
    result = await db["organizations"].insert_one(organization.dict(by_alias=True))
    # Return the created organization
    return Organization.parse_obj(organization.dict(by_alias=True, exclude_unset=True))

# Endpoint to get all members of the current user's organization
@router.get("/members", status_code=200)
async def get_organization_members(current_user: User = Depends(get_current_user)):
    """
    Get all members in the current user's organization.
    """
    if not current_user.org_id:
        # Raise an error if the user is not part of an organization
        raise HTTPException(status_code=404, detail="No organization found.")

    # Retrieve members of the organization from the database
    members_cursor = db["users"].find({"org_id": current_user.org_id})
    members_list = await members_cursor.to_list(length=100)

    # Format the members' data
    members = []
    for member in members_list:
        members.append({
            "id": str(member["_id"]),
            "name": member.get("name", ""),
            "email": member["email"],
            "role": member.get("role", "member"),
            "isCurrentUser": str(member["_id"]) == str(current_user.id)
        })

    # Return the list of members
    return {"members": members}

# Endpoint to check if the current user or any member of their organization has an enterprise plan
@router.get("/has-enterprise", response_model=bool)
async def check_enterprise_status(current_user: User = Depends(get_current_user)):
    """
    Returns True if the current user has an enterprise plan or if any member 
    of their organization has an enterprise plan.
    """
    # Check if the current user has an enterprise plan.
    if current_user.subscription and current_user.subscription.plan_type == "enterprise":
        return True

    # If the current user belongs to an organization, check if any member has enterprise.
    if current_user.org_id:
        user_with_enterprise = await db["users"].find_one({
            "org_id": current_user.org_id,
            "subscription.plan_type": "enterprise"
        })
        return bool(user_with_enterprise)
    
    return False

# Endpoint to retrieve an organization by its ID
@router.get("/{organization_id}", response_model=Organization)
async def get_organization(organization_id: str):
    # Find the organization in the database
    organization = await db["organizations"].find_one({"_id": ObjectId(organization_id)})
    if organization is None:
        # Raise an error if the organization is not found
        raise HTTPException(status_code=404, detail="Organization not found")
    # Return the organization
    return Organization(**organization)

# Endpoint to update an organization's details
@router.put("/{organization_id}", response_model=Organization)
async def update_organization(organization_id: str, organization: Organization):
    # Update the organization in the database
    result = await db["organizations"].update_one(
        {"_id": ObjectId(organization_id)}, 
        {"$set": organization.dict(by_alias=True)}
    )
    if result.matched_count == 0:
        # Raise an error if the organization is not found
        raise HTTPException(status_code=404, detail="Organization not found")
    # Return the updated organization
    return organization

# Endpoint to delete an organization by its ID
@router.delete("/{organization_id}")
async def delete_organization(organization_id: str):
    # Delete the organization from the database
    result = await db["organizations"].delete_one({"_id": ObjectId(organization_id)})
    if result.deleted_count == 0:
        # Raise an error if the organization is not found
        raise HTTPException(status_code=404, detail="Organization not found")
    # Return a success message
    return {"message": "Organization deleted"}

# Endpoint to retrieve all organizations
@router.get("/", response_model=List[Organization])
async def get_all_organizations():
    # Retrieve all organizations from the database
    organizations = await db["organizations"].find().to_list(length=None)
    # Return the list of organizations
    return [Organization(**organization) for organization in organizations]

# Endpoint to allow a user to leave their current organization
@router.delete("/members/leave", status_code=200)
async def leave_organization(current_user: User = Depends(get_current_user)):
    """
    Leave the current organization.
    This endpoint sets the user's "org_id" to an empty string.
    Prevents an admin from leaving if they are the only admin.
    """
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="You are not a member of any organization.")
    
    # Prevent the only admin from leaving the organization.
    if current_user.role == "admin":
        admin_count = await db["users"].count_documents({
            "org_id": current_user.org_id,
            "role": "admin"
        })
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="You cannot leave the organization as you are the only admin.")
    
    # Update the user document in the database, setting org_id to an empty string.
    result = await db["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"org_id": ""}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to leave the organization.")
    
    return {"message": "You have successfully left the organization."}

# Endpoint to update a team member's role
@router.patch("/members/{member_id}/role", status_code=200)
async def update_member_role(
    member_id: str, 
    role_update: dict, 
    current_user: User = Depends(get_current_user)
):
    """
    Update a team member's role.
    Only admins can perform this action.
    """
    if current_user.role != "admin":
        # Raise an error if the current user is not an admin
        raise HTTPException(status_code=403, detail="Only administrators can update roles.")

    # Validate the new role
    new_role = role_update.get("role")
    if new_role not in [UserRole.ADMIN, UserRole.MEMBER, UserRole.GUEST]:
        raise HTTPException(status_code=400, detail="Invalid role specified.")

    # Find the member in the database
    member = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not member:
        # Raise an error if the member is not found
        raise HTTPException(status_code=404, detail="Member not found.")
    if member.get("org_id") != current_user.org_id:
        # Raise an error if the member belongs to a different organization
        raise HTTPException(status_code=403, detail="Cannot update role for a user from a different organization.")

    # Update the member's role in the database
    await db["users"].update_one({"_id": ObjectId(member_id)}, {"$set": {"role": new_role}})
    # Return a success message
    return {"message": "Member role updated successfully."}

# Endpoint to remove a member from the organization
@router.delete("/members/{member_id}", status_code=200)
async def remove_member(member_id: str, current_user: User = Depends(get_current_user)):
    """
    Remove a member from the organization.
    Only admins can perform this action.
    """
    if current_user.role != "admin":
        # Raise an error if the current user is not an admin
        raise HTTPException(status_code=403, detail="Only administrators can remove members.")

    # Find the member in the database
    member = await db["users"].find_one({"_id": ObjectId(member_id)})
    if not member:
        # Raise an error if the member is not found
        raise HTTPException(status_code=404, detail="Member not found.")
    if member.get("org_id") != current_user.org_id:
        # Raise an error if the member belongs to a different organization
        raise HTTPException(status_code=403, detail="Cannot remove a user from a different organization.")
    if str(current_user.id) == str(member["_id"]):
        # Raise an error if the user tries to remove themselves
        raise HTTPException(status_code=400, detail="You cannot remove yourself.")

    # Remove the member from the database
    await db["users"].update_one({"_id": ObjectId(member_id)}, {"$set": {"org_id": ""}})
    # Return a success message
    return {"message": "Member removed successfully."}
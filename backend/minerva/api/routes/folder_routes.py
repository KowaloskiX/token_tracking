from typing import List
from fastapi import APIRouter, HTTPException, Query
from minerva.core.models.folder import Folder
from bson import ObjectId
from minerva.core.database.database import db

router = APIRouter()

@router.post("/", response_model=Folder)
async def create_folder(folder: Folder):
    result = await db["folders"].insert_one(folder.dict(by_alias=True))
    
    # If it's a subfolder, update parent folder's subfolders list
    if folder.parent_folder_id:
        await db["folders"].update_one(
            {"_id": ObjectId(folder.parent_folder_id)},
            {"$push": {"subfolders": str(result.inserted_id)}}
        )
    
    return Folder.parse_obj(folder.dict(by_alias=True))

@router.get("/assistant/{assistant_id}", response_model=List[Folder])
async def get_assistant_folders(
    assistant_id: str,
    owner_id: str = Query(..., description="Owner ID to ensure proper access")
):
    """Get all folders for a specific assistant owned by the user"""
    folders = await db["folders"].find({
        "assistant_id": assistant_id,
        "owner_id": owner_id
    }).to_list(length=None)
    return [Folder(**folder) for folder in folders]

@router.get("/assistant/{assistant_id}/root", response_model=List[Folder])
async def get_assistant_root_folders(
    assistant_id: str,
    owner_id: str = Query(..., description="Owner ID to ensure proper access")
):
    """Get root folders for a specific assistant owned by the user"""
    folders = await db["folders"].find({
        "assistant_id": assistant_id,
        "owner_id": owner_id,
        "parent_folder_id": None
    }).to_list(length=None)
    return [Folder(**folder) for folder in folders]

@router.get("/{folder_id}", response_model=Folder)
async def get_folder(folder_id: str):
    folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return Folder(**folder)

@router.put("/{folder_id}", response_model=Folder)
async def update_folder(folder_id: str, folder_update: dict):
    result = await db["folders"].update_one(
        {"_id": ObjectId(folder_id)},
        {"$set": folder_update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Folder not found")
    updated_folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
    return Folder(**updated_folder)

@router.delete("/{folder_id}")
async def delete_folder(folder_id: str):
    # Get the folder to check if it's a subfolder
    folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Recursively delete all subfolders and their contents
    async def delete_folder_recursive(folder_id: str):
        folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
        if folder:
            # Delete all files in the folder
            for file_id in folder["files"]:
                await db["files"].delete_one({"_id": ObjectId(file_id)})
            
            # Recursively delete subfolders
            for subfolder_id in folder["subfolders"]:
                await delete_folder_recursive(subfolder_id)
            
            # Delete the folder itself
            await db["folders"].delete_one({"_id": ObjectId(folder_id)})
    
    # If it's a subfolder, remove it from parent's subfolders list
    if folder.get("parent_folder_id"):
        await db["folders"].update_one(
            {"_id": ObjectId(folder["parent_folder_id"])},
            {"$pull": {"subfolders": folder_id}}
        )
    
    # Delete the folder and all its contents
    await delete_folder_recursive(folder_id)
    return {"message": "Folder and all contents deleted"}

@router.get("/", response_model=List[Folder])
async def get_all_folders(
    owner_id: str = Query(None, description="Filter folders by owner"),
    assistant_id: str = Query(None, description="Filter folders by assistant")
):
    """Get all folders with optional filtering by owner and assistant"""
    query = {}
    if owner_id:
        query["owner_id"] = owner_id
    if assistant_id:
        query["assistant_id"] = assistant_id
        
    folders = await db["folders"].find(query).to_list(length=None)
    return [Folder(**folder) for folder in folders]

@router.get("/{folder_id}/subfolders", response_model=List[Folder])
async def get_subfolders(folder_id: str):
    subfolders = await db["folders"].find({"parent_folder_id": folder_id}).to_list(length=None)
    return [Folder(**folder) for folder in subfolders]


@router.post("/create-default", response_model=Folder)
async def create_default_folder(owner_id: str, assistant_id: str):
    """Create a default 'Home' folder if it doesn't exist"""
    # Check if default folder already exists
    existing_folder = await db["folders"].find_one({
        "owner_id": owner_id,
        "assistant_id": assistant_id,
        "name": "Home",
        "parent_folder_id": None
    })
    
    if existing_folder:
        return Folder(**existing_folder)
    
    # Create new default folder
    default_folder = Folder(
        name="Home",
        description="Default home folder",
        owner_id=owner_id,
        assistant_id=assistant_id,
        parent_folder_id=None,
        files=[],
        subfolders=[]
    )
    
    result = await db["folders"].insert_one(default_folder.dict(by_alias=True))
    created_folder = await db["folders"].find_one({"_id": result.inserted_id})
    return Folder(**created_folder)

@router.get("/get-default/{assistant_id}/{owner_id}", response_model=Folder)
async def get_default_folder(assistant_id: str, owner_id: str):
    """Get the default 'Home' folder for a user and assistant"""
    folder = await db["folders"].find_one({
        "owner_id": owner_id,
        "assistant_id": assistant_id,
        "name": "Home",
        "parent_folder_id": None
    })
    
    if folder is None:
        # Create default folder if it doesn't exist
        folder = await create_default_folder(owner_id, assistant_id)
        return folder
        
    return Folder(**folder)


@router.patch("/{folder_id}/rename", response_model=Folder)
async def rename_folder(folder_id: str, new_name: str):
    """Rename a folder"""
    folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Check if a folder with the same name exists at the same level
    existing_folder = await db["folders"].find_one({
        "parent_folder_id": folder["parent_folder_id"],
        "name": new_name,
        "_id": {"$ne": ObjectId(folder_id)}  # Exclude current folder
    })
    
    if existing_folder:
        raise HTTPException(
            status_code=400, 
            detail="A folder with this name already exists in this location"
        )
    
    # Update folder name
    result = await db["folders"].update_one(
        {"_id": ObjectId(folder_id)},
        {"$set": {"name": new_name}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Folder rename failed")
        
    updated_folder = await db["folders"].find_one({"_id": ObjectId(folder_id)})
    return Folder(**updated_folder)

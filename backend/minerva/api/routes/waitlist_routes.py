from typing import List
from minerva.core.models.waitlist import WaitlistEntry
from fastapi import APIRouter, HTTPException
from minerva.core.database.database import db

router = APIRouter()

async def add_to_waitlist(entry: WaitlistEntry) -> bool:
    # Check if email already exists
    existing_entry = await db["waitlist"].find_one({"email": entry.email})
    if existing_entry:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Insert new entry
    result = await db["waitlist"].insert_one(entry.model_dump())
    return bool(result.inserted_id)

async def get_waitlist_count() -> int:
    return await db["waitlist"].count_documents({})


@router.post("/")
async def create_waitlist_entry(entry: WaitlistEntry):
    try:
        success = await add_to_waitlist(entry)
        if success:
            return {"status": "success", "message": "Successfully added to waitlist"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/count")
async def get_count():
    count = await get_waitlist_count()
    return {"count": count + 141}


async def get_all_waitlist_emails() -> List[str]:
    cursor = db["waitlist"].find({}, {"email": 1, "_id": 0})
    emails = [doc["email"] async for doc in cursor]
    return emails


@router.get("/emails", response_model=List[str])
async def list_emails():
    try:
        emails = await get_all_waitlist_emails()
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
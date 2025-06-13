from datetime import datetime
from typing import List
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from fastapi import APIRouter, HTTPException, Depends, status
from bson import ObjectId

from minerva.core.models.kanban_board import (
    KanbanBoardModel,
    KanbanBoardModelUpdate,
    KanbanBoardTenderItemModel,
    KanbanBoardTenderItemModelUpdate,
    KanbanColumnModel,
    KanbanColumnModelUpdate,
    MoveTenderRequest
)
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.database.database import db
from minerva.core.models.user import User

router = APIRouter()

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

async def reorder_columns(board_id: str) -> None:
    board = await db["kanban_boards"].find_one({"_id": ObjectId(board_id)})
    if not board:
        return

    columns = board.get("columns", [])
    columns.sort(key=lambda col: col.get("order", 0))
    
    for idx, col in enumerate(columns):
        col["order"] = idx + 1

    await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id)},
        {"$set": {"columns": columns, "updated_at": datetime.now()}}
    )

async def reorder_tenders(board_id: str, column_id: str) -> None:
    # Fetch latest board state
    board = await db["kanban_boards"].find_one({"_id": ObjectId(board_id)})
    if not board:
        return

    # Find the target column
    column = next(
        (col for col in board["columns"] if str(col["_id"]) == column_id),
        None
    )
    if not column:
        return

    # Get and sort tenders by current order
    tenders = column.get("tender_items", [])
    tenders.sort(key=lambda x: x.get("order", 0))

    # Renumber orders sequentially starting at 1
    for index, tender in enumerate(tenders):
        tender["order"] = index + 1

    # Update the database with new order values
    await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id), "columns._id": ObjectId(column_id)},
        {"$set": {
            "columns.$.tender_items": tenders,
            "updated_at": datetime.now()
        }}
    )

# -----------------------------------------------------------------------------
# BOARDS (GET, POST, PUT, DELETE)
# -----------------------------------------------------------------------------

@router.get("/boards/{board_id}", response_model=KanbanBoardModel)
async def get_single_board(
    board_id: str,
    current_user: User = Depends(get_current_user)
):
    if not ObjectId.is_valid(board_id):
        raise HTTPException(status_code=400, detail="Invalid board ID.")

    # Only user-based principals now
    principals = [
        {"user_id": str(current_user.id)},
        {"assigned_users": str(current_user.id)}
    ]

    query = {
        "_id": ObjectId(board_id),
        "$or": principals
    }

    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(
            status_code=404,
            detail="Board not found or not accessible by user."
        )

    return KanbanBoardModel.parse_obj(board)


# ── GET /boards ───────────────────────────────────────────────────────────────
@router.get("/boards", response_model=List[KanbanBoardModel])
async def get_boards(current_user: User = Depends(get_current_user)):
    principals = [
        {"user_id": str(current_user.id)},
        {"assigned_users": str(current_user.id)}
    ]

    query = {"$or": principals}

    cursor = db["kanban_boards"].find(query)
    boards = [doc async for doc in cursor]
    return [KanbanBoardModel.parse_obj(b) for b in boards]


@router.post("/boards", response_model=KanbanBoardModel, status_code=status.HTTP_201_CREATED)
async def create_board(
    board_data: KanbanBoardModel,
    current_user: User = Depends(get_current_user),
):
    board_dict = board_data.dict(by_alias=True, exclude_unset=True)
    board_dict.pop("org_id", None)
    board_dict["user_id"] = str(current_user.id)
    board_dict["created_at"] = datetime.now()
    board_dict["updated_at"] = datetime.now()

    result = await db["kanban_boards"].insert_one(board_dict)
    inserted = await db["kanban_boards"].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=400, detail="Failed to create board.")

    return KanbanBoardModel.parse_obj(inserted)

@router.put("/boards/{board_id}", response_model=KanbanBoardModel)
async def update_board(
    board_id: str,
    board_data: KanbanBoardModelUpdate,
    current_user: User = Depends(get_current_user)
):
    # ── 1.  Basic validation & access check ──────────────────────────────────────
    if not ObjectId.is_valid(board_id):
        raise HTTPException(status_code=400, detail="Invalid board ID.")

    principals = [
        {"user_id": str(current_user.id)},
        {"assigned_users": str(current_user.id)},
    ]
    if current_user.org_id and current_user.org_id.strip():
        principals.append({"org_id": current_user.org_id})

    query = {"_id": ObjectId(board_id), "$or": principals}

    existing = await db["kanban_boards"].find_one(query)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Board not found or not accessible by user.",
        )

    # ── 2.  Build the update payload ────────────────────────────────────────────
    base_set: dict = board_data.dict(by_alias=True, exclude_unset=True)
    base_set["updated_at"] = datetime.now()

    # New rule: conditionally add / remove org_id based on assigned_users
    unset_ops: dict = {}  # keep it empty unless we have something to unset

    if "assigned_users" in base_set:  # means the caller tried to change the list
        assigned = base_set["assigned_users"]

        # If the list is empty → remove org_id
        if isinstance(assigned, list) and len(assigned) == 0:
            unset_ops["org_id"] = ""  # empty string is fine for $unset

        # If the list has elements → (re-)attach org_id (if user has one)
        elif isinstance(assigned, list) and len(assigned) > 0:
            if current_user.org_id and current_user.org_id.strip():
                base_set["org_id"] = current_user.org_id

    # Assemble the update document that MongoDB expects
    update_ops: dict = {"$set": base_set}
    if unset_ops:  # only include $unset when needed
        update_ops["$unset"] = unset_ops

    # ── 3.  Persist the update & post-processing ────────────────────────────────
    result = await db["kanban_boards"].find_one_and_update(
        query,
        update_ops,
        return_document=True,  # returns the updated document
    )
    if not result:
        raise HTTPException(status_code=400, detail="Unable to update board.")

    # Keep your extra housekeeping logic
    await reorder_columns(board_id)

    return KanbanBoardModel.parse_obj(result)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: str,
    current_user: User = Depends(get_current_user)
):
    if not ObjectId.is_valid(board_id):
        raise HTTPException(status_code=400, detail="Invalid board ID.")
    
    principals = [
        {"user_id": str(current_user.id)},
        {"assigned_users": str(current_user.id)}
    ]
    if current_user.org_id and current_user.org_id.strip():
        principals.append({"org_id": current_user.org_id})

    query = {
        "_id": ObjectId(board_id),
        "$or": principals
    }

    delete_result = await db["kanban_boards"].delete_one(query)
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Board not found or not accessible by user.")
    return None


# -----------------------------------------------------------------------------
# COLUMNS (GET, POST, PUT, DELETE)
# Embedded in "columns" array of the board doc
# -----------------------------------------------------------------------------

@router.get("/boards/{board_id}/columns", response_model=List[KanbanColumnModel])
async def get_columns(
    board_id: str,
    current_user: User = Depends(get_current_user)
):
    if not ObjectId.is_valid(board_id):
        raise HTTPException(status_code=400, detail="Invalid board ID.")
    
    # Use org-based access similar to the get_single_board endpoint.
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        query = {"_id": ObjectId(board_id), "user_id": str(current_user.id)}

    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found or not accessible by user.")

    columns = board.get("columns", [])

    return [KanbanColumnModel.parse_obj(c) for c in columns]

@router.post("/boards/{board_id}/columns", response_model=KanbanColumnModel)
async def create_column(
    board_id: str,
    column_data: KanbanColumnModel,
    current_user: User = Depends(get_current_user)
):
    if not ObjectId.is_valid(board_id):
        raise HTTPException(status_code=400, detail="Invalid board ID.")

    # Use org-based query for lookup: allow if:
    # - current user is owner OR board belongs to current_user's org
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        query = {"_id": ObjectId(board_id), "user_id": str(current_user.id)}

    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(
            status_code=404,
            detail="Board not found or not accessible by user."
        )

    col_dict = column_data.dict(by_alias=True, exclude_unset=True)
    if not col_dict.get("_id"):
        col_dict["_id"] = ObjectId()

    orders = [col.get("order", 0) for col in board.get("columns", [])]
    max_order = max(orders) if orders else 0
    col_dict["order"] = max_order + 1

    updated_board = await db["kanban_boards"].find_one_and_update(
        {"_id": ObjectId(board_id)},
        {
            "$push": {"columns": col_dict},
            "$set": {"updated_at": datetime.now()}
        },
        return_document=True
    )
    if not updated_board:
        raise HTTPException(status_code=400, detail="Failed to add column.")

    new_col_id = col_dict["_id"]
    for col in updated_board["columns"]:
        if col["_id"] == new_col_id:
            return KanbanColumnModel.parse_obj(col)

    raise HTTPException(status_code=500, detail="Newly added column not found in updated board.")

@router.put("/boards/{board_id}/columns/{column_id}", response_model=KanbanColumnModel)
async def update_column(
    board_id: str,
    column_id: str,
    column_data: KanbanColumnModelUpdate,
    current_user: User = Depends(get_current_user)
):
    if not (ObjectId.is_valid(board_id) and ObjectId.is_valid(column_id)):
        raise HTTPException(status_code=400, detail="Invalid IDs.")

    # Use org-based query for the parent board as well
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        query = {"_id": ObjectId(board_id), "user_id": str(current_user.id)}

    # Ensure that the board exists
    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found or not accessible by user.")

    update_dict = column_data.dict(by_alias=True, exclude_unset=True)
    update_fields = {}
    for k, v in update_dict.items():
        if k == "_id":
            continue
        if k == "tender_items":
            new_tenders = []
            for tender in v:
                if not ObjectId.is_valid(tender['_id']):
                    raise HTTPException(status_code=400, detail="Invalid tender ID format.")
                new_tender = {
                    "_id": ObjectId(tender['_id']),
                    "order": tender['order'],
                    "tender_analysis_result_id": ObjectId(tender['tender_analysis_result_id']) if tender.get('tender_analysis_result_id') else None,
                    "board_id": ObjectId(tender['board_id']),
                    "column_id": ObjectId(tender['column_id']),
                }
                new_tenders.append(new_tender)
            update_fields["columns.$.tender_items"] = new_tenders
        else:
            update_fields[f"columns.$.{k}"] = v
    update_fields["updated_at"] = datetime.now()

    updated_board = await db["kanban_boards"].find_one_and_update(
        {**query, "columns._id": ObjectId(column_id)},
        {"$set": update_fields},
        return_document=True
    )
    if not updated_board:
        raise HTTPException(status_code=404, detail="Board or column not found.")

    for col in updated_board["columns"]:
        if col["_id"] == ObjectId(column_id):
            return KanbanColumnModel.parse_obj(col)

    raise HTTPException(status_code=500, detail="Updated column not found in board.")

@router.delete("/boards/{board_id}/columns/{column_id}", response_model=KanbanColumnModel)
async def delete_column(
    board_id: str,
    column_id: str,
    current_user: User = Depends(get_current_user)
):
    if not (ObjectId.is_valid(board_id) and ObjectId.is_valid(column_id)):
        raise HTTPException(status_code=400, detail="Invalid IDs.")

    # Use org-based query for board lookup
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        query = {"_id": ObjectId(board_id), "user_id": str(current_user.id)}

    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found or not accessible by user.")
    
    column_to_delete = None
    for col in board.get("columns", []):
        if col["_id"] == ObjectId(column_id):
            column_to_delete = col
            break
    
    if not column_to_delete:
        raise HTTPException(status_code=404, detail="Column not found in board.")
    
    updated_board = await db["kanban_boards"].find_one_and_update(
        {"_id": ObjectId(board_id)},
        {
            "$pull": {"columns": {"_id": ObjectId(column_id)}},
            "$set": {"updated_at": datetime.now()}
        },
        return_document=True
    )
    if not updated_board:
        raise HTTPException(status_code=404, detail="Column not found in board.")
    await reorder_columns(board_id)
    return KanbanColumnModel.parse_obj(column_to_delete)

# ----------------------------------------------------------------------------
# TENDERS (Items) referencing BOTH board_id and column_id
# /boards/{board_id}/columns/{column_id}/items
# ----------------------------------------------------------------------------

@router.get("/boards/{board_id}/columns/{column_id}/items", response_model=List[KanbanBoardTenderItemModel])
async def get_tenders(
    board_id: str,
    column_id: str,
    current_user: User = Depends(get_current_user)
):
    if not (ObjectId.is_valid(board_id) and ObjectId.is_valid(column_id)):
        raise HTTPException(status_code=400, detail="Invalid board or column ID.")

    # Use org-based logic here as well
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        query = {"_id": ObjectId(board_id), "user_id": str(current_user.id)}

    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found.")

    column = next(
        (col for col in board.get("columns", []) if str(col["_id"]) == column_id),
        None
    )
    
    if not column:
        raise HTTPException(status_code=404, detail="Column not found.")

    tender_items = column.get("tender_items", [])
    for item in tender_items:
        if isinstance(item.get("_id"), ObjectId):
            item["_id"] = str(item["_id"])
        if isinstance(item.get("board_id"), ObjectId):
            item["board_id"] = str(item["board_id"])
        if isinstance(item.get("column_id"), ObjectId):
            item["column_id"] = str(item["column_id"])

    return tender_items

@router.post("/boards/{board_id}/columns/{column_id}/items", 
             response_model=KanbanBoardTenderItemModel,
             status_code=status.HTTP_201_CREATED)
async def create_tender(
    board_id: str,
    column_id: str,
    item_data: KanbanBoardTenderItemModel,
    current_user: User = Depends(get_current_user)
):
    if not (ObjectId.is_valid(board_id) and ObjectId.is_valid(column_id)):
        raise HTTPException(status_code=400, detail="Invalid board or column ID.")

    # Use org-based query for board lookup: allow if user is owner or board belongs to user's org
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ],
            "columns._id": ObjectId(column_id)
        }
    else:
        query = {
            "_id": ObjectId(board_id),
            "user_id": str(current_user.id),
            "columns._id": ObjectId(column_id)
        }
    
    board = await db["kanban_boards"].find_one(query)
    if not board:
        raise HTTPException(status_code=404, detail="Board or column not found or not accessible by user.")

    # Ensure that the board_id and column_id in item_data match the URL parameters
    if str(item_data.board_id) != board_id or str(item_data.column_id) != column_id:
        raise HTTPException(
            status_code=400,
            detail="Board/column ID in path and item_data do not match."
        )

    # Get the target column from the board document
    column = next(col for col in board["columns"] if str(col["_id"]) == column_id)
    existing_tenders = column.get("tender_items", [])
    
    # Determine new order for the tender item
    new_order = max([t.get("order", 0) for t in existing_tenders], default=0) + 1

    tender_item = item_data.dict(by_alias=True, exclude_unset=True)
    tender_item["order"] = new_order
    tender_item["_id"] = ObjectId()
    tender_item["created_at"] = datetime.now()
    tender_item["updated_at"] = datetime.now()

    # Push the new tender item into the appropriate column
    update_result = await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id), "columns._id": ObjectId(column_id)},
        {"$push": {"columns.$.tender_items": tender_item}}
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to add tender item to column.")

    return KanbanBoardTenderItemModel.parse_obj(tender_item)

@router.put("/boards/{board_id}/columns/{column_id}/items/{tender_id}", response_model=KanbanBoardTenderItemModel)
async def update_tender(
    board_id: str,
    column_id: str,
    tender_id: str,
    update_data: KanbanBoardTenderItemModelUpdate,
    current_user: User = Depends(get_current_user)
):
    if not all(ObjectId.is_valid(x) for x in [board_id, column_id, tender_id]):
        raise HTTPException(status_code=400, detail="Invalid ID format.")

    update_data_dict = update_data.dict(exclude_unset=True, by_alias=True)
    update_data_dict["_id"] = ObjectId(tender_id)

    # Build query to allow access by owner or by org member
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ],
            "columns._id": ObjectId(column_id)
        }
    else:
        query = {
            "_id": ObjectId(board_id),
            "user_id": str(current_user.id),
            "columns._id": ObjectId(column_id)
        }

    update_result = await db["kanban_boards"].update_one(
        query,
        {"$set": {"columns.$[col].tender_items.$[item]": update_data_dict}},
        array_filters=[{"col._id": ObjectId(column_id)}, {"item._id": ObjectId(tender_id)}]
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Tender not found or update failed.")

    return update_data

@router.delete("/boards/{board_id}/columns/{column_id}/items/{tender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tender(
    board_id: str,
    column_id: str,
    tender_id: str,
    current_user: User = Depends(get_current_user)
):
    if not all(ObjectId.is_valid(x) for x in [board_id, column_id, tender_id]):
        raise HTTPException(status_code=400, detail="Invalid ID format.")
    
    # Build query to allow access by owner or by org member
    if current_user.org_id and current_user.org_id.strip() != "":
        query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ],
            "columns._id": ObjectId(column_id)
        }
    else:
        query = {
            "_id": ObjectId(board_id),
            "user_id": str(current_user.id),
            "columns._id": ObjectId(column_id)
        }
    
    update_result = await db["kanban_boards"].update_one(
        query,
        {"$pull": {"columns.$.tender_items": {"_id": ObjectId(tender_id)}}}
    )
    
    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Tender not found or already deleted.")
    
    await reorder_tenders(board_id, column_id)
    return None

@router.put("/boards/{board_id}/tenders/{tender_id}/move", response_model=KanbanBoardTenderItemModel)
async def move_tender(
    board_id: str,
    tender_id: str,
    move_data: MoveTenderRequest,
    current_user: User = Depends(get_current_user)
):
    # Validate IDs
    if not all(ObjectId.is_valid(id) for id in [board_id, tender_id, move_data.source_column_id, move_data.target_column_id]):
        raise HTTPException(status_code=400, detail="Invalid ID format.")

    # Check user access to the board
    if current_user.org_id and current_user.org_id.strip() != "":
        board_query = {
            "_id": ObjectId(board_id),
            "$or": [
                {"user_id": str(current_user.id)},
                {"org_id": current_user.org_id}
            ]
        }
    else:
        # Fixed query - don't use $or if there's no org_id
        board_query = {
            "_id": ObjectId(board_id),
            "user_id": str(current_user.id)
        }
    
    board = await db["kanban_boards"].find_one(board_query)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found or access denied.")

    # Find source and target columns
    source_column = next((col for col in board["columns"] if str(col["_id"]) == str(move_data.source_column_id)), None)
    target_column = next((col for col in board["columns"] if str(col["_id"]) == str(move_data.target_column_id)), None)
    if not source_column or not target_column:
        raise HTTPException(status_code=404, detail="Source or target column not found.")

    # Find tender in source column
    tender = next((t for t in source_column.get("tender_items", []) if str(t["_id"]) == tender_id), None)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found in source column.")
    
    # Make a copy of the tender to return later if needed
    tender_copy = dict(tender)

    # Remove from source
    await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id), "columns._id": ObjectId(move_data.source_column_id)},
        {"$pull": {"columns.$.tender_items": {"_id": ObjectId(tender_id)}}}
    )

    # Add to target and update column_id
    tender["column_id"] = ObjectId(move_data.target_column_id)
    tender["order"] = 0  # Temporarily set to 0

    await db["kanban_boards"].update_one(
        {"_id": ObjectId(board_id), "columns._id": ObjectId(move_data.target_column_id)},
        {"$push": {"columns.$.tender_items": tender}}
    )

    # Reorder both columns
    await reorder_tenders(board_id, str(move_data.source_column_id))
    await reorder_tenders(board_id, str(move_data.target_column_id))

    # Fetch updated tender - with error handling
    try:
        updated_board = await db["kanban_boards"].find_one({"_id": ObjectId(board_id)})
        updated_target_col = next(col for col in updated_board["columns"] if str(col["_id"]) == str(move_data.target_column_id))
        
        # Try to find the moved tender in the target column
        try:
            moved_tender = next(t for t in updated_target_col.get("tender_items", []) if str(t["_id"]) == tender_id)
        except StopIteration:
            # The tender might not be found due to race conditions or timing issues
            # In this case, return the original tender with updated column_id and order
            tender_copy["column_id"] = str(move_data.target_column_id)
            # Get max order of existing items in target column
            existing_orders = [t.get("order", 0) for t in updated_target_col.get("tender_items", [])]
            tender_copy["order"] = max(existing_orders, default=0) + 1
            return KanbanBoardTenderItemModel.parse_obj(tender_copy)
        
        return KanbanBoardTenderItemModel.parse_obj(moved_tender)
    except Exception as e:
        # In case of any other error, return the original tender with updated fields
        tender_copy["column_id"] = str(move_data.target_column_id)
        return KanbanBoardTenderItemModel.parse_obj(tender_copy)

@router.post("/tender-results/batch", response_model=List[TenderAnalysisResult])
async def get_tender_results_batch(
    tender_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    if not all(ObjectId.is_valid(id) for id in tender_ids):
        raise HTTPException(status_code=400, detail="Invalid tender ID format.")

    
    query = {
        "_id": {"$in": [ObjectId(id) for id in tender_ids]}
    }
    
    cursor = db["tender_analysis_results"].find(query)
    raw_results = await cursor.to_list(length=None)  # Fetch all results explicitly
    
    results = []
    for doc in raw_results:
        try:
            result = TenderAnalysisResult.parse_obj(doc)
            results.append(result)
        except Exception as e:
            print(f"Failed to parse document {doc['_id']}: {e}")
    
    if not results:
        raise HTTPException(status_code=404, detail="No tenders found.")
    
    return results
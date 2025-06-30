from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, logger
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.models.columns import (
    ColumnConfiguration, 
    ColumnConfigurationRequest, 
    ColumnConfigurationUpdate, 
    ColumnConfigurationResponse
)
from minerva.core.models.user import User
from minerva.core.models.utils import PyObjectId
from minerva.core.database.database import db

router = APIRouter()

@router.get("/tender-analysis/{analysis_id}/column-config", response_model=ColumnConfigurationResponse)
async def get_column_configuration(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Get column configuration for a specific analysis and user"""
    try:
        # Check if analysis exists and user has access
        query = {
            "_id": analysis_id,
            "$or": [
                {"user_id": current_user.id},  # User is creator
                {"assigned_users": {"$in": [str(current_user.id)]}}  # User is assigned
            ]
        }
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Find column configurations for this user and analysis
        column_configs = await db.column_configurations.find({
            "user_id": current_user.id,
            "analysis_id": analysis_id
        }).sort("order", 1).to_list(None)
        
        # Convert to response format
        configs = [ColumnConfiguration(**config) for config in column_configs]
        
        return ColumnConfigurationResponse(
            columns=configs,
            total_count=len(configs)
        )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting column configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting column configuration: {str(e)}"
        )

@router.post("/tender-analysis/{analysis_id}/column-config", response_model=ColumnConfigurationResponse)
async def save_column_configuration(
    analysis_id: PyObjectId,
    config_data: ColumnConfigurationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Save or update column configuration for a specific analysis and user"""
    try:
        # Check if analysis exists and user has access
        query = {
            "_id": analysis_id,
            "$or": [
                {"user_id": current_user.id},  # User is creator
                {"assigned_users": {"$in": [str(current_user.id)]}}  # User is assigned
            ]
        }
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Delete existing configurations for this user and analysis
        await db.column_configurations.delete_many({
            "user_id": current_user.id,
            "analysis_id": analysis_id
        })
        
        # Insert new configurations
        new_configs = []
        for column_data in config_data.columns:
            config = ColumnConfiguration(
                user_id=current_user.id,
                analysis_id=analysis_id,
                column_id=column_data.column_id,
                column_type=column_data.column_type,
                column_key=column_data.column_key,
                label=column_data.label,
                width=column_data.width,
                visible=column_data.visible,
                order=column_data.order,
                criteria_id=column_data.criteria_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            new_configs.append(config.dict(by_alias=True))
        
        if new_configs:
            await db.column_configurations.insert_many(new_configs)
        
        # Fetch and return the saved configurations
        saved_configs = await db.column_configurations.find({
            "user_id": current_user.id,
            "analysis_id": analysis_id
        }).sort("order", 1).to_list(None)
        
        configs = [ColumnConfiguration(**config) for config in saved_configs]
        
        logger.info(f"Saved {len(configs)} column configurations for user {current_user.id}, analysis {analysis_id}")
        
        return ColumnConfigurationResponse(
            columns=configs,
            total_count=len(configs)
        )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error saving column configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error saving column configuration: {str(e)}"
        )

@router.delete("/tender-analysis/{analysis_id}/column-config", response_model=dict)
async def reset_column_configuration(
    analysis_id: PyObjectId,
    current_user: User = Depends(get_current_user)
):
    """Reset column configuration to defaults by deleting saved configuration"""
    try:
        # Check if analysis exists and user has access
        query = {
            "_id": analysis_id,
            "$or": [
                {"user_id": current_user.id},  # User is creator
                {"assigned_users": {"$in": [str(current_user.id)]}}  # User is assigned
            ]
        }
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Delete configurations for this user and analysis
        delete_result = await db.column_configurations.delete_many({
            "user_id": current_user.id,
            "analysis_id": analysis_id
        })
        
        logger.info(f"Reset column configuration for user {current_user.id}, analysis {analysis_id} - deleted {delete_result.deleted_count} configs")
        
        return {
            "message": "Column configuration reset to defaults",
            "deleted_count": delete_result.deleted_count
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error resetting column configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error resetting column configuration: {str(e)}"
        )

@router.get("/tender-analysis/{analysis_id}/columns/{column_id}", response_model=ColumnConfiguration)
async def get_single_column_configuration(
    analysis_id: PyObjectId,
    column_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific column configuration"""
    try:
        # Check if analysis exists and user has access
        query = {
            "_id": analysis_id,
            "$or": [
                {"user_id": current_user.id},
                {"assigned_users": {"$in": [str(current_user.id)]}}
            ]
        }
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Find the specific column configuration
        column_config = await db.column_configurations.find_one({
            "user_id": current_user.id,
            "analysis_id": analysis_id,
            "column_id": column_id
        })
        
        if not column_config:
            raise HTTPException(
                status_code=404,
                detail="Column configuration not found"
            )
        
        return ColumnConfiguration(**column_config)
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting single column configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting single column configuration: {str(e)}"
        )

@router.put("/tender-analysis/{analysis_id}/columns/{column_id}", response_model=ColumnConfiguration)
async def update_single_column_configuration(
    analysis_id: PyObjectId,
    column_id: str,
    column_data: ColumnConfigurationRequest,
    current_user: User = Depends(get_current_user)
):
    """Update a specific column configuration"""
    try:
        # Check if analysis exists and user has access
        query = {
            "_id": analysis_id,
            "$or": [
                {"user_id": current_user.id},
                {"assigned_users": {"$in": [str(current_user.id)]}}
            ]
        }
        
        analysis = await db.tender_analysis.find_one(query)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Tender analysis not found or you don't have access to it"
            )
        
        # Update the column configuration
        update_data = {
            "column_type": column_data.column_type,
            "column_key": column_data.column_key,
            "label": column_data.label,
            "width": column_data.width,
            "visible": column_data.visible,
            "order": column_data.order,
            "criteria_id": column_data.criteria_id,
            "updated_at": datetime.utcnow()
        }
        
        result = await db.column_configurations.find_one_and_update(
            {
                "user_id": current_user.id,
                "analysis_id": analysis_id,
                "column_id": column_id
            },
            {"$set": update_data},
            return_document=True,
            upsert=True  # Create if doesn't exist
        )
        
        if not result:
            # If upsert created a new document, we need to set the required fields
            config = ColumnConfiguration(
                user_id=current_user.id,
                analysis_id=analysis_id,
                column_id=column_id,
                **update_data
            )
            await db.column_configurations.insert_one(config.dict(by_alias=True))
            result = config.dict(by_alias=True)
        
        return ColumnConfiguration(**result)
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating single column configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating single column configuration: {str(e)}"
        )
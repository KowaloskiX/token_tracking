from datetime import datetime, date
from pprint import pprint
from typing import List, Dict, Optional, Tuple
from minerva.core.helpers.biznespolska_oferent_shared import is_same_tender
from pymongo.database import Database
from bson import ObjectId
from urllib.parse import urlparse
import logging
from minerva.core.database.database import db

logger = logging.getLogger(__name__)

class TenderExternalComparison:
    
    def convert_result_to_dict(self, result) -> Dict:
        """Convert TenderAnalysisResult to dictionary for comparison."""
        result_dict = result.dict() if hasattr(result, 'dict') else dict(result)
        # Ensure id is string for comparison
        if 'id' in result_dict and isinstance(result_dict['id'], ObjectId):
            result_dict['id'] = str(result_dict['id'])
        if '_id' in result_dict and isinstance(result_dict['_id'], ObjectId):
            result_dict['id'] = str(result_dict['_id'])
        return result_dict
    
    def calculate_tender_external_differences(
        self, 
        external_results: List[Dict], 
        internal_results: List[Dict]
    ) -> Dict:
        """
        Compare external and internal tender results.
        
        Args:
            external_results: Results with status 'external'
            internal_results: Results with other statuses
            
        Returns:
            Dictionary with unique and overlapping tenders
        """
        external_tenders = [self.convert_result_to_dict(t) for t in external_results]
        internal_tenders = [self.convert_result_to_dict(t) for t in internal_results]
        
        matched_external, matched_internal, overlaps = set(), set(), []
        
        # Find overlaps between external and internal results
        for i, t_ext in enumerate(external_tenders):
            external_url = t_ext.get("external_best_url", "")
            
            for j, t_int in enumerate(internal_tenders):
                if j in matched_internal:
                    continue
                
                internal_url = t_int.get("tender_url", "")
                
                a = {
                        "id": external_url,
                        "name": t_ext.get("tender_metadata", {}).get("name", ""),
                        "organization": t_ext.get("tender_metadata", {}).get("organization", "")
                    }
                b = {
                        "id": internal_url,
                        "name": t_int.get("tender_metadata", {}).get("name", ""),
                        "organization": t_int.get("tender_metadata", {}).get("organization", "")
                    }
                
                if internal_url == external_url:
                    overlap_record = {
                        "external_id": t_ext["id"],
                        "internal_id": t_int["id"],
                        "match_type": "id_match"
                    }
                    overlaps.append(overlap_record)
                    matched_external.add(i)
                    matched_internal.add(j)
                    break   
                elif is_same_tender(a, b):
                    overlap_record = {
                        "external_id": t_ext["id"],
                        "internal_id": t_int["id"],
                        "match_type": "url_match",
                        "external_url": external_url,
                        "internal_url": internal_url
                    }
                    overlaps.append(overlap_record)
                    matched_external.add(i)
                    matched_internal.add(j)
                    break
        
        # Get unique tenders
        unique_external = [t for i, t in enumerate(external_tenders) if i not in matched_external]
        unique_internal = [t for j, t in enumerate(internal_tenders) if j not in matched_internal]
        
        return {
            "unique_external": unique_external,
            "unique_internal": unique_internal,
            "total_unique_external": len(unique_external),
            "total_unique_internal": len(unique_internal),
            "overlaps": overlaps,
            "total_overlaps": len(overlaps)
        }
    
    async def update_external_compare_status(
        self, 
        analysis_id: str, 
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Main function to compare external and internal tender results and update statuses.
        
        Args:
            analysis_id: The analysis ID to process
            target_date: The date to filter results (as ISO string 'YYYY-MM-DD')
        
        Returns:
            Dictionary with comparison results and update statistics
        """
        try:
            # Convert analysis_id to ObjectId
            analysis_object_id = ObjectId(analysis_id)
            
            # First check if analysis exists and has include_external_sources enabled
            analysis = await db.tender_analysis.find_one({"_id": analysis_object_id})
            if not analysis:
                raise ValueError(f"Analysis with ID {analysis_id} not found")
            
            if not analysis.get("include_external_sources", False):
                raise ValueError("External sources are not enabled for this analysis")
            
            # Parse target_date string to date
            try:
                parsed_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                if parsed_date > parsed_end_date:
                    raise ValueError("start_date cannot be after end_date")
            except Exception:
                raise ValueError("target_date must be a string in 'YYYY-MM-DD' format")
            
            # Create date filter (using initiation_date in tender_metadata for date filtering)
            date_filter = {
                "tender_analysis_id": analysis_object_id,
                "tender_metadata.initiation_date": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
            print(f"Date filter: {date_filter}")
            # Query for external results
            external_results_cursor = db.tender_analysis_results.find({
                **date_filter,
                "status": "external"
            })
            external_results = await external_results_cursor.to_list(length=None)
            
            # Query for internal results (all statuses except external)
            internal_results_cursor = db.tender_analysis_results.find({
                **date_filter,
                "status": {"$ne": "external"}
            })
            internal_results = await internal_results_cursor.to_list(length=None)
            
            logger.info(f"Found {len(external_results)} external and {len(internal_results)} internal results")
            
            if not external_results and not internal_results:
                return {
                    "message": "No results found for the specified analysis and date",
                    "updated_count": 0
                }
            
            # Perform comparison
            comparison_result = self.calculate_tender_external_differences(
                external_results, internal_results
            )

            # Prepare lists for API response (id, tender_url, external_best_url)
            def extract_fields(t, is_external):
                return {
                    "id": str(t.get("_id") or t.get("id")),
                    "tender_url": t.get("tender_url", None),
                    "external_best_url": t.get("external_best_url", None) if is_external else None
                }

            unique_external = [extract_fields(t, True) for t in comparison_result["unique_external"]]
            unique_internal = [extract_fields(t, False) for t in comparison_result["unique_internal"]]
            overlaps = []
            for overlap in comparison_result["overlaps"]:
                # Find the full tender dicts for both external and internal
                ext = next((t for t in external_results if str(t.get("_id") or t.get("id")) == overlap["external_id"]), None)
                intl = next((t for t in internal_results if str(t.get("_id") or t.get("id")) == overlap["internal_id"]), None)
                overlaps.append({
                    "external": extract_fields(ext, True) if ext else None,
                    "internal": extract_fields(intl, False) if intl else None,
                    "match_type": overlap.get("match_type")
                })

            # Update external compare status for all results
            update_operations = []
            
            # Mark overlapping results
            overlapping_external_ids = set()
            overlapping_internal_ids = set()
            
            for overlap in comparison_result["overlaps"]:
                overlapping_external_ids.add(overlap["external_id"])
                overlapping_internal_ids.add(overlap["internal_id"])
            
            # Update external results
            for result in external_results:
                result_id = str(result["_id"])
                if result_id in overlapping_external_ids:
                    # Determine which external source
                    url = result.get("tender_url") or result.get("external_best_url") or ""
                    if "oferent" in url:
                        status = "overlap_oferent"
                    elif "biznes-polska" in url:
                        status = "overlap_bizpol"
                    else:
                        status = "overlap"
                else:
                    status = "external_unique"
                update_operations.append({
                    "filter": {"_id": result["_id"]},
                    "update": {
                        "$set": {
                            "external_compare_status": status,
                            "updated_at": datetime.utcnow()
                        }
                    }
                })
            # Update internal results
            for result in internal_results:
                result_id = str(result["_id"])
                if result_id in overlapping_internal_ids:
                    # Find the overlap record for this internal result
                    overlap = next((o for o in comparison_result["overlaps"] if o["internal_id"] == result_id), None)
                    status = "overlap"
                    if overlap:
                        # Find the external tender for this overlap
                        ext = next((t for t in external_results if str(t.get("_id") or t.get("id")) == overlap["external_id"]), None)
                        url = None
                        if ext:
                            url = ext.get("tender_url") or ext.get("external_best_url") or ""
                        if url:
                            if "oferent" in url:
                                status = "overlap_oferent"
                            elif "biznes-polska" in url:
                                status = "overlap_bizpol"

                else:
                    status = "our_unique"
                update_operations.append({
                    "filter": {"_id": result["_id"]},
                    "update": {
                        "$set": {
                            "external_compare_status": status,
                            "updated_at": datetime.utcnow()
                        }
                    }
                })
            
            # Execute bulk updates
            updated_count = 0
            if update_operations:
                for operation in update_operations:
                    
                    result = await db.tender_analysis_results.update_one(
                        operation["filter"], 
                        operation["update"]
                    )
                    
                    updated_count += result.modified_count
            
            logger.info(f"Updated {updated_count} tender analysis results")
            
            return {
                "message": "External comparison completed successfully",
                "analysis_id": analysis_id,
                "date": start_date,  # keep as string
                "comparison_results": {
                    "total_external": len(external_results),
                    "total_internal": len(internal_results),
                    "unique_external": unique_external,
                    "unique_internal": unique_internal,
                    "overlaps": overlaps
                },
                # "updated_count":  updated_count
            }
            
        except Exception as e:
            logger.error(f"Error in external comparison: {str(e)}")
            raise
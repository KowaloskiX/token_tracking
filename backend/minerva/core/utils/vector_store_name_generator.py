from hashlib import md5
from typing import Optional

def generate_vector_store_name(tender_name: str, organization: Optional[str] = None, max_length: int = 256) -> str:
    # Create a base prefix for the vector store
    prefix = "vs_tender_"
    
    # Calculate remaining length for the tender identifier
    remaining_length = max_length - len(prefix)
    
    # Create a unique hash of the full tender name
    name_hash = md5(tender_name.encode()).hexdigest()[:8]
    
    # If we have an organization, try to include a portion of it
    if organization:
        # Clean and truncate organization name
        org_clean = ''.join(c for c in organization if c.isalnum())
        org_part = org_clean[:20] if org_clean else ''
        
        # Calculate space left for tender name
        name_space = remaining_length - len(name_hash) - len(org_part) - 2  # 2 for separators
        
        if name_space > 10:
            # Clean and truncate tender name
            tender_clean = ''.join(c for c in tender_name if c.isalnum())
            tender_part = tender_clean[:name_space]
            
            # Combine all parts
            return f"{prefix}{org_part}_{tender_part}_{name_hash}"
    
    # Fallback to simpler format if no organization or not enough space
    # Clean and truncate tender name
    tender_clean = ''.join(c for c in tender_name if c.isalnum())
    tender_part = tender_clean[:remaining_length - len(name_hash) - 1]  # 1 for separator
    
    return f"{prefix}{tender_part}_{name_hash}"
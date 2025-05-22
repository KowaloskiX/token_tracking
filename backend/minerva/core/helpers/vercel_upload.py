from dotenv import load_dotenv
from fastapi import HTTPException
import vercel_blob


load_dotenv()

def upload_file_to_vercel_blob(filename: str, file_content: bytes) -> str:

    try:
        vercel_url = vercel_blob.put(filename, file_content)['url']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error vercel file upload: {str(e)}")
    
    return vercel_url


def delete_file_from_vercel_blob(blob_url: str):

    try:
        vercel_blob.delete(blob_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting vercel file: {str(e)}")


def delete_files_from_vercel_blob(blob_urls: list[str]):
    
    try:
        vercel_blob.delete(blob_urls)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting vercel file: {str(e)}")
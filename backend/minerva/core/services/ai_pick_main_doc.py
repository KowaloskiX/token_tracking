import os
from typing import List, Optional, Tuple
import json, re, logging
from fastapi import HTTPException
from minerva.core.middleware.token_tracking import update_user_token_usage
from minerva.core.models.request.ai import LLMSearchRequest
from minerva.core.models.user import User
from minerva.core.services.llm_logic import ask_llm_logic
from minerva.core.services.llm_providers.model_config import get_model_config, get_optimal_max_tokens
import psutil
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Memory logging helper
def log_mem(tag: str = ""):
    try:
        process_mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        logger.info(f"[{tag}] Memory usage: {process_mem:.1f} MB")
    except Exception as mem_exc:
        logger.debug(f"Unable to log memory usage for tag '{tag}': {mem_exc}")

class FileSelectionResponse(BaseModel):
    """Pydantic model – mirrors the JSON schema returned by the LLM."""
    selected: Optional[dict]  # either {"index": int, "filename": str, "category": str} or null


async def ai_pick_main_doc(
    file_entries: List[Tuple[str, str]],  # List of (label, filename) tuples
    current_user: Optional[User] = None,
    run_id: Optional[str] = None,          # to correlate parallel runs (same idea as before)
) -> FileSelectionResponse:
    """
    Decide which file in *file_entries* represents either:
        • „Ogłoszenie o zamówieniu”  (contract notice)  **or**
        • „Specyfikacja Warunków Zamówienia” (SWZ / tender specification)

    The LLM may select **one** PDF/DOC/DOCX entry (or none).
    It must return      {"selected": null}     when nothing matches.
    """

    # 1️⃣  memory trace
    log_mem(f"ai_pick_main_doc:start:{run_id or 'single'}")

    # 2️⃣  craft prompt
    system_message = (
        "You are a careful assistant for public-procurement workflows. "
        "You receive a list of file entries, each containing a label and filename. "
        "Your job is to pick *one* file that is the contract notice "
        "(Polish: \"Ogłoszenie o zamówieniu\") **or** the tender specification "
        "(Polish: \"SWZ\", full name \"Specyfikacja warunków zamówienia\"). "
        "Only PDF, DOC or DOCX files may be selected. "
        "If nothing looks like a notice nor an SWZ, return null."
    )

    user_message = (
        "Here are the file entries:\n<FILES>\n"
        + "\n".join(f"{idx}. Label: {label}\n   File: {name}" for idx, (label, name) in enumerate(file_entries))
        + "\n</FILES>\n\n"
        "Think step-by-step which (if any) sounds like the contract notice or SWZ. "
        "Consider both the label and filename when making your decision. "
        "Return JSON that *exactly* matches this schema:\n"
        "{\n"
        "  \"selected\": null | {\n"
        "     \"index\": integer,    // zero-based index from the <FILES> list\n"
        "     \"filename\": string,  // verbatim file name\n"
        "     \"category\": \"notice\" | \"swz\"  // which kind it is\n"
        "  }\n"
        "}\n"
    )

    # 3️⃣  model config (reuse your helper)
    # model_to_use = "gemini-2.5-flash-preview-05-20" 
    model_to_use = "gpt-4.1-mini"
    provider, max_tokens = get_model_config(model_to_use)

    max_tokens = get_optimal_max_tokens(model_to_use, "high")

    request_data = LLMSearchRequest(
        query=user_message,
        vector_store=None,
        llm={
            "provider": provider,
            "model": model_to_use,
            "temperature": 0,
            "stream": False,
            "max_tokens": max_tokens,
            "system_message": system_message,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "file_selection_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "selected": {
                                "anyOf": [
                                    {"type": "null"},
                                    {
                                        "type": "object",
                                        "properties": {
                                            "index": {"type": "integer"},
                                            "filename": {"type": "string"},
                                            "category": {
                                                "type": "string",
                                                "enum": ["notice", "swz"]
                                            },
                                        },
                                        "required": ["index", "filename", "category"],
                                        "additionalProperties": False,
                                    },
                                ]
                            }
                        },
                        "required": ["selected"],
                        "additionalProperties": False,
                    },
                },
            },
        },
    )

    # 4️⃣  call LLM and robustly parse
    try:
        response = await ask_llm_logic(request_data)

        # First-pass JSON parse
        try:
            parsed = json.loads(response.llm_response)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM gave malformed JSON – first try failed: {e}")
            # sanitise common \uXXXX glitches
            safe = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', response.llm_response)
            try:
                parsed = json.loads(safe)
                logger.info("Parsed JSON after sanitising bad escapes")
            except json.JSONDecodeError as e2:
                logger.error(f"Still invalid JSON after sanitisation: {e2}")
                parsed = {"selected": None}

        # 5️⃣  minimal post-processing / sanity checks
        sel = parsed.get("selected")
        if sel is not None:
            idx = sel.get("index")
            fn  = sel.get("filename")
            # Check bounds & extension
            if idx is None or idx < 0 or idx >= len(file_entries) or fn != file_entries[idx][1]:
                logger.warning("LLM returned inconsistent index/filename → treating as no-choice")
                parsed["selected"] = None
            else:
                ext = fn.lower().split(".")[-1]
                if ext not in {"pdf", "doc", "docx"}:
                    logger.warning("LLM picked unsupported extension → ignoring")
                    parsed["selected"] = None

        # # 6️⃣  token accounting
        # if current_user and getattr(response, "usage", None):
        #     await update_user_token_usage(str(current_user.id), response.usage.total_tokens)

        log_mem(f"ai_pick_main_doc:end:{run_id or 'single'}")
        return FileSelectionResponse(**parsed)

    except Exception as err:
        logger.error(f"ai_pick_main_doc failed: {err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to select main document: {err}")

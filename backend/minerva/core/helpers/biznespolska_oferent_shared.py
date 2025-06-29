import os
import json
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from bson import ObjectId
from fastapi import HTTPException
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysis
from minerva.tasks.services.search_service import perform_tender_search
from minerva.tasks.services.tender_initial_ai_filtering_service import perform_ai_filtering
from minerva.core.database.database import db

def normalize_eb2b_id(tender_id: str) -> str:
    """Normalize eb2b.com.pl tender IDs to a canonical format."""
    if tender_id.startswith("https://platforma.eb2b.com.pl/auction/auction/preview-auction/id/"):
        return tender_id
    m = re.match(r"https://platforma.eb2b.com.pl/open-preview-auction.html/(\d+)/", tender_id)
    if m:
        auction_id = m.group(1)
        return f"https://platforma.eb2b.com.pl/auction/auction/preview-auction/id/{auction_id}"
    return tender_id

def as_dict(t):
    if hasattr(t, "model_dump"):
        return t.model_dump()
    if hasattr(t, "dict"):
        return t.dict()
    return dict(t if isinstance(t, dict) else vars(t))

GENERIC_ORG_TOKENS: set = {
    # ── administrative units ───────────────────────────────────────────────
    "gmina", "gminy", "gminie", "gminę",                                # all cases
    "miasto", "miasta", "miejski", "miejska", "miejskie",
    "miejsko-wiejska", "miejsko-wiejskiej",
    "powiat", "powiatu", "powiatowy", "powiatowa", "powiatowe",
    "powiatowych", "starostwo", "starosta", "starosty", "starostwie",
    "województwo", "wojewodztwo", "wojewódzki", "wojewodzki",
    "wojewódzka", "wojewodzka", "wojewódzkie", "wojewodzkie",
    "urząd", "urzad", "urzad_miasta", "urząd_miasta",
    "urzad_gminy", "urząd_gminy", "urząd_marszałkowski",
    "urzad_marszalkowski",

    # ── institutional nouns ───────────────────────────────────────────────
    "biuro", "wydział", "wydzial", "centrum", "jednostka",
    "zakład", "zaklad", "zespół", "zespol", "ośrodek", "osrodek",
    "instytucja", "organizacja", "komenda", "komenda_powiatowa",
    "szpital", "przychodnia", "dom", "dom_kultury", "biblioteka",
    "cuk", "cukit",

    # ── sector adjectives / nouns ─────────────────────────────────────────
    "komunalny", "komunalna", "komunalne", "komunalnych",
    "techniczny", "techniczna", "techniczne", "technicznych",
    "publiczny", "publiczna", "publiczne", "publicznych",
    "samorządowy", "samorzadowy", "samorządowa", "samorządowe",
    "usług", "uslug", "usługowy", "uslugowy", "usługowych", "uslugowych",
    "mieszkaniowy", "mieszkaniowa", "mieszkaniowe",

    # ── legal forms: “spółka …”, “SA”, “SK-A”, etc. ───────────────────────
    "spółka", "spolka", "sp", "sp.",
    "spółka_jawna", "sj", "s.j.", "spj",
    "spółka_komandytowa", "sk", "s.k.", "sk-a", "spk", "sp.k.",
    "spółka_komandytowo-akcyjna", "ska", "s.k.a.",
    "spółka_akcyjna", "sa", "s.a.", "s.a",
    "psa", "p.s.a.",                                              # prosta S.A.
    "z", "oo", "o.o.", "zoo", "z_o_o", "z.o.o", "z.o.o.",
    "sp_z_oo", "sp_z_o_o", "sp._z_o.o.",                          # all dots/spaces
    "z_ograniczoną_odpowiedzialnością", "z_ograniczona_odpowiedzialnoscia",

    # ── assorted abbreviations often seen in sigla ───────────────────────
    "ag", "ti", "zzp", "dkw", "pcpr", "pcpr-powiat", "pcp", "pc", "zdp",
    "pgk", "pgm", "pgn", "mpgn", "mpgk", "mpwik", "pgwik", "zgkim",
}
STOPWORDS = GENERIC_ORG_TOKENS | {"w", "im", "przy", "dla"}

def is_same_tender(a: dict, b: dict) -> bool:
    LEGAL_SUFFIXES = (
        r"\b(sp[.\s]*z[.\s]*o[.\s]*o[.]?)\b",
        r"\b(spółka z\s+ograniczoną\s+odpowiedzialnością)\b",
        r"\b(gmina)\b",
        r"\b(cukit|cul|cuk)\b",
    )
    LEGAL_SUFFIX_RX = re.compile("|".join(LEGAL_SUFFIXES), re.I)
    NOTICE_ID_RX = re.compile(r"/(\d{4,})(?:/|$)")
    STOPWORDS = (GENERIC_ORG_TOKENS or set()) | {"w", "im", "przy", "dla"}
    def normalise(txt: str | None) -> str:
        if not txt:
            return ""
        txt = re.sub(rf"[„”\"',()\-–{re.escape('.:/')}]", " ", txt.lower())
        txt = LEGAL_SUFFIX_RX.sub(" ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt
    def extract_numeric_id(url: str | None, title: str | None) -> str | None:
        if url:
            m = NOTICE_ID_RX.search(url)
            if m:
                host = urlparse(url).hostname or ""
                return f"{host}:{m.group(1)}"
        if title:
            m = NOTICE_ID_RX.search(title)
            if m:
                return m.group(1)
        return None
    def portal_family(url: str | None) -> str:
        if not url:
            return ""
        host = urlparse(url).hostname or ""
        parts = host.lower().split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()
    def distinctive_tokens(org: str) -> set[str]:
        return {tok for tok in org.split() if tok and tok not in STOPWORDS}
    ida = extract_numeric_id(a.get("id"), a.get("name"))
    idb = extract_numeric_id(b.get("id"), b.get("name"))
    if ida and idb and ida == idb:
        return True
    if portal_family(a.get("id")) != portal_family(b.get("id")):
        return False
    org_a = normalise(a.get("organization"))
    org_b = normalise(b.get("organization"))
    if distinctive_tokens(org_a).isdisjoint(distinctive_tokens(org_b)):
        return False
    name_a = normalise(a.get("name"))
    name_b = normalise(b.get("name"))
    from rapidfuzz import fuzz
    title_score = fuzz.token_set_ratio(name_a, name_b) / 100
    if title_score >= 0.93:
        return True
    tokens_a, tokens_b = set(name_a.split()), set(name_b.split())
    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) < len(tokens_b) else (tokens_b, tokens_a)
    if shorter.issubset(longer):
        return title_score >= 0.80
    return False

def extract_tenders_from_file(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def prepare_tender_analysis(request, current_user):
    tender_analysis = None
    search_phrase_to_use = getattr(request, 'search_phrase', None)
    company_description_to_use = getattr(request, 'company_description', None)
    sources_to_use = getattr(request, 'sources', None)
    analysis_id = getattr(request, 'analysis_id', None)
    if analysis_id:
        try:
            analysis_doc = await db.tender_analysis.find_one({"_id": ObjectId(request.analysis_id)})
            if not analysis_doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tender analysis with ID {analysis_id} not found."
                )
            tender_analysis = TenderAnalysis(**analysis_doc)
            company_description_to_use = tender_analysis.company_description
            search_phrase_to_use = tender_analysis.search_phrase
            sources_to_use = tender_analysis.sources
        except Exception as db_err:
            logging.error(f"Error fetching tender analysis {analysis_id}: {db_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error retrieving tender analysis data.")
    elif company_description_to_use and search_phrase_to_use:
        tender_analysis = TenderAnalysis(
            user_id=current_user.id,
            org_id=None,
            name="Temporary Analysis for Comparison",
            company_description=company_description_to_use,
            search_phrase=search_phrase_to_use,
            sources=sources_to_use or [],
            criteria=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            active=True
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either analysis_id or both company_description and search_phrase must be provided for search and filtering"
        )
    if not search_phrase_to_use:
        raise HTTPException(
            status_code=400,
            detail="Search phrase is required for search and filtering"
        )
    return tender_analysis, search_phrase_to_use, company_description_to_use, sources_to_use

async def run_search_and_filter(request, search_phrase_to_use, company_description_to_use, sources_to_use, dates):
    filter_conditions = []
    if dates:
        filter_conditions.append({"field": "initiation_date", "op": "in", "value": dates})
    else:
        filter_conditions.append({"field": "initiation_date", "op": "eq", "value": None})
    return await perform_tender_search(
        search_phrase=search_phrase_to_use,
        company_description=company_description_to_use,
        tender_names_index_name=getattr(request, 'tender_names_index_name', 'tenders'),
        elasticsearch_index_name=getattr(request, 'elasticsearch_index_name', 'tenders'),
        tender_subjects_index_name=getattr(request, 'tender_subjects_index_name', 'tender-subjects'),
        embedding_model=getattr(request, 'embedding_model', 'text-embedding-3-large'),
        score_threshold=getattr(request, 'score_threshold', 0.5),
        top_k=getattr(request, 'top_k', 30),
        sources=sources_to_use,
        filter_conditions=filter_conditions,
        analysis_id=getattr(request, 'analysis_id', None),
        current_user_id=str(getattr(request, 'current_user_id', '')),
        save_results=getattr(request, 'save_results', False)
    )

def calculate_pre_filter_differences(transformed_result, search_results):
    def get_tender_id_from_dict(tender):
        if isinstance(tender, dict):
            return tender.get("id", "")
        return getattr(tender, "id", "")
    raw_ids_1 = {get_tender_id_from_dict(t) for t in transformed_result.get("tenders", []) if get_tender_id_from_dict(t)}
    raw_ids_2 = {get_tender_id_from_dict(t) for t in search_results["all_tender_matches"] if get_tender_id_from_dict(t)}
    unique_to_1_ids = raw_ids_1 - raw_ids_2
    unique_to_2_ids = raw_ids_2 - raw_ids_1
    overlap_ids = raw_ids_1 & raw_ids_2
    unique_to_1 = [t for t in transformed_result.get("tenders", []) if get_tender_id_from_dict(t) in unique_to_1_ids]
    unique_to_2 = [t for t in search_results["all_tender_matches"] if get_tender_id_from_dict(t) in unique_to_2_ids]
    overlapping = [t for t in transformed_result.get("tenders", []) if get_tender_id_from_dict(t) in overlap_ids]
    return {
        "unique_to_oferent": unique_to_1,
        "unique_to_search": unique_to_2,
        "total_unique_to_oferent": len(unique_to_1),
        "total_unique_to_search": len(unique_to_2),
        "potential_overlaps": overlapping
    }

async def ai_filter_tenders(tender_analysis, matches, combined_search_matches, analysis_id, current_user, ai_batch_size, search_id, save_results, filtering_mode):
    return await perform_ai_filtering(
        tender_analysis=tender_analysis,
        all_tender_matches=matches,
        combined_search_matches=combined_search_matches,
        analysis_id=analysis_id or "",
        current_user=current_user,
        ai_batch_size=ai_batch_size,
        search_id=search_id,
        save_results=save_results,
        filtering_mode=filtering_mode
    )

def generate_comparison_summary(transformed_result, search_results, oferent_filtered_tenders, search_filtered_tenders, oferent_matches):
    return {
        "oferent_total_extracted": len(transformed_result.get("tenders", [])),
        "search_total_found": len(search_results["all_tender_matches"]),
        "oferent_filtered_count": len(oferent_filtered_tenders),
        "search_filtered_count": len(search_filtered_tenders),
        "oferent_filter_rate": len(oferent_filtered_tenders) / max(len(oferent_matches), 1),
        "search_filter_rate": len(search_filtered_tenders) / max(len(search_results["all_tender_matches"]), 1),
        "comparison_notes": {
            "oferent_source": "Direct extraction from Oferent platform",
            "search_source": "Elasticsearch-based search across multiple tender sources",
            "filtering_method": "AI-based relevancy filtering using the same criteria"
        }
    }

def calculate_tender_differences(oferent_filtered_tenders, search_filtered_tenders):
    oferent_tenders = [as_dict(t) for t in oferent_filtered_tenders]
    search_tenders = [as_dict(t) for t in search_filtered_tenders]
    matched_oferent, matched_search, overlaps = set(), set(), []
    for i, t_o in enumerate(oferent_tenders):
        for j, t_s in enumerate(search_tenders):
            if j in matched_search:
                continue
            if t_o.get("id") == t_s.get("id"):
                overlaps.append(t_o | {"matched_with": t_s["id"]})
                matched_oferent.add(i)
                matched_search.add(j)
                break
            if is_same_tender(t_o, t_s):
                overlaps.append(t_o | {"matched_with": t_s["id"]})
                matched_oferent.add(i)
                matched_search.add(j)
                break
    unique_to_oferent = [t for i, t in enumerate(oferent_tenders) if i not in matched_oferent]
    unique_to_search  = [t for j, t in enumerate(search_tenders) if j not in matched_search]
    return {
        "unique_to_oferent": unique_to_oferent,
        "unique_to_search": unique_to_search,
        "total_unique_to_oferent": len(unique_to_oferent),
        "total_unique_to_search": len(unique_to_search),
        "potential_overlaps": overlaps,
    }
def get_best_tender_url(tender: Dict[str, Any]) -> str:
    """
    Extract the best URL for a tender based on client website or external URLs.
    
    Args:
        tender: Tender object/dict containing client and external_urls info
        
    Returns:
        Best URL string or empty string if none found
    """
    procurement_platforms = [
        'ezamowienia.gov.pl', 'platformazakupowa.pl', 'smartpzp.pl', 
        'e-propublico.pl', 'ted.europa.eu', 'logintrade.pl',
        'ezamawiajacy.pl', 'egospodarka.pl', 'eb2b.com.pl',
        'bazakonkurencyjnosci.funduszeeuropejskie.gov.pl', 
        'connect.orlen.pl', 'pge.pl'
    ]
    
    # Platform-specific URL patterns
    patterns = {
        'ezamowienia.gov.pl': r'https://ezamowienia\.gov\.pl/mp-client/search/list/ocds-[\d]+-[\w-]+',
        'pge.pl': r'https://swpp2\.gkpge\.pl/app/demand/notice/public/\d+/details',
        'platformazakupowa.pl': r'https://platformazakupowa\.pl/transakcja/\d+',
        'ezamawiajacy.pl': r'https://[\w-]+\.ezamawiajacy\.pl/pn/[\w-]+/demand/\d+/notice/public/details',
        'eb2b.com.pl': r'https://platforma\.eb2b\.com\.pl/auction/auction/preview-auction/id/\d+',
        'bazakonkurencyjnosci.funduszeeuropejskie.gov.pl': r'https://bazakonkurencyjnosci\.funduszeeuropejskie\.gov\.pl/ogloszenia/\d+',
        'logintrade.pl': r'https://[\w-]+\.logintrade\.net/zapytania_email,\d+,[\w]+'
    }
    
    # First, try client website if it exists and is not empty
    client_website = tender.get('client', {}).get('website', '').strip()
    if client_website:
        return client_website
    
    # Get source type and external URLs
    source_type = tender.get('source_type', '')
    external_urls = tender.get('external_urls', [])
    
    if not external_urls:
        # If no external URLs, try to return oferent_url
        return tender.get('details_url', '')
    
    # Try to match platform-specific patterns based on source_type
    if source_type in patterns:
        pattern = patterns[source_type]
        for url in external_urls:
            if re.match(pattern, url):
                return url
    
    # If no pattern match, find URLs containing procurement platforms
    platform_urls = []
    for url in external_urls:
        for platform in procurement_platforms:
            if platform in url:
                platform_urls.append(url)
                break
    
    # Return the longest URL that contains a procurement platform
    if platform_urls:
        return max(platform_urls, key=len)
    
    # If all else fails, return oferent_url
    return tender.get('details_url', '')

def transform_tenders_to_comparable_format(tenders: List[Any], search_phrase: str = "") -> List[Dict[str, Any]]:
    """
    Transform Tender objects to comparable format.
    
    Args:
        tenders: List of Tender objects or dicts
        search_phrase: Optional search phrase used
        
    Returns:
        List of transformed tender dictionaries
    """
    transformed_tenders = []
    
    for tender in tenders:
        # Handle both Tender objects and dictionaries
        if hasattr(tender, '__dict__'):
            tender_dict = tender.__dict__
        else:
            tender_dict = tender
        
        # Get the best URL for this tender
        tender_url = get_best_tender_url(tender_dict)

        print(tender_dict.get('name', ''), tender_url)
        
        # Create the transformed format
        transformed_tender = {
            "id": tender_url,  # Use the determined URL as ID
            "name": tender_dict.get('name', ''),
            "organization": tender_dict.get('organization', ''),
            "location": tender_dict.get('location', ''),
            "source": "oferent_tenders",  # Adjust as needed
            "search_phrase": search_phrase,
            "source_type": tender_dict.get('source_type', ''),
            "submission_deadline": tender_dict.get('submission_deadline', ''),
            "initiation_date": tender_dict.get('initiation_date', ''),
            "tender_id": tender_dict.get('tender_id', ''),
            "region": tender_dict.get('region', ''),
            # Include client info for additional context
            "client": tender_dict.get('client', {}),
            # Optional: include original oferent URL if needed for reference
            "original_source_url": tender_dict.get('details_url', ''),
            "external_urls": tender_dict.get('external_urls', [])
        }
        
        transformed_tenders.append(transformed_tender)
    
    return transformed_tenders
def transform_endpoint_result(result: Dict[str, Any], search_phrase: str = "") -> Dict[str, Any]:
    """
    Transform the endpoint result to include comparable tender format.
    
    Args:
        result: The result dict from your endpoint
        search_phrase: Optional search phrase
        
    Returns:
        Transformed result with comparable tender format
    """
    tenders = result.get('tenders', [])
    
    # Transform tenders to comparable format
    comparable_tenders = transform_tenders_to_comparable_format(tenders, search_phrase)
    
    # Update the result
    result['tenders'] = comparable_tenders
    result['tender_count'] = len(comparable_tenders)
    
    return result
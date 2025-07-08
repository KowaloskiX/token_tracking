import re
from typing import List, Dict, Any
import logging
import unicodedata

logger = logging.getLogger(__name__)


def strip_highlight_tags(text: str) -> str:
    """Remove only the specific highlight tags we add (<em></em>) while preserving any other content"""
    # Only remove the specific <em> and </em> tags that Elasticsearch adds for highlighting
    clean_text = text.replace('<em>', '').replace('</em>', '')
    return clean_text


def normalize_filename_for_matching(filename: str) -> str:
    """Normalize filename for better matching by removing common variations"""
    # Remove accents/diacritics
    nfkd = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    
    # Replace spaces and special characters with underscores for comparison
    normalized = re.sub(r'[^A-Za-z0-9._-]+', '_', only_ascii)
    
    # Remove leading/trailing underscores
    normalized = re.sub(r'^_+|_+$', '', normalized)
    
    return normalized.lower()


def create_polish_word_variations(word: str) -> List[str]:
    """Create common Polish word variations for better matching"""
    variations = [word]
    
    # Common Polish endings that might be stripped or modified
    polish_endings = [
        'a', 'ą', 'e', 'ę', 'y', 'i', 'o', 'ę', 'ą', 'ami', 'ach', 'em', 'ie', 'owy', 'owa', 'owe'
    ]
    
    # Try removing common endings
    for ending in polish_endings:
        if word.endswith(ending) and len(word) > len(ending) + 2:
            variations.append(word[:-len(ending)])
    
    # Try adding common endings to base word
    if not any(word.endswith(ending) for ending in polish_endings):
        for ending in ['a', 'y', 'e', 'ą', 'ę']:
            variations.append(word + ending)
    
    return list(set(variations))


class KeywordPresenceValidator:
    """Verifies literal keyword presence and returns short, cite-ready snippets."""

    def __init__(self, es_client, index_name: str):
        self.es = es_client
        self.index_name = index_name

    async def check_keywords(
        self,
        tender_id: str,
        keywords: List[str],
        max_snippets_per_kw: int = 100,
        fragment_size: int = 1000,
    ) -> Dict[str, Any]:
        hits: list[dict[str, Any]] = []
        missing: list[str] = []

        for kw in keywords:
            kw = kw.strip()
            
            # Create word variations for better Polish inflection matching
            words = kw.split()
            should_clauses = []
            
            # Exact phrase match (highest priority)
            should_clauses.append({
                "match_phrase": {
                    "text": {
                        "query": kw,
                        "boost": 3.0
                    }
                }
            })
            
            # For multi-word phrases, be much more strict
            if len(words) > 1:
                # Only add phrase variations for multi-word phrases, no fuzzy matching
                # Add match_phrase with slop for slight word order variations
                should_clauses.append({
                    "match_phrase": {
                        "text": {
                            "query": kw,
                            "slop": 1,  # Allow 1 word between phrase words
                            "boost": 2.0
                        }
                    }
                })
                
                # Match with Polish stemming - but keep operator as 'and' to require all words
                should_clauses.append({
                    "match": {
                        "text.stemmed": {
                            "query": kw,
                            "operator": "and",
                            "boost": 1.5
                        }
                    }
                })
            
            # For single words, be more flexible with fuzzy matching and variations
            else:
                # Basic match (less strict than exact phrase)
                should_clauses.append({
                    "match": {
                        "text": {
                            "query": kw,
                            "boost": 2.5
                        }
                    }
                })
                
                # Fuzzy match for single word inflections (more permissive)
                should_clauses.append({
                    "match": {
                        "text": {
                            "query": kw,
                            "fuzziness": "1",  # Allow 1 character difference
                            "prefix_length": 1,  # Reduced from 2 to 1
                            "max_expansions": 50,
                            "boost": 2.0
                        }
                    }
                })
                
                # Wildcard search for partial matches
                should_clauses.append({
                    "wildcard": {
                        "text": {
                            "value": f"*{kw}*",
                            "boost": 1.8
                        }
                    }
                })
                
                # Match with Polish stemming for single words (with error handling)
                should_clauses.append({
                    "match": {
                        "text.stemmed": {
                            "query": kw,
                            "boost": 1.5
                        }
                    }
                })
                
                # Add variations for single words
                variations = create_polish_word_variations(kw)
                for variation in variations:
                    if variation != kw and len(variation) > 1:  # Don't duplicate the original
                        should_clauses.append({
                            "match_phrase": {
                                "text": {
                                    "query": variation,
                                    "boost": 1.2
                                }
                            }
                        })
                        
                        # Also add wildcard for variations
                        should_clauses.append({
                            "wildcard": {
                                "text": {
                                    "value": f"*{variation}*",
                                    "boost": 0.8
                                }
                            }
                        })
            
            # ------------------------------------------------------------------
            # SAFETY GUARD: if we ended up with no search clauses, skip this kw
            # ------------------------------------------------------------------
            if not should_clauses:
                logger.info("No valid search clauses generated for keyword '%s'; treating as missing.", kw)
                missing.append(kw)
                continue
            
            # Build the bool query for the keyword.  We only set
            # `minimum_should_match` when there is more than one clause – this
            # avoids Elasticsearch parse errors for a single-clause / empty list
            # situation.
            bool_query = {
                "should": should_clauses
            }
            if len(should_clauses) > 1:
                bool_query["minimum_should_match"] = 1
            
            # Create a more flexible query that handles Polish inflections
            query = {
                "bool": {
                    "must": [
                        {"term": {"metadata.tender_pinecone_id.keyword": tender_id}},
                        {"bool": bool_query}
                    ]
                }
            }

            try:
                res = await self.es.search(
                    index=self.index_name,
                    body={
                        "query": query,
                        "size": max_snippets_per_kw,
                        "highlight": {
                            "fields": {
                                "text": {
                                    "number_of_fragments": max_snippets_per_kw,
                                    "fragment_size": fragment_size,
                                }
                            },
                            "pre_tags": ["<em>"],
                            "post_tags": ["</em>"],
                        },
                    },
                )

                if res["hits"]["total"]["value"]:
                    snippets: list[dict[str, Any]] = []
                    for h in res["hits"]["hits"]:
                        # "text" highlight may contain multiple fragments. We gather them
                        # until we reach the desired maximum for this keyword.
                        fragment_list = (
                            h.get("highlight", {}).get("text")
                            or [h["_source"]["text"][:fragment_size]]
                        )

                        for fragment in fragment_list:
                            if len(snippets) >= max_snippets_per_kw:
                                break

                            # Remove only the specific highlight tags we added
                            clean_text = strip_highlight_tags(fragment)

                            snippets.append(
                                {
                                    "text": clean_text,
                                    "source": h["_source"]["metadata"].get("source", "unknown"),
                                    "keyword": kw,
                                    "score": h["_score"]
                                }
                            )

                        if len(snippets) >= max_snippets_per_kw:
                            break

                    hits.append({"keyword": kw, "snippets": snippets})
                else:
                    missing.append(kw)

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Keyword check failed for %s → treating as missing. %s", kw, exc)
                missing.append(kw)

        return {"hits": hits, "missing": missing}

    async def get_citations_for_file(
        self,
        tender_id: str,
        filename: str,
        max_citations: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all citations/snippets for a specific file using both original and normalized filename matching.
        """
        normalized_filename = normalize_filename_for_matching(filename)
        
        # Try multiple search strategies
        search_strategies = [
            # Exact match on original filename
            {"term": {"metadata.source.keyword": filename}},
            # Exact match on sanitized filename
            {"term": {"metadata.sanitized_filename.keyword": normalized_filename}},
            # Partial match on source
            {"wildcard": {"metadata.source.keyword": f"*{filename}*"}},
            # Partial match on sanitized filename  
            {"wildcard": {"metadata.sanitized_filename.keyword": f"*{normalized_filename}*"}}
        ]
        
        all_citations = []
        seen_texts = set()
        
        for strategy in search_strategies:
            if len(all_citations) >= max_citations:
                break
                
            query = {
                "bool": {
                    "must": [
                        {"term": {"metadata.tender_pinecone_id.keyword": tender_id}},
                        strategy
                    ]
                }
            }
            
            try:
                res = await self.es.search(
                    index=self.index_name,
                    body={
                        "query": query,
                        "size": max_citations,
                        "_source": ["text", "metadata.source", "metadata.file_id"]
                    }
                )
                
                for hit in res["hits"]["hits"]:
                    text = hit["_source"]["text"]
                    # Avoid duplicate texts
                    if text not in seen_texts and len(all_citations) < max_citations:
                        seen_texts.add(text)
                        all_citations.append({
                            "text": text,
                            "source": hit["_source"]["metadata"]["source"],
                            "file_id": hit["_source"]["metadata"].get("file_id"),
                            "score": hit["_score"]
                        })
                        
            except Exception as exc:
                logger.warning(f"File citation search failed for strategy {strategy}: {exc}")
                continue
        
        return all_citations
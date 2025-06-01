from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class KeywordPresenceValidator:
    """Verifies literal keyword presence and returns short, cite-ready snippets."""

    def __init__(self, es_client, index_name: str):
        self.es = es_client
        self.index_name = index_name

    async def check_keywords(
        self,
        tender_id: str,
        keywords: List[str],
        max_snippets_per_kw: int = 3,
        fragment_size: int = 750,
    ) -> Dict[str, Any]:
        hits: list[dict[str, Any]] = []
        missing: list[str] = []

        for kw in keywords:
            kw = kw.strip()
            query = {
                "bool": {
                    "must": [
                        {"term": {"metadata.tender_pinecone_id.keyword": tender_id}},
                        {"match_phrase": {"text": kw}},
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

                            snippets.append(
                                {
                                    "text": fragment,
                                    "source": h["_source"]["metadata"].get("source", "unknown"),
                                    "score": h["_score"],
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

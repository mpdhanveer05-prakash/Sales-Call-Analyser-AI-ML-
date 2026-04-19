"""OpenSearch full-text indexing and search for call transcripts."""
import logging
from datetime import date
from typing import Optional
from urllib.parse import urlparse

from opensearchpy import OpenSearch

from app.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "call_transcripts"

INDEX_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "english_analyzer": {
                    "type": "standard",
                    "stopwords": "_english_",
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "call_id": {"type": "keyword"},
            "agent_id": {"type": "keyword"},
            "agent_name": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                },
            },
            "call_date": {"type": "date"},
            "transcript_text": {
                "type": "text",
                "analyzer": "english",
                "term_vector": "with_positions_offsets",
            },
            "disposition": {"type": "keyword"},
            "speech_score": {"type": "float"},
            "sales_score": {"type": "float"},
            "duration_seconds": {"type": "integer"},
            "segments": {
                "type": "nested",
                "properties": {
                    "speaker": {"type": "keyword"},
                    "start_ms": {"type": "integer"},
                    "end_ms": {"type": "integer"},
                    "text": {
                        "type": "text",
                        "term_vector": "with_positions_offsets",
                    },
                },
            },
        }
    },
}


def _get_client() -> OpenSearch:
    parsed = urlparse(settings.opensearch_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 9200
    scheme = parsed.scheme or "http"
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_compress=True,
        use_ssl=(scheme == "https"),
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def ensure_index() -> None:
    """Create the OpenSearch index if it does not already exist.

    Failures are logged as warnings — the app continues even if OpenSearch
    is unavailable at startup.
    """
    try:
        client = _get_client()
        if not client.indices.exists(index=INDEX_NAME):
            client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
            logger.info("Created OpenSearch index '%s'", INDEX_NAME)
        else:
            logger.debug("OpenSearch index '%s' already exists", INDEX_NAME)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not ensure OpenSearch index '%s': %s", INDEX_NAME, exc)


def index_call(
    call_id: str,
    agent_id: Optional[str],
    agent_name: Optional[str],
    call_date: Optional[date],
    disposition: Optional[str],
    speech_score: Optional[float],
    sales_score: Optional[float],
    duration_seconds: Optional[int],
    segments: list[dict],
) -> None:
    """Index a single call document into OpenSearch.

    Failures are caught and logged — the pipeline continues on error.

    ``segments`` is a list of dicts with keys: speaker, start_ms, end_ms, text.
    """
    try:
        client = _get_client()

        transcript_text = " ".join(seg.get("text", "") for seg in segments)

        doc = {
            "call_id": call_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "call_date": call_date.isoformat() if call_date else None,
            "transcript_text": transcript_text,
            "disposition": disposition,
            "speech_score": speech_score,
            "sales_score": sales_score,
            "duration_seconds": duration_seconds,
            "segments": [
                {
                    "speaker": seg.get("speaker"),
                    "start_ms": seg.get("start_ms"),
                    "end_ms": seg.get("end_ms"),
                    "text": seg.get("text", ""),
                }
                for seg in segments
            ],
        }

        client.index(index=INDEX_NAME, id=call_id, body=doc, refresh=True)
        logger.info("Indexed call %s into OpenSearch", call_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to index call %s into OpenSearch: %s", call_id, exc)


def search_calls(
    query: str,
    agent_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    disposition: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Search calls using OpenSearch full-text search.

    Returns a list of result dicts with keys:
        call_id, agent_id, agent_name, call_date, disposition,
        speech_score, sales_score, duration_seconds, highlights,
        matched_segment, score
    """
    try:
        client = _get_client()

        filters: list[dict] = []
        if agent_id:
            filters.append({"term": {"agent_id": agent_id}})
        if disposition:
            filters.append({"term": {"disposition": disposition}})
        if date_from or date_to:
            date_range: dict = {}
            if date_from:
                date_range["gte"] = date_from
            if date_to:
                date_range["lte"] = date_to
            filters.append({"range": {"call_date": date_range}})

        nested_query = {
            "nested": {
                "path": "segments",
                "query": {
                    "match": {
                        "segments.text": {
                            "query": query,
                            "operator": "or",
                        }
                    }
                },
                "inner_hits": {
                    "size": 1,
                    "_source": ["segments.start_ms", "segments.text"],
                    "highlight": {
                        "fields": {
                            "segments.text": {
                                "pre_tags": ["<mark>"],
                                "post_tags": ["</mark>"],
                                "fragment_size": 200,
                                "number_of_fragments": 1,
                            }
                        }
                    },
                },
            }
        }

        should_queries: list[dict] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["transcript_text", "agent_name"],
                    "type": "best_fields",
                    "operator": "or",
                }
            },
            nested_query,
        ]

        body: dict = {
            "size": limit,
            "query": {
                "bool": {
                    "should": should_queries,
                    "minimum_should_match": 1,
                    "filter": filters,
                }
            },
            "highlight": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fragment_size": 200,
                "number_of_fragments": 2,
                "fields": {
                    "transcript_text": {},
                },
            },
            "_source": True,
        }

        response = client.search(index=INDEX_NAME, body=body)
        hits = response.get("hits", {}).get("hits", [])

        results: list[dict] = []
        for hit in hits:
            src = hit.get("_source", {})
            hl = hit.get("highlight", {})
            inner = hit.get("inner_hits", {})

            # Collect top-level highlights
            highlights: list[str] = []
            for frags in hl.values():
                highlights.extend(frags)

            # Extract best matched segment from nested inner_hits
            matched_segment: Optional[dict] = None
            seg_inner = inner.get("segments", {}).get("hits", {}).get("hits", [])
            if seg_inner:
                seg_src = seg_inner[0].get("_source", {})
                matched_segment = {
                    "start_ms": seg_src.get("start_ms", 0),
                    "text": seg_src.get("text", ""),
                }

            results.append(
                {
                    "call_id": src.get("call_id", hit["_id"]),
                    "agent_id": src.get("agent_id"),
                    "agent_name": src.get("agent_name"),
                    "call_date": src.get("call_date"),
                    "disposition": src.get("disposition"),
                    "speech_score": src.get("speech_score"),
                    "sales_score": src.get("sales_score"),
                    "duration_seconds": src.get("duration_seconds"),
                    "highlights": highlights,
                    "matched_segment": matched_segment,
                    "score": hit.get("_score", 0.0),
                }
            )

        return results

    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenSearch search failed: %s", exc)
        return []

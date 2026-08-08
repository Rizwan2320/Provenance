# src/ingestion/entities.py

"""
Entity extraction — single document scope. spaCy NER, local, no API cost.
Cross-document canonicalization is a separate, later step — not built yet,
see LEARNINGS.md for why.
"""

from __future__ import annotations
from collections import defaultdict

import spacy

from configurations.schema import CanonicalEntity, EntityType


_nlp = None  # lazy singleton — spaCy model load is expensive, load once


_SPACY_TO_ENTITY_TYPE = {
    "ORG": EntityType.ORGANISATION,
    "PERSON": EntityType.PERSON,
    "DATE": EntityType.DATE,
    "MONEY": EntityType.MONEY,
    "GPE": EntityType.LOCATION,
}


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _normalize(text: str) -> str:
    """Cheap normalization for in-document dedup: lowercase, strip common
    legal suffixes. Not fuzzy matching — exact-match on normalized form only."""
    text = text.strip().lower()
    for suffix in [", inc.", " inc.", ", inc", " inc", " corporation", " corp."]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip()


def _is_low_value_entity(text: str) -> bool:
    """Filter obvious NER noise: symbols, single characters, punctuation."""
    stripped = text.strip()
    return len(stripped) <= 1 or not any(c.isalnum() for c in stripped)


def extract_entities(text: str, doc_id: str) -> list[CanonicalEntity]:
    nlp = _get_nlp()
    doc = nlp(text)

    grouped: dict[tuple[str, EntityType], list[str]] = defaultdict(list)

    for ent in doc.ents:
        entity_type = _SPACY_TO_ENTITY_TYPE.get(ent.label_)

        if entity_type is None:
            continue  # skip types outside our schema (ORDINAL, PERCENT, etc.)

        if _is_low_value_entity(ent.text):
            continue  # skip obvious NER noise such as ®

        key = (_normalize(ent.text), entity_type)
        grouped[key].append(ent.text)

    entities = []

    for i, ((normalized, entity_type), surface_forms) in enumerate(grouped.items()):
        entities.append(
            CanonicalEntity(
                id=f"{doc_id}-entity{i}",
                document_id=doc_id,
                canonical_name=surface_forms[0],
                entity_type=entity_type,
                mention_count=len(surface_forms),
                aliases=list(set(surface_forms)),
            )
        )

    return entities
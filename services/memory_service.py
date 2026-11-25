import re
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from database import (
    memories_collection,
    memory_proposals_collection,
    memory_versions_collection,
    memory_audit_collection
)


# --------------------------------------------------
# Agronomic Temporal Validity Rules (in days)
# None = persistent until explicitly updated
# --------------------------------------------------

CATEGORY_TTL_DAYS = {
    "crop_health": 30,    # Transient disease/pest reports decay after 30 days
    "crop": 180,          # Seasonal crop cycle (~6 months)
    "irrigation": 180,    # Seasonal irrigation practice
    "soil": None,         # Persistent until new soil test
    "farm_profile": None  # Persistent farm location / area
}


# --------------------------------------------------
# Utility functions
# --------------------------------------------------

def current_time():
    return datetime.now(timezone.utc)


def compute_valid_until(category, base_time=None):
    """Compute expiration timestamp based on agronomic category TTL."""
    ttl_days = CATEGORY_TTL_DAYS.get(category)
    if ttl_days is None:
        return None
    ref = base_time or current_time()
    return ref + timedelta(days=ttl_days)


def log_memory_action(
    action,
    memory_id=None,
    proposal_id=None,
    owner_id=None,
    details=None
):
    """Record every memory operation in the audit collection."""

    memory_audit_collection.insert_one({
        "action": action,
        "memory_id": str(memory_id) if memory_id else None,
        "proposal_id": str(proposal_id) if proposal_id else None,
        "owner_id": owner_id,
        "details": details or {},
        "timestamp": current_time()
    })


def serialize_document(document):
    """Convert MongoDB ObjectId into a JSON-friendly string."""

    if not document:
        return None

    document["_id"] = str(document["_id"])
    return document


# --------------------------------------------------
# Database indexes
# --------------------------------------------------

def initialize_memory_indexes():
    """Create indexes for efficient memory retrieval."""

    memories_collection.create_index([
        ("scope", ASCENDING),
        ("owner_id", ASCENDING),
        ("category", ASCENDING)
    ])

    memories_collection.create_index(
        [("key", ASCENDING), ("scope", ASCENDING)]
    )

    memories_collection.create_index(
        [("valid_until", ASCENDING)]
    )

    memory_proposals_collection.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)]
    )

    memory_versions_collection.create_index(
        [("memory_id", ASCENDING), ("version", DESCENDING)]
    )

    memory_audit_collection.create_index(
        [("timestamp", DESCENDING)]
    )


# --------------------------------------------------
# 1. Create a memory proposal
# --------------------------------------------------

def create_memory_proposal(
    key,
    content,
    category,
    scope="farmer",
    owner_id=None,
    source_conversation_id=None,
    source_message_id=None,
    evidence=None
):
    """
    Create a pending memory proposal.

    scope:
        farmer  -> information belonging to a specific farmer
        general -> general agricultural knowledge
    """

    if not key or not content or not category:
        raise ValueError("Key, content and category are required.")

    if scope not in ("farmer", "general"):
        raise ValueError("Scope must be 'farmer' or 'general'.")

    if scope == "farmer" and not owner_id:
        raise ValueError("Farmer-specific memories require an owner_id.")

    if scope == "general":
        owner_id = None

    # Avoid creating duplicate pending proposals.
    existing = memory_proposals_collection.find_one({
        "key": key,
        "scope": scope,
        "owner_id": owner_id,
        "status": "pending"
    })

    if existing:
        return {
            "success": True,
            "message": "A similar pending proposal already exists.",
            "proposal_id": str(existing["_id"])
        }

    proposal = {
        "key": key,
        "content": content,
        "category": category,
        "scope": scope,
        "owner_id": owner_id,
        "source_conversation_id": source_conversation_id,
        "source_message_id": source_message_id,
        "evidence": evidence or {},
        "status": "pending",
        "created_at": current_time(),
        "reviewed_at": None
    }

    result = memory_proposals_collection.insert_one(proposal)

    log_memory_action(
        action="proposal_created",
        proposal_id=result.inserted_id,
        owner_id=owner_id,
        details={"key": key, "scope": scope, "category": category}
    )

    return {
        "success": True,
        "message": "Memory proposal created successfully.",
        "proposal_id": str(result.inserted_id)
    }


# --------------------------------------------------
# 2. Retrieve memory proposals
# --------------------------------------------------

def get_memory_proposals(status="pending", owner_id=None):
    """Retrieve proposals, optionally filtered by status and owner."""

    query = {}

    if status:
        query["status"] = status

    if owner_id:
        query["$or"] = [
            {"owner_id": owner_id},
            {"scope": "general"}
        ]

    proposals = memory_proposals_collection.find(
        query
    ).sort("created_at", DESCENDING)

    return [serialize_document(p) for p in proposals]


# --------------------------------------------------
# 3. Approve a memory proposal
# --------------------------------------------------

def approve_memory_proposal(
    proposal_id,
    reviewed_by="admin",
    owner_id=None
):
    """
    Approve a pending proposal and save it in permanent memory.

    If owner_id is supplied, only that farmer's own
    farmer-scoped proposal can be approved.
    """

    if not ObjectId.is_valid(proposal_id):
        return {
            "success": False,
            "message": "Invalid proposal ID."
        }

    proposal_query = {
        "_id": ObjectId(proposal_id),
        "status": "pending"
    }

    # Enforce farmer ownership for dashboard actions.
    if owner_id is not None:
        proposal_query["owner_id"] = owner_id
        proposal_query["scope"] = "farmer"

    proposal = memory_proposals_collection.find_one(proposal_query)

    if not proposal:
        return {
            "success": False,
            "message": "Pending proposal not found or access denied."
        }

    now = current_time()
    valid_until = compute_valid_until(proposal["category"], now)

    memory_query = {
        "key": proposal["key"],
        "scope": proposal["scope"],
        "owner_id": proposal["owner_id"]
    }

    existing_memory = memories_collection.find_one(memory_query)

    if existing_memory:
        # Preserve the previous version.
        memory_versions_collection.insert_one({
            "memory_id": str(existing_memory["_id"]),
            "version": existing_memory.get("version", 1),
            "key": existing_memory["key"],
            "content": existing_memory["content"],
            "category": existing_memory["category"],
            "scope": existing_memory["scope"],
            "owner_id": existing_memory["owner_id"],
            "recorded_at": now,
            "verification_status": existing_memory.get(
                "verification_status", "unverified"
            ),
            "source_type": existing_memory.get(
                "source_type", "farmer_report"
            )
        })

        new_version = existing_memory.get("version", 1) + 1

        memories_collection.update_one(
            {"_id": existing_memory["_id"]},
            {
                "$set": {
                    "content": proposal["content"],
                    "category": proposal["category"],
                    "version": new_version,
                    "updated_at": now,
                    "last_proposal_id": str(proposal["_id"]),
                    "approval_status": "approved",
                    "verification_status": "unverified",
                    "source_type": "farmer_report",
                    "source_message_id": proposal.get("source_message_id"),
                    "valid_from": now,
                    "valid_until": valid_until
                }
            }
        )

        memory_id = existing_memory["_id"]
        action = "memory_updated"

    else:
        # Create a new permanent memory.
        memory = {
            "key": proposal["key"],
            "content": proposal["content"],
            "category": proposal["category"],
            "scope": proposal["scope"],
            "owner_id": proposal["owner_id"],
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "source_conversation_id": proposal.get(
                "source_conversation_id"
            ),
            "last_proposal_id": str(proposal["_id"]),
            "approval_status": "approved",
            "verification_status": "unverified",
            "source_type": "farmer_report",
            "source_message_id": proposal.get("source_message_id"),
            "valid_from": now,
            "valid_until": valid_until
        }

        result = memories_collection.insert_one(memory)

        memory_id = result.inserted_id
        action = "memory_created"

    # Mark the proposal as approved.
    update_result = memory_proposals_collection.update_one(
        {
            "_id": proposal["_id"],
            "status": "pending"
        },
        {
            "$set": {
                "status": "approved",
                "reviewed_at": now,
                "reviewed_by": reviewed_by,
                "memory_id": str(memory_id)
            }
        }
    )

    if update_result.modified_count == 0:
        return {
            "success": False,
            "message": "Proposal was already processed."
        }

    log_memory_action(
        action=action,
        memory_id=memory_id,
        proposal_id=proposal["_id"],
        owner_id=proposal["owner_id"],
        details={
            "key": proposal["key"],
            "version": new_version if existing_memory else 1
        }
    )

    return {
        "success": True,
        "message": "Memory approved and saved successfully.",
        "memory_id": str(memory_id)
    }


# --------------------------------------------------
# 4. Reject a memory proposal
# --------------------------------------------------

def reject_memory_proposal(
    proposal_id,
    reviewed_by="admin",
    reason=None,
    owner_id=None
):
    """
    Reject a pending proposal.

    If owner_id is supplied, only that farmer's own
    farmer-scoped proposal can be rejected.
    """

    if not ObjectId.is_valid(proposal_id):
        return {
            "success": False,
            "message": "Invalid proposal ID."
        }

    proposal_query = {
        "_id": ObjectId(proposal_id),
        "status": "pending"
    }

    # Enforce farmer ownership for dashboard actions.
    if owner_id is not None:
        proposal_query["owner_id"] = owner_id
        proposal_query["scope"] = "farmer"

    proposal = memory_proposals_collection.find_one(proposal_query)

    if not proposal:
        return {
            "success": False,
            "message": "Pending proposal not found or access denied."
        }

    now = current_time()

    update_result = memory_proposals_collection.update_one(
        {
            "_id": proposal["_id"],
            "status": "pending"
        },
        {
            "$set": {
                "status": "rejected",
                "reviewed_at": now,
                "reviewed_by": reviewed_by,
                "rejection_reason": reason
            }
        }
    )

    if update_result.modified_count == 0:
        return {
            "success": False,
            "message": "Proposal was already processed."
        }

    log_memory_action(
        action="proposal_rejected",
        proposal_id=proposal["_id"],
        owner_id=proposal["owner_id"],
        details={"reason": reason}
    )

    return {
        "success": True,
        "message": "Memory proposal rejected."
    }


# --------------------------------------------------
# 5. Retrieve approved & non-expired memories
# --------------------------------------------------

def retrieve_memories(
    owner_id=None,
    category=None,
    scope=None,
    limit=20,
    include_expired=False
):
    """Retrieve active approved memories for a farmer or general knowledge."""

    now = current_time()
    and_clauses = []

    if scope == "farmer":
        if not owner_id:
            return []
        and_clauses.append({"scope": "farmer", "owner_id": owner_id})

    elif scope == "general":
        and_clauses.append({"scope": "general"})

    elif owner_id:
        and_clauses.append({
            "$or": [
                {"scope": "farmer", "owner_id": owner_id},
                {"scope": "general"}
            ]
        })

    else:
        and_clauses.append({"scope": "general"})

    if category:
        and_clauses.append({"category": category})

    # Temporal validity filter: exclude memories past their valid_until date
    if not include_expired:
        and_clauses.append({
            "$or": [
                {"valid_until": None},
                {"valid_until": {"$exists": False}},
                {"valid_until": {"$gt": now}}
            ]
        })

    query = {"$and": and_clauses} if len(and_clauses) > 1 else and_clauses[0]

    memories = memories_collection.find(query).sort(
        "updated_at", DESCENDING
    ).limit(limit)

    results = [serialize_document(m) for m in memories]

    if results:
        log_memory_action(
            action="memories_retrieved",
            owner_id=owner_id,
            details={
                "count": len(results),
                "category": category,
                "scope": scope
            }
        )

    return results


# --------------------------------------------------
# 6. Retrieve memory version history
# --------------------------------------------------

def get_memory_versions(memory_id):
    """Return previous versions of a memory."""

    versions = memory_versions_collection.find({
        "memory_id": str(memory_id)
    }).sort("version", DESCENDING)

    return [serialize_document(v) for v in versions]


# --------------------------------------------------
# 7. Candidate Extraction Helper
# --------------------------------------------------

def _extract_memory_candidates(text, analysis):
    """Extract structured candidate key-value records from NLP analysis."""
    entities = analysis.get("entities", {})
    measurements = analysis.get("measurements", [])
    candidates = []

    for crop in entities.get("CROP", []):
        candidates.append({
            "key": "crop_" + crop.lower().replace(" ", "_"),
            "content": f"The farmer grows {crop}.",
            "category": "crop"
        })

    for location in entities.get("LOCATION", []):
        candidates.append({
            "key": "farm_location",
            "content": f"The farmer's agricultural location is {location}.",
            "category": "farm_profile"
        })

    for soil in entities.get("SOIL_TYPE", []):
        candidates.append({
            "key": "soil_type",
            "content": f"The farmer reported {soil}.",
            "category": "soil"
        })

    for disease in entities.get("DISEASE", []):
        candidates.append({
            "key": "reported_symptom_" + disease.lower().replace(" ", "_"),
            "content": (
                f"The farmer reported symptoms associated "
                f"with {disease}. This is a reported symptom, "
                f"not a confirmed diagnosis."
            ),
            "category": "crop_health"
        })

    for pest in entities.get("PEST", []):
        candidates.append({
            "key": "reported_pest_" + pest.lower().replace(" ", "_"),
            "content": f"The farmer reported {pest} in their agricultural context.",
            "category": "crop_health"
        })

    for method in entities.get("IRRIGATION", []):
        candidates.append({
            "key": "irrigation_method",
            "content": f"The farmer reported using {method}.",
            "category": "irrigation"
        })

    for stage in entities.get("GROWTH_STAGE", []):
        candidates.append({
            "key": "growth_stage",
            "content": f"The farmer reported crop growth stage: {stage}.",
            "category": "crop"
        })

    area_pattern = r"\b(\d+(?:\.\d+)?)\s*(acres?|hectares?|ha|bighas?)\b"
    for match in re.finditer(area_pattern, text, re.IGNORECASE):
        value = match.group(1)
        unit = match.group(2).lower()
        candidates.append({
            "key": "farm_area",
            "content": f"The farmer reported a farm area of {value} {unit}.",
            "category": "farm_profile"
        })

    for measurement in measurements:
        if measurement.get("type") == "SOIL_PH":
            value = measurement.get("value")
            candidates.append({
                "key": "soil_ph",
                "content": f"The farmer reported a soil pH value of {value}.",
                "category": "soil"
            })

    unique_candidates = {}
    for candidate in candidates:
        unique_candidates[candidate["key"]] = candidate

    return list(unique_candidates.values())


def is_direct_farmer_assertion(text):
    """
    Determine whether an utterance asserts a direct first-person fact
    rather than a hypothetical scenario, general question, or third-party report.
    """
    text_lower = text.lower().strip()

    # Block hypothetical, negated, or third-party context poisoning triggers
    exclusion_patterns = [
        r"\bwhat if\b",
        r"\bsuppose\b",
        r"\bhypothetically\b",
        r"\bfor example\b",
        r"\bmy neighbor(?:'s|s)?\b",
        r"\bmy friend(?:'s|s)?\b",
        r"\bmy brother(?:'s|s)?\b",
        r"\bmy cousin(?:'s|s)?\b",
        r"\bmy relative(?:'s|s)?\b",
        r"\banother farmer(?:'s|s)?\b",
        r"\bsomeone(?:'s)?\b",
        r"\b(?:do|does|did|is|are|was|were|have|has|had)\s+not\b",
        r"\b(?:don't|doesn't|didn't|isn't|aren't|haven't|hasn't|never|no)\b"
    ]

    if any(re.search(pat, text_lower) for pat in exclusion_patterns):
        return False

    personal_indicators = [
        "my ",
        "our ",
        "i grow ",
        "i cultivate ",
        "i manage ",
        "i have ",
        "i am growing ",
        "i planted ",
        "i noticed ",
        "i see ",
        "we grow ",
        "we cultivate ",
        "we have ",
        "we planted ",
        "my farm",
        "my field",
        "our farm",
        "our field"
    ]

    return any(phrase in text_lower for phrase in personal_indicators)


# --------------------------------------------------
# 8. AUTOMATIC MEMORY PROPOSAL EXTRACTION (GOVERNED)
# --------------------------------------------------

def propose_memories_from_analysis(
    text,
    analysis,
    owner_id,
    conversation_id=None,
    message_id=None
):
    """
    Extract farmer-specific facts from an agricultural
    message and create pending memory proposals.

    Memories are proposed only when the message directly asserts
    information belonging to the farmer (blocking third-party and
    hypothetical context poisoning).
    """

    if not text or not analysis or not owner_id:
        return []

    if not is_direct_farmer_assertion(text):
        return []

    candidates = _extract_memory_candidates(text, analysis)
    results = []

    for candidate in candidates:
        try:
            result = create_memory_proposal(
                key=candidate["key"],
                content=candidate["content"],
                category=candidate["category"],
                scope="farmer",
                owner_id=owner_id,
                source_conversation_id=conversation_id,
                source_message_id=(
                    str(message_id) if message_id else None
                ),
                evidence={
                    "original_message": text,
                    "extraction_method": "agricultural_nlp"
                }
            )

            results.append({
                "key": candidate["key"],
                **result
            })

        except Exception as exc:
            results.append({
                "key": candidate["key"],
                "success": False,
                "message": str(exc)
            })

    return results


# --------------------------------------------------
# 9. UNGATED AUTO-MEMORY BASELINE (FOR ABLATION STUDY)
# --------------------------------------------------

def auto_commit_ungated_memories(
    text,
    analysis,
    owner_id,
    conversation_id=None,
    message_id=None
):
    """
    Baseline helper simulating standard un-gated LLM memory:
    writes every extracted entity directly to permanent memory
    without personal-assertion filtering or HITL approval.
    """
    if not text or not analysis or not owner_id:
        return []

    candidates = _extract_memory_candidates(text, analysis)
    now = current_time()
    committed = []

    for candidate in candidates:
        memories_collection.update_one(
            {
                "key": candidate["key"],
                "scope": "farmer",
                "owner_id": owner_id
            },
            {
                "$set": {
                    "content": candidate["content"],
                    "category": candidate["category"],
                    "version": 1,
                    "updated_at": now,
                    "approval_status": "auto_ungated",
                    "verification_status": "unverified",
                    "source_type": "ungated_extraction",
                    "source_conversation_id": conversation_id,
                    "source_message_id": str(message_id) if message_id else None,
                    "valid_from": now,
                    "valid_until": None
                },
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )
        committed.append(candidate["key"])

    return committed


# --------------------------------------------------
# 10. MEMORY DASHBOARD STATISTICS
# --------------------------------------------------

def get_memory_statistics(owner_id=None):

    farmer_filter = {"scope": "farmer"}

    if owner_id:
        farmer_filter["owner_id"] = owner_id

    approved = memories_collection.count_documents(
        farmer_filter
    )

    pending_filter = {"status": "pending"}

    if owner_id:
        pending_filter["$or"] = [
            {"owner_id": owner_id},
            {"scope": "general"}
        ]

    pending = memory_proposals_collection.count_documents(
        pending_filter
    )

    rejected_filter = {"status": "rejected"}

    if owner_id:
        rejected_filter["$or"] = [
            {"owner_id": owner_id},
            {"scope": "general"}
        ]

    rejected = memory_proposals_collection.count_documents(
        rejected_filter
    )

    general = memories_collection.count_documents({
        "scope": "general"
    })

    return {
        "approved": approved,
        "pending": pending,
        "rejected": rejected,
        "general": general,
        "total": approved + general
    }


# --------------------------------------------------
# 11. GET APPROVED MEMORIES FOR DASHBOARD
# --------------------------------------------------

def get_all_approved_memories(owner_id=None, limit=100):

    query = {}

    if owner_id:
        query["$or"] = [
            {"owner_id": owner_id, "scope": "farmer"},
            {"scope": "general"}
        ]

    records = memories_collection.find(
        query
    ).sort(
        "updated_at", -1
    ).limit(limit)

    return [
        serialize_document(record)
        for record in records
    ]


# --------------------------------------------------
# 12. GET MEMORY AUDIT LOGS
# --------------------------------------------------

def get_memory_audit_logs(owner_id=None, limit=100):

    query = {}

    if owner_id:
        query["$or"] = [
            {"owner_id": owner_id},
            {"owner_id": None}
        ]

    records = memory_audit_collection.find(
        query
    ).sort(
        "timestamp", -1
    ).limit(limit)

    return [
        serialize_document(record)
        for record in records
    ]
from flask import Flask, render_template, request, jsonify, session

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from config import Config

from database import (
    client,
    conversations_collection,
    messages_collection
)

from services.agri_ner import extract_agricultural_entities
from services.llm_service import generate_response
from services.memory_service import (
    propose_memories_from_analysis,
    get_memory_statistics,
    get_memory_proposals,
    get_all_approved_memories,
    get_memory_audit_logs,
    approve_memory_proposal,
    reject_memory_proposal,
    get_memory_versions,
    initialize_memory_indexes
)

try:
    initialize_memory_indexes()
except Exception:
    app_startup_index_error = True


app = Flask(__name__)
app.config.from_object(Config)
app.config.update(
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

@app.before_request
def make_session_persistent():
    # Keep the same farmer identity when the browser is closed and reopened.
    session.permanent = True


# HOME PAGE

@app.route("/")
def home():
    return render_template("index.html")


# CHAT API

@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "error": "Please enter a message."
        }), 400

    try:
        # 1. CHECK MONGODB CONNECTION
        client.admin.command("ping")

        # 2. GET OR CREATE CONVERSATION ID

        conversation_id = session.get("conversation_id")

        if not conversation_id:

            conversation_id = str(uuid4())

            session["conversation_id"] = conversation_id

        # 3. GET OR CREATE FARMER ID

        farmer_id = session.get("farmer_id")

        if not farmer_id:

            farmer_id = str(uuid4())

            session["farmer_id"] = farmer_id

        # 4. AGRICULTURAL NLP ANALYSIS

        nlp_analysis = extract_agricultural_entities(
            user_message
        )

        # 5. SAVE USER MESSAGE + NLP ANALYSIS

        user_message_result = messages_collection.insert_one({

            "conversation_id": conversation_id,

            "farmer_id": farmer_id,

            "role": "user",

            "content": user_message,

            "nlp_analysis": nlp_analysis,

            "created_at": datetime.now(timezone.utc)

        })

        # 6. AUTOMATIC MEMORY PROPOSAL EXTRACTION

        memory_proposals = []

        try:

            memory_proposals = propose_memories_from_analysis(

                text=user_message,

                analysis=nlp_analysis,

                owner_id=farmer_id,

                conversation_id=conversation_id,

                message_id=user_message_result.inserted_id

            )

            app.logger.info(
                "Memory proposals generated: %s",
                len(memory_proposals)
            )

        except Exception:

            app.logger.exception(
                "Automatic memory extraction failed"
            )

        # 7. RETRIEVE CONVERSATION HISTORY

        history = list(

            messages_collection.find(

                {
                    "conversation_id": conversation_id
                },

                {
                    "_id": 0,
                    "role": 1,
                    "content": 1
                }

            ).sort(
                "created_at", -1
            ).limit(12)

        )

        history.reverse()

        # 8. GENERATE INTELLIGENT RESPONSE

        answer = generate_response(

            history,

            nlp_analysis=nlp_analysis,
            owner_id=farmer_id

        )

        # 9. SAVE ASSISTANT RESPONSE

        messages_collection.insert_one({

            "conversation_id": conversation_id,

            "farmer_id": farmer_id,

            "role": "assistant",

            "content": answer,

            "created_at": datetime.now(timezone.utc)

        })

        # 10. RETURN API RESPONSE

        return jsonify({

            "response": answer,

            "conversation_id": conversation_id,

            "farmer_id": farmer_id,

            "nlp_analysis": nlp_analysis,

            "memory_proposals": memory_proposals

        })

    except Exception:

        app.logger.exception(
            "Chat processing failed"
        )

        return jsonify({

            "error": (
                "Unable to process your request. "
                "Check Ollama and MongoDB connections."
            )

        }), 500


# MEMORY DASHBOARD - STATISTICS

@app.route("/api/memory/stats")
def memory_stats():

    try:
        farmer_id = session.get("farmer_id")

        if not farmer_id:
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        stats = get_memory_statistics(
            owner_id=farmer_id
        )

        return jsonify(stats)

    except Exception:

        app.logger.exception("Memory statistics failed")

        return jsonify({
            "error": "Unable to retrieve memory statistics."
        }), 500


# MEMORY DASHBOARD - PENDING PROPOSALS

@app.route("/api/memory/proposals")
def memory_proposals_api():

    try:
        farmer_id = session.get("farmer_id")

        if not farmer_id:
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        proposals = get_memory_proposals(
            status="pending",
            owner_id=farmer_id
        )

        return jsonify({
            "proposals": proposals
        })

    except Exception:

        app.logger.exception("Memory proposals retrieval failed")

        return jsonify({
            "error": "Unable to retrieve memory proposals."
        }), 500


# MEMORY DASHBOARD - APPROVED MEMORIES

@app.route("/api/memory/approved")
def approved_memories_api():

    try:
        farmer_id = session.get("farmer_id")

        if not farmer_id:
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        memories = get_all_approved_memories(
            owner_id=farmer_id
        )

        return jsonify({
            "memories": memories
        })

    except Exception:

        app.logger.exception("Approved memories retrieval failed")

        return jsonify({
            "error": "Unable to retrieve approved memories."
        }), 500


# MEMORY DASHBOARD - APPROVE PROPOSAL

@app.route(
    "/api/memory/approve/<proposal_id>",
    methods=["POST"]
)
def approve_memory_api(proposal_id):

    try:
        if not session.get("farmer_id"):
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        result = approve_memory_proposal(
            proposal_id,
            reviewed_by="farmer",
            owner_id=session["farmer_id"]
        )

        status_code = 200 if result["success"] else 400

        return jsonify(result), status_code

    except Exception:

        app.logger.exception("Memory approval failed")

        return jsonify({
            "error": "Unable to approve memory."
        }), 500


# MEMORY DASHBOARD - REJECT PROPOSAL

@app.route(
    "/api/memory/reject/<proposal_id>",
    methods=["POST"]
)
def reject_memory_api(proposal_id):

    try:
        if not session.get("farmer_id"):
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        data = request.get_json(silent=True) or {}

        result = reject_memory_proposal(
            proposal_id,
            reviewed_by="farmer",
            reason=data.get("reason"),
            owner_id=session["farmer_id"]
        )

        status_code = 200 if result["success"] else 400

        return jsonify(result), status_code

    except Exception:

        app.logger.exception("Memory rejection failed")

        return jsonify({
            "error": "Unable to reject memory."
        }), 500


# MEMORY DASHBOARD - VERSION HISTORY

@app.route("/api/memory/versions/<memory_id>")
def memory_versions_api(memory_id):

    try:
        if not session.get("farmer_id"):
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        # Verify that the requested memory belongs to this farmer or is general knowledge.
        memories = get_all_approved_memories(
            owner_id=session["farmer_id"]
        )

        allowed_ids = {
            memory["_id"] for memory in memories
        }

        if memory_id not in allowed_ids:
            return jsonify({
                "error": "Memory not found."
            }), 404

        versions = get_memory_versions(memory_id)

        return jsonify({
            "versions": versions
        })

    except Exception:

        app.logger.exception("Memory versions retrieval failed")

        return jsonify({
            "error": "Unable to retrieve memory versions."
        }), 500


# MEMORY DASHBOARD - AUDIT LOGS

@app.route("/api/memory/audit")
def memory_audit_api():

    try:
        farmer_id = session.get("farmer_id")

        if not farmer_id:
            return jsonify({
                "error": "Farmer session not found."
            }), 401

        logs = get_memory_audit_logs(
            owner_id=farmer_id
        )

        return jsonify({
            "logs": logs
        })

    except Exception:

        app.logger.exception("Memory audit retrieval failed")

        return jsonify({
            "error": "Unable to retrieve audit logs."
        }), 500


# HEALTH CHECK

@app.route("/health")
def health():

    try:

        client.admin.command("ping")

        mongo_status = "Connected"

    except Exception:

        mongo_status = "Disconnected"

    return jsonify({

        "application": "EvoMindAgri",

        "mongodb": mongo_status,

        "status": "Running"

    })


# RUN APPLICATION

if __name__ == "__main__":

    app.run(debug=True)

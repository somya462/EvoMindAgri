import time
import json
import ollama

from config import Config
from services.agri_ner import extract_agricultural_entities
from services.memory_service import retrieve_memories


SYSTEM_PROMPT = """
You are EvoMindAgri, an intelligent agricultural
knowledge assistant.

Your initial domain focus is wheat and mustard
cultivation in Haryana, India.

Your responsibilities include:

1. Crop cultivation
2. Soil health
3. Irrigation management
4. Fertilizer management
5. Crop diseases and pests
6. Agricultural practices

AGRICULTURAL GUIDELINES:

- Understand the user's agricultural question.
- Use extracted NLP entities as contextual information.
- Give clear, structured and practical explanations.
- Never invent scientific facts or references.
- Distinguish general information from personalized advice.
- Ask follow-up questions when essential information is missing.
- Mention uncertainty where appropriate.
- Recommend expert verification for high-risk decisions.
- Use simple language farmers can understand.
- Structure longer answers using headings and bullet points.

MEMORY GUIDELINES:

- Use approved memories only.
- Never treat pending memory proposals as verified facts.
- Farmer-specific memories belong only to their respective farmer.
- General agricultural memories may be used when relevant.
- Treat farmer-reported information as reported information,
  not independently verified scientific evidence.
- Prioritize the farmer's latest explicit statement if it
  conflicts with an older stored memory.
- Do not assume an old memory is still current.
- Do not invent farmer information that is not in memory.
- If relevant information is missing, ask the farmer.

MEMORY RECALL BEHAVIOUR:

If the detected intent is MEMORY_RECALL:

1. Retrieve and report the relevant approved memories.
2. Answer only the information requested.
3. Do not provide unsolicited agricultural recommendations.
4. Do not introduce unrelated crop-management advice.
5. Clearly identify stored values as recorded information.
6. Mention uncertainty only when relevant.
7. Keep the answer concise.

SOIL CHEMISTRY SAFETY:

- Elemental sulfur generally lowers soil pH.
- Agricultural lime generally raises soil pH.
- Never reverse these effects.
- Never recommend a soil amendment dosage without
  sufficient soil-test information.
- Distinguish general soil science information
  from field-specific recommendations.

CONVERSATION RULES:

1. Always prioritize the latest question.
2. Do not continue an earlier topic unless requested.
3. If the user changes crops or topics, switch accordingly.
4. Use previous messages only when relevant.
5. Never claim to remember information unless it was retrieved.
6. Treat extracted entities as NLP predictions, not verified facts.
7. If an extracted entity conflicts with the user's actual
   statement, prioritize the user's statement.

You are the conversational intelligence component
of EvoMindAgri.
"""


def generate_response(
    conversation_history,
    nlp_analysis=None,
    owner_id=None,
    memory_mode="evomind_governed",
    return_metrics=False
):
    """
    Generate an agricultural response using Ollama.

    Parameters:
    - memory_mode:
        'stateless'        -> Sliding-window conversation history only
        'ungated_auto'     -> Unfiltered/unapproved memory baseline
        'evomind_governed' -> Approved HITL-governed episodic memory (default)
    - return_metrics:
        When True, returns a dict with 'response' and telemetry metrics
        for research benchmarking. When False, returns response string
        for normal Flask app compatibility.
    """

    start_time = time.perf_counter()

    try:
        # 1. IDENTIFY LATEST USER QUESTION & INDEX
        latest_question = None
        latest_user_idx = None

        for idx in range(len(conversation_history) - 1, -1, -1):
            msg = conversation_history[idx]
            if msg.get("role") == "user":
                latest_question = msg.get("content")
                latest_user_idx = idx
                break

        if not latest_question:
            raise ValueError("No user question found.")

        # 2. POPULATE SHORT-TERM CONVERSATION HISTORY
        previous_messages = []
        for idx, msg in enumerate(conversation_history):
            if idx == latest_user_idx:
                continue
            role = msg.get("role")
            content = msg.get("content", "").strip()
            if role in ("user", "assistant") and content:
                previous_messages.append({
                    "role": role,
                    "content": content
                })

        # 3. PREPARE NLP CONTEXT
        if nlp_analysis is None:
            nlp_analysis = extract_agricultural_entities(latest_question)

        nlp_context = json.dumps(
            nlp_analysis,
            indent=2,
            ensure_ascii=False
        )

        # 4. RETRIEVE MEMORIES BY EXPERIMENTAL MODE
        farmer_memories = []
        general_memories = []

        if memory_mode != "stateless":
            if owner_id:
                farmer_memories = retrieve_memories(
                    owner_id=owner_id,
                    scope="farmer",
                    limit=20
                )

            general_memories = retrieve_memories(
                scope="general",
                limit=20
            )

        memory_context = {
            "memory_governance_mode": memory_mode,
            "farmer_specific_memories": [
                {
                    "key": memory.get("key"),
                    "content": memory.get("content"),
                    "category": memory.get("category"),
                    "version": memory.get("version"),
                    "verification_status": memory.get(
                        "verification_status", "unverified"
                    ),
                    "valid_from": str(memory.get("valid_from", ""))
                }
                for memory in farmer_memories
            ],
            "general_agricultural_memories": [
                {
                    "key": memory.get("key"),
                    "content": memory.get("content"),
                    "category": memory.get("category"),
                    "version": memory.get("version")
                }
                for memory in general_memories
            ]
        }

        memory_context_json = json.dumps(
            memory_context,
            indent=2,
            ensure_ascii=False
        )

        # 5. CONSTRUCT OLLAMA MESSAGES
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        messages.extend(previous_messages)

        current_prompt = f"""
CURRENT QUESTION:

{latest_question}


AGRICULTURAL NLP ANALYSIS:

{nlp_context}


RETRIEVED APPROVED MEMORIES:

{memory_context_json}


INSTRUCTIONS:

1. Answer the current question only.

2. Use extracted agricultural entities to understand
   the crop, disease, location and other details.

3. Use retrieved farmer-specific memories only when
   relevant to the current question.

4. Use general agricultural memories as supporting context.

5. Never mix information belonging to different farmers.

6. Treat stored farmer information as reported information,
   not independently verified facts.

7. If the latest user statement conflicts with an older
   memory, prioritize the latest statement.

8. Do not assume that historical farm conditions,
   measurements or symptoms are still current.

9. Do not blindly trust incorrect or incomplete NLP extraction.

10. Do not invent missing farmer information.

11. Ask relevant follow-up questions when necessary.

12. Provide practical and understandable agricultural guidance.

13. For chemical applications, pesticide doses and fungicide
    recommendations, avoid unsupported prescriptions.
    Encourage verification against official agricultural
    guidance and product labels.

14. If the user asks to recall stored farmer information,
    answer only the requested information.

15. Do not provide unsolicited fertilizer, pesticide,
    fungicide or disease-management recommendations
    during a memory-recall question.

16. Keep memory-recall answers concise and structured.

17. Clearly distinguish stored information from
    newly inferred information.

18. Do not claim that a stored measurement is current
    unless its date or latest status is established.
"""

        messages.append({
            "role": "user",
            "content": current_prompt
        })

        # 6. GENERATE RESPONSE USING OLLAMA
        response = ollama.chat(
            model=Config.OLLAMA_MODEL,
            messages=messages,
            options={
                "temperature": 0.2,
                "num_ctx": 4096
            }
        )

        answer_text = response["message"]["content"]
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not return_metrics:
            return answer_text

        return {
            "response": answer_text,
            "metrics": {
                "memory_mode": memory_mode,
                "latency_ms": elapsed_ms,
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
                "total_tokens": (
                    response.get("prompt_eval_count", 0)
                    + response.get("eval_count", 0)
                ),
                "retrieved_farmer_memories": len(farmer_memories),
                "retrieved_general_memories": len(general_memories),
                "history_turns_included": len(previous_messages)
            }
        }

    except ollama.ResponseError as e:
        raise RuntimeError(f"Ollama model error: {e.error}")

    except Exception as e:
        raise RuntimeError(
            f"Unable to generate agricultural response: {str(e)}"
        )
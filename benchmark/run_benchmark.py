import os
import sys
import json
from uuid import uuid4

# Allow imports from project root
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import (
    client,
    memories_collection,
    memory_proposals_collection,
    memory_versions_collection,
    memory_audit_collection
)
from services.agri_ner import extract_agricultural_entities
from services.llm_service import generate_response
from services.memory_service import (
    propose_memories_from_analysis,
    auto_commit_ungated_memories,
    approve_memory_proposal
)


MODES = ["stateless", "ungated_auto", "evomind_governed"]


def cleanup_owner_records(owner_id):
    """Remove synthetic benchmark records so production DB stays clean."""
    memories_collection.delete_many({"owner_id": owner_id})
    memory_proposals_collection.delete_many({"owner_id": owner_id})
    memory_versions_collection.delete_many({"owner_id": owner_id})
    memory_audit_collection.delete_many({"owner_id": owner_id})


def evaluate_response_rules(
    response_text,
    must_include,
    must_exclude,
    must_include_any=None
):
    """Check whether model output satisfies inclusion, synonym-group, and exclusion criteria."""
    text_lower = response_text.lower()
    must_include_any = must_include_any or []

    inc_hits = sum(1 for kw in must_include if kw.lower() in text_lower)
    inc_total = len(must_include)

    if must_include_any:
        any_hit = any(kw.lower() in text_lower for kw in must_include_any)
        inc_total += 1
        if any_hit:
            inc_hits += 1

    exc_violations = sum(1 for kw in must_exclude if kw.lower() in text_lower)
    exc_total = len(must_exclude)

    passed = (inc_hits == inc_total) and (exc_violations == 0)
    return {
        "passed": passed,
        "inc_hits": inc_hits,
        "inc_total": inc_total,
        "exc_violations": exc_violations,
        "exc_total": exc_total
    }


def run_single_case(case, mode):
    """Execute one multi-turn test case under a specified memory mode."""
    owner_id = f"bench_{mode}_{case['id']}_{uuid4().hex[:8]}"
    history = []

    # Stage 1: Candidate proposal screening counts
    prop_tp = 0
    prop_fp = 0
    prop_fn = 0

    # Gold keys expected to be committed to permanent storage (where approve_proposals is True)
    gold_committed_keys = set()

    turn_latencies = []
    turn_prompt_tokens = []
    turn_total_tokens = []

    final_eval = None

    try:
        for turn_idx, turn in enumerate(case["turns"]):
            user_msg = turn["user"]
            nlp_analysis = extract_agricultural_entities(user_msg)
            expected_keys = set(turn.get("expected_proposed_keys", []))

            if turn.get("approve_proposals", False):
                gold_committed_keys |= expected_keys

            # 1. Memory Ingestion Step by Mode
            if mode == "evomind_governed":
                proposals = propose_memories_from_analysis(
                    text=user_msg,
                    analysis=nlp_analysis,
                    owner_id=owner_id
                )
                proposed_keys = {
                    p["key"] for p in proposals if p.get("success")
                }

                prop_tp += len(proposed_keys & expected_keys)
                prop_fp += len(proposed_keys - expected_keys)
                prop_fn += len(expected_keys - proposed_keys)

                if turn.get("approve_proposals", False):
                    for p in proposals:
                        if p.get("success") and p.get("proposal_id"):
                            approve_memory_proposal(
                                proposal_id=p["proposal_id"],
                                reviewed_by="benchmark_oracle",
                                owner_id=owner_id
                            )

            elif mode == "ungated_auto":
                committed_keys = set(
                    auto_commit_ungated_memories(
                        text=user_msg,
                        analysis=nlp_analysis,
                        owner_id=owner_id
                    )
                )
                prop_tp += len(committed_keys & expected_keys)
                prop_fp += len(committed_keys - expected_keys)
                prop_fn += len(expected_keys - committed_keys)

            # 2. Construct history (simulate cross-session recall on final turn for stateful modes)
            if (
                mode in ("evomind_governed", "ungated_auto")
                and turn_idx == len(case["turns"]) - 1
            ):
                active_history = [{"role": "user", "content": user_msg}]
            else:
                history.append({"role": "user", "content": user_msg})
                active_history = list(history)

            # 3. Generate Response + Telemetry
            gen_out = generate_response(
                conversation_history=active_history,
                nlp_analysis=nlp_analysis,
                owner_id=owner_id,
                memory_mode=mode,
                return_metrics=True
            )

            answer = gen_out["response"]
            metrics = gen_out["metrics"]

            history.append({"role": "assistant", "content": answer})

            turn_latencies.append(metrics["latency_ms"])
            turn_prompt_tokens.append(metrics["prompt_tokens"])
            turn_total_tokens.append(metrics["total_tokens"])

            # 4. Evaluate final turn assertions
            if turn_idx == len(case["turns"]) - 1:
                final_eval = evaluate_response_rules(
                    response_text=answer,
                    must_include=turn.get("must_include", []),
                    must_exclude=turn.get("must_exclude", []),
                    must_include_any=turn.get("must_include_any", [])
                )

        # Stage 2: Inspect actual committed permanent memory collection
        committed_docs = list(memories_collection.find({"owner_id": owner_id}))
        actual_committed_keys = {doc["key"] for doc in committed_docs if "key" in doc}

        if mode == "stateless":
            comm_tp, comm_fp, comm_fn = 0, 0, len(gold_committed_keys)
        else:
            comm_tp = len(actual_committed_keys & gold_committed_keys)
            comm_fp = len(actual_committed_keys - gold_committed_keys)
            comm_fn = len(gold_committed_keys - actual_committed_keys)

        version_count = memory_versions_collection.count_documents({
            "owner_id": owner_id
        })

        return {
            "case_id": case["id"],
            "category": case["category"],
            "mode": mode,
            "passed": final_eval["passed"] if final_eval else False,
            "inc_hits": final_eval["inc_hits"] if final_eval else 0,
            "inc_total": final_eval["inc_total"] if final_eval else 0,
            "exc_violations": (
                final_eval["exc_violations"] if final_eval else 0
            ),
            "exc_total": final_eval["exc_total"] if final_eval else 0,
            "prop_tp": prop_tp,
            "prop_fp": prop_fp,
            "prop_fn": prop_fn,
            "comm_tp": comm_tp,
            "comm_fp": comm_fp,
            "comm_fn": comm_fn,
            "actual_committed_keys": sorted(list(actual_committed_keys)),
            "archived_versions": version_count,
            "avg_latency_ms": round(
                sum(turn_latencies) / len(turn_latencies), 2
            ),
            "avg_prompt_tokens": round(
                sum(turn_prompt_tokens) / len(turn_prompt_tokens), 1
            ),
            "avg_total_tokens": round(
                sum(turn_total_tokens) / len(turn_total_tokens), 1
            )
        }

    finally:
        cleanup_owner_records(owner_id)


def calc_prf(tp, fp, fn):
    precision = round((tp / (tp + fp)) * 100, 2) if (tp + fp) else 0.0
    recall = round((tp / (tp + fn)) * 100, 2) if (tp + fn) else 0.0
    f1 = (
        round((2 * precision * recall) / (precision + recall), 2)
        if (precision + recall) else 0.0
    )
    return precision, recall, f1


def main():
    client.admin.command("ping")

    dataset_path = os.path.join(
        os.path.dirname(__file__),
        "dataset_haryana_agri.json"
    )
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    all_results = []
    summary = {}

    for mode in MODES:
        print(f"\n=== Running Benchmark Mode: {mode} ===")
        mode_records = []

        for case in dataset:
            rec = run_single_case(case, mode)
            mode_records.append(rec)
            all_results.append(rec)
            status = "PASS" if rec["passed"] else "FAIL"
            print(
                f"  [{status}] {rec['case_id']} ({rec['category']}) | "
                f"Comm TP/FP/FN: {rec['comm_tp']}/{rec['comm_fp']}/{rec['comm_fn']} | "
                f"Latency: {rec['avg_latency_ms']} ms"
            )

        total_cases = len(mode_records)
        passed_cases = sum(1 for r in mode_records if r["passed"])

        poison_cases = [
            r for r in mode_records
            if r["category"] in ("poisoning_trap", "unapproved_isolation")
        ]
        poison_violations = sum(r["exc_violations"] for r in poison_cases)
        poison_checks = sum(r["exc_total"] for r in poison_cases)
        leakage_rate = (
            round((poison_violations / poison_checks) * 100, 2)
            if poison_checks else 0.0
        )
        cat_cd_committed_fp = sum(r["comm_fp"] for r in poison_cases)

        recall_cases = [
            r for r in mode_records
            if r["category"] in ("fact_recall", "temporal_update")
        ]
        recall_passed = sum(1 for r in recall_cases if r["passed"])
        recall_acc = (
            round((recall_passed / len(recall_cases)) * 100, 2)
            if recall_cases else 0.0
        )

        p_tp = sum(r["prop_tp"] for r in mode_records)
        p_fp = sum(r["prop_fp"] for r in mode_records)
        p_fn = sum(r["prop_fn"] for r in mode_records)
        prop_prec, prop_rec, prop_f1 = calc_prf(p_tp, p_fp, p_fn)

        c_tp = sum(r["comm_tp"] for r in mode_records)
        c_fp = sum(r["comm_fp"] for r in mode_records)
        c_fn = sum(r["comm_fn"] for r in mode_records)
        comm_prec, comm_rec, comm_f1 = calc_prf(c_tp, c_fp, c_fn)

        summary[mode] = {
            "overall_pass_rate_pct": round((passed_cases / total_cases) * 100, 2),
            "recall_and_conflict_acc_pct": recall_acc,
            "response_lexical_leakage_pct": leakage_rate,
            "cat_cd_unauthorized_commits": None if mode == "stateless" else cat_cd_committed_fp,
            "proposal_precision_pct": None if mode == "stateless" else prop_prec,
            "proposal_recall_pct": prop_rec,
            "proposal_f1_pct": prop_f1,
            "committed_write_precision_pct": None if mode == "stateless" else comm_prec,
            "committed_write_recall_pct": comm_rec,
            "committed_write_f1_pct": comm_f1,
            "committed_counts": {"tp": c_tp, "fp": c_fp, "fn": c_fn},
            "proposal_counts": {"tp": p_tp, "fp": p_fp, "fn": p_fn},
            "archived_versions": sum(r["archived_versions"] for r in mode_records),
            "mean_latency_ms": round(
                sum(r["avg_latency_ms"] for r in mode_records) / total_cases, 2
            ),
            "mean_prompt_tokens": round(
                sum(r["avg_prompt_tokens"] for r in mode_records) / total_cases, 1
            ),
            "mean_total_tokens": round(
                sum(r["avg_total_tokens"] for r in mode_records) / total_cases, 1
            )
        }

    out_json = os.path.join(os.path.dirname(__file__), "results_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": summary, "detailed_runs": all_results},
            f,
            indent=2
        )

    print("\nBenchmark complete! Saved updated results_summary.json")


if __name__ == "__main__":
    main()
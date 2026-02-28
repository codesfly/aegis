#!/usr/bin/env python3
"""
AEGIS-1 minimal reference orchestrator (example only).
- Controller-driven fast path state machine
- Fail-fast
- Produces tool_summary + output artifacts
- Runs built-in verifier before final success
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REQUIRED_LANES = ["grok_scout", "gemini_scout", "qwen_scout", "grok_fusion"]
UNCONFIGURED_ALIASES = ["豆包", "Doubao", "doubao"]


class ErrorCode:
    NONE = "NONE"
    ERROR_MISSING_TOOL_CALL = "ERROR_MISSING_TOOL_CALL"
    ERROR_MODEL_MISMATCH = "ERROR_MODEL_MISMATCH"
    ERROR_UNCONFIGURED_MODEL_CLAIM = "ERROR_UNCONFIGURED_MODEL_CLAIM"
    ERROR_SCOUT_TIMEOUT = "ERROR_SCOUT_TIMEOUT"
    ERROR_UPSTREAM_FETCH_FAILED = "ERROR_UPSTREAM_FETCH_FAILED"
    ERROR_GUARDRAIL_REJECTED = "ERROR_GUARDRAIL_REJECTED"


LANE_MODELS = {
    "grok_scout": "grok/grok-4.1-thinking",
    "gemini_scout": "cpa/gemini-3-flash",
    "qwen_scout": "bailian/qwen3.5-plus",
    "grok_fusion": "grok/grok-4.1-thinking",
}


@dataclass
class LaneRun:
    lane: str
    tool_call_id: str
    run_id: str
    requested_model: str
    actual_model: str
    status: str  # ok|error
    error_code: str
    duration_ms: int


class MockExecutor:
    """Reference executor; replace with live tool adapter in production."""

    def __init__(self, fail_lane: Optional[str] = None):
        self.fail_lane = fail_lane

    def run_lane(self, lane: str) -> LaneRun:
        start = time.time()
        requested = LANE_MODELS[lane]
        actual = requested

        if lane == self.fail_lane:
            return LaneRun(
                lane=lane,
                tool_call_id=f"call_{uuid.uuid4().hex[:10]}",
                run_id=f"run_{uuid.uuid4().hex}",
                requested_model=requested,
                actual_model=actual,
                status="error",
                error_code=ErrorCode.ERROR_UPSTREAM_FETCH_FAILED,
                duration_ms=int((time.time() - start) * 1000),
            )

        return LaneRun(
            lane=lane,
            tool_call_id=f"call_{uuid.uuid4().hex[:10]}",
            run_id=f"run_{uuid.uuid4().hex}",
            requested_model=requested,
            actual_model=actual,
            status="ok",
            error_code=ErrorCode.NONE,
            duration_ms=int((time.time() - start) * 1000),
        )


def verify(tool_summary: Dict, output: Dict, claim_text: str = "") -> (bool, str, Dict):
    lane_map = {x["lane"]: x for x in tool_summary.get("lanes", [])}

    for lane in REQUIRED_LANES:
        row = lane_map.get(lane)
        if not row or not row.get("tool_call_id") or not row.get("run_id"):
            return False, ErrorCode.ERROR_MISSING_TOOL_CALL, {"missing_lane": lane}
        if row.get("requested_model") != row.get("actual_model"):
            return False, ErrorCode.ERROR_MODEL_MISMATCH, {
                "lane": lane,
                "requested_model": row.get("requested_model"),
                "actual_model": row.get("actual_model"),
            }

    for bad in UNCONFIGURED_ALIASES:
        if bad in claim_text:
            return False, ErrorCode.ERROR_UNCONFIGURED_MODEL_CLAIM, {"alias": bad}

    for lane in REQUIRED_LANES:
        if lane not in output.get("model_trace", {}):
            return False, ErrorCode.ERROR_GUARDRAIL_REJECTED, {"missing_model_trace": lane}

    return True, ErrorCode.NONE, {}


def build_output(query: str, runs: List[LaneRun], ok: bool, error_code: str, details: Dict) -> Dict:
    lane_by = {r.lane: r for r in runs}

    model_trace = {k: lane_by[k].run_id for k in lane_by}
    model_lock = {
        k: {
            "requested_model": lane_by[k].requested_model,
            "actual_model": lane_by[k].actual_model,
        }
        for k in lane_by
    }
    lane_error = {
        k: ("none" if lane_by[k].status == "ok" else lane_by[k].error_code)
        for k in lane_by
    }

    return {
        "query": query,
        "status": "success" if ok else "error",
        "error_code": error_code,
        "error_details": details,
        "model_trace": model_trace,
        "model_lock": model_lock,
        "lane_error": lane_error,
        "confidence": 85 if ok else 0,
        "source_mix": {
            "authority": ["https://docs.example.org"],
            "realtime": ["https://x.com/example"],
            "aggregator": ["https://news.example.com"],
        },
        "conflict_points": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def orchestrate(query: str, fail_lane: Optional[str] = None) -> Dict:
    executor = MockExecutor(fail_lane=fail_lane)
    runs: List[LaneRun] = []

    # Controller state machine (fail-fast)
    for lane in REQUIRED_LANES:
        r = executor.run_lane(lane)
        runs.append(r)
        if r.status != "ok":
            break

    summary = {
        "query": query,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "lanes": [asdict(x) for x in runs],
    }

    preliminary = build_output(query, runs, ok=False, error_code=ErrorCode.ERROR_GUARDRAIL_REJECTED, details={"phase": "precheck"})
    ok, code, details = verify(summary, preliminary)
    final = build_output(query, runs, ok=ok, error_code=code, details=details)
    return {"tool_summary": summary, "output": final}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--fail-lane", default=None, choices=[None] + REQUIRED_LANES)
    ap.add_argument("--out-dir", default="examples/artifacts")
    args = ap.parse_args()

    bundle = orchestrate(args.query, args.fail_lane)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "tool_summary.json").write_text(json.dumps(bundle["tool_summary"], ensure_ascii=False, indent=2))
    (out_dir / "output.json").write_text(json.dumps(bundle["output"], ensure_ascii=False, indent=2))

    print(f"written: {out_dir / 'tool_summary.json'}")
    print(f"written: {out_dir / 'output.json'}")
    print(f"status={bundle['output']['status']} error_code={bundle['output']['error_code']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

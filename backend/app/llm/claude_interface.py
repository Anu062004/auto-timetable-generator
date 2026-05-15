"""LLM Interface (Layer 1).

Supports two providers:
- AWS Bedrock (default) — uses your AWS CLI credentials, region from
  AWS_REGION / AWS_DEFAULT_REGION (falls back to ap-southeast-2).
- Anthropic direct API — used when ANTHROPIC_API_KEY is set.

Translates natural language into a strict TimetableRequest and explains
solver results in plain English. Uses prompt caching for the (large,
repeated) schema/system prompt.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from ..models.domain import (
    PreflightReport,
    Timetable,
    TimetableRequest,
    VerificationReport,
)


SYSTEM_PROMPT = """You are a scheduling assistant for a college timetable generator.

OUTPUT — strict JSON, no markdown, no prose outside JSON. One object only.

Top-level keys:
  action:  "patch" | "ask" | "explain"
  message: short human summary (1-2 sentences) of what you're doing
  ops:     present only when action == "patch" — a list of edit operations

Pick "patch" for any change to the timetable (faculty leave, locking a course,
moving an elective, etc.). Pick "ask" only if the user's request is too vague
to translate into operations. Pick "explain" only when the user is asking
about the current schedule rather than changing it.

{ops_help}

Reference context — the current timetable already exists with these courses,
faculty and sections. Use partial-name matching ("Sampath", "AI Lab",
"section A") — you do NOT need to invent IDs. Days are MON/TUE/WED/THU/FRI/SAT.
Slots are 1..7 (slot 1 = 8:30, slot 7 = 15:15-16:10). Tea break is after slot
2, lunch after slot 4.

Example user → assistant exchanges:

  User: "Dr Sampath is on leave Wednesdays"
  Assistant: {{"action":"patch","message":"Marked Dr Sampath unavailable all day Wednesday.","ops":[{{"op":"faculty_unavailable","faculty":"Sampath","day":"WED","slots":[1,2,3,4,5,6,7]}}]}}

  User: "Move the elective to MON-2, WED-3, FRI-3, FRI-4"
  Assistant: {{"action":"patch","message":"Reassigning the elective block to those four slots.","ops":[{{"op":"set_elective_slots","slots":[{{"day":"MON","slot":2}},{{"day":"WED","slot":3}},{{"day":"FRI","slot":3}},{{"day":"FRI","slot":4}}]}}]}}

  User: "What does sec A look like on Friday?"
  Assistant: {{"action":"explain","message":"(brief answer about Friday)"}}
"""


# Groq (OpenAI-compatible, very fast) — preferred when GROQ_API_KEY is set.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Preferred Bedrock model IDs (Anthropic Claude) — strongest first.
DEFAULT_BEDROCK_MODEL = "global.anthropic.claude-opus-4-5-20251101-v1:0"
DEFAULT_BEDROCK_FALLBACK_MODELS = [
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "apac.anthropic.claude-sonnet-4-20250514-v1:0",
    "au.anthropic.claude-haiku-4-5-20251001-v1:0",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
]
# Amazon Nova fallback — works without the Anthropic use-case form.
NOVA_FALLBACK_MODELS = [
    "amazon.nova-pro-v1:0",
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
]
DEFAULT_DIRECT_MODEL = "claude-opus-4-7"

ACCESS_ERROR_TOKENS = (
    "403",
    "404",
    "not available",
    "Throttling",
    "AccessDenied",
    "submitted",
    "use case",
    "isn",
    "Legacy",
)


def _schema_blob() -> str:
    return json.dumps(TimetableRequest.model_json_schema(), indent=2)


def _summarise_request(req: TimetableRequest) -> str:
    """Compact one-page summary of the current request for the LLM context.

    Replaces dumping the full ~20k-token JSON. Free-tier LLMs choke on the
    full payload; this gives them just enough to translate user requests.
    """
    lines: list[str] = []
    lines.append(f"Sections: {', '.join(s.id for s in req.sections)}")
    lines.append("Courses:")
    for c in req.courses:
        lock = ""
        if c.locked_day and c.locked_slots:
            lock = f" [locked {c.locked_day} {c.locked_slots}]"
        pair = f" pairs={c.pair_course}" if c.pair_course else ""
        lines.append(f"  - {c.code} \"{c.name}\" ({c.type.value}, {c.credits}cr){pair}{lock}")
    for b in req.elective_blocks:
        lines.append(
            f"Elective {b.id} \"{b.name}\": {b.weekly_slot_count} slots, "
            f"locked={b.locked_global_slots}, options={[o.course_code for o in b.options]}"
        )
    lines.append("Faculty (name → courses):")
    for f in req.faculty[:120]:
        codes = sorted({a.course_code for a in f.assignments})
        if not codes:
            continue
        lines.append(f"  - {f.name}: {', '.join(codes)}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> dict:
    """Extract the first complete JSON object from a possibly noisy LLM reply.

    Handles markdown code fences (```json ... ```), prose preambles, and
    trailing text. Falls back to {"action": "ask", "message": text} when no
    parseable object is found.
    """
    if not text:
        return {"action": "ask", "message": ""}
    # Strip markdown fences.
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove first fence line and last fence (if any).
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
    # Try a direct parse first.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Bracket-balance scan: find the first '{' and walk to its matching '}'.
    depth = 0
    start = -1
    in_str = False
    escape = False
    for i, ch in enumerate(stripped):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    start = -1
                    continue
    return {"action": "ask", "message": text}


class ClaudeInterface:
    """Backend-agnostic Claude wrapper.

    Provider is selected as follows:
    - If `provider` is passed explicitly, use that ("bedrock" | "anthropic").
    - Else if ANTHROPIC_API_KEY env var is set, use the direct API.
    - Else default to Bedrock (uses ambient AWS CLI credentials).
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        aws_region: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("anthropic SDK not installed") from e
        self._anthropic = anthropic

        if provider is None:
            if os.environ.get("GROQ_API_KEY"):
                provider = "groq"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            else:
                provider = "bedrock"
        provider = provider.lower()
        self.provider = provider
        self.active_model: Optional[str] = None

        if provider == "groq":
            try:
                from openai import OpenAI
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("openai SDK not installed (needed for Groq)") from e
            key = api_key or os.environ.get("GROQ_API_KEY")
            if not key:
                raise RuntimeError("GROQ_API_KEY not set")
            self.client = OpenAI(api_key=key, base_url=GROQ_BASE_URL)
            self.model = model or DEFAULT_GROQ_MODEL
            # Build a boto3 Nova client too so we can fall back if Groq throttles.
            region = (
                aws_region
                or os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION")
                or "ap-southeast-2"
            )
            self.region = region
            try:
                import boto3
                self._nova_client = boto3.client("bedrock-runtime", region_name=region)
            except Exception:
                self._nova_client = None
        elif provider == "anthropic":
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self.client = anthropic.Anthropic(api_key=key)
            self.model = model or DEFAULT_DIRECT_MODEL
        elif provider == "bedrock":
            region = (
                aws_region
                or os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION")
                or "ap-southeast-2"
            )
            self.region = region
            # AnthropicBedrock — Claude over Bedrock (preferred when accessible).
            self.client = anthropic.AnthropicBedrock(aws_region=region)
            self.model = model or DEFAULT_BEDROCK_MODEL
            # boto3 bedrock-runtime client for Amazon Nova fallback.
            try:
                import boto3
                self._nova_client = boto3.client("bedrock-runtime", region_name=region)
            except Exception:
                self._nova_client = None
        else:
            raise ValueError(f"unknown provider {provider}")

        # Cache the system prompt. We no longer embed the full JSON schema —
        # the patch-ops help is short and the LLM uses partial-name matching
        # instead of needing the full request to find IDs.
        from .patch_ops import OPS_HELP
        self._system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT.format(ops_help=OPS_HELP),
                "cache_control": {"type": "ephemeral"},
            },
        ]

    # ------------------------------------------------------------------
    def _claude_models_to_try(self) -> list[str]:
        if self.provider != "bedrock":
            return [self.model]
        return [self.model, *[m for m in DEFAULT_BEDROCK_FALLBACK_MODELS if m != self.model]]

    def _shape_anthropic_resp(self, resp) -> str:
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def _call_nova(
        self,
        *,
        max_tokens: int,
        system: Optional[list],
        messages: list,
    ) -> str:
        """Invoke Amazon Nova via boto3.bedrock-runtime.converse.

        Returns the assistant text. Raises if all Nova models fail too.
        """
        if not self._nova_client:
            raise RuntimeError("boto3 bedrock-runtime client not available")

        # Translate Anthropic-style payload to Nova converse format.
        nova_system = []
        if system:
            for blk in system:
                if isinstance(blk, dict) and "text" in blk:
                    nova_system.append({"text": blk["text"]})
                elif isinstance(blk, str):
                    nova_system.append({"text": blk})
        nova_messages = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                nova_messages.append({"role": m["role"], "content": [{"text": content}]})
            elif isinstance(content, list):
                # Pass through {text: ...} blocks.
                parts = []
                for c in content:
                    if isinstance(c, dict) and "text" in c:
                        parts.append({"text": c["text"]})
                    elif isinstance(c, str):
                        parts.append({"text": c})
                nova_messages.append({"role": m["role"], "content": parts})

        last_err: Optional[Exception] = None
        for mid in NOVA_FALLBACK_MODELS:
            try:
                kw = dict(
                    modelId=mid,
                    messages=nova_messages,
                    inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
                )
                if nova_system:
                    kw["system"] = nova_system
                resp = self._nova_client.converse(**kw)
                self.active_model = mid
                return resp["output"]["message"]["content"][0]["text"]
            except Exception as e:  # pragma: no cover
                msg = str(e)
                if any(tok in msg for tok in ACCESS_ERROR_TOKENS):
                    last_err = e
                    continue
                raise
        raise last_err or RuntimeError("no Nova model could be invoked")

    def _call_groq(
        self,
        *,
        max_tokens: int,
        system: Optional[list],
        messages: list,
    ) -> str:
        """Invoke Groq's OpenAI-compatible /chat/completions endpoint.

        Converts Anthropic-style system blocks + messages into OpenAI's
        single system message + messages format. Falls through Groq's own
        model chain on per-model errors.
        """
        sys_text = ""
        if system:
            for blk in system:
                if isinstance(blk, dict) and "text" in blk:
                    sys_text += blk["text"]
                elif isinstance(blk, str):
                    sys_text += blk
        oai_messages = []
        if sys_text:
            oai_messages.append({"role": "system", "content": sys_text})
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                content = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            oai_messages.append({"role": m["role"], "content": content})

        last_err: Optional[Exception] = None
        for mid in [self.model, *[m for m in GROQ_FALLBACK_MODELS if m != self.model]]:
            try:
                resp = self.client.chat.completions.create(
                    model=mid,
                    messages=oai_messages,
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
                self.active_model = f"groq:{mid}"
                return resp.choices[0].message.content or ""
            except Exception as e:
                msg = str(e)
                if any(tok in msg for tok in ACCESS_ERROR_TOKENS) or "rate" in msg.lower():
                    last_err = e
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("no Groq model could be invoked")

    def _create_text(
        self,
        *,
        max_tokens: int,
        system: Optional[list],
        messages: list,
    ) -> str:
        """Try the configured provider; fall back transparently when blocked.

        Order: Groq → (if Groq configured) Nova → Claude (direct or Bedrock)
               Bedrock provider: Claude → Nova
        """
        if self.provider == "groq":
            try:
                return self._call_groq(
                    max_tokens=max_tokens, system=system, messages=messages
                )
            except Exception as e:
                # Fall back to Nova so the chat keeps working on Groq outages.
                try:
                    return self._call_nova(
                        max_tokens=max_tokens, system=system, messages=messages
                    )
                except Exception:
                    raise e

        last_err: Optional[Exception] = None
        if self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            self.active_model = self.model
            return self._shape_anthropic_resp(resp)

        # Provider = bedrock. Try Claude variants first.
        for mid in self._claude_models_to_try():
            try:
                resp = self.client.messages.create(
                    model=mid,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                )
                self.active_model = mid
                return self._shape_anthropic_resp(resp)
            except Exception as e:
                msg = str(e)
                if any(tok in msg for tok in ACCESS_ERROR_TOKENS):
                    last_err = e
                    continue
                raise

        # Fall back to Amazon Nova so the LLM endpoint stays usable while the
        # Anthropic use-case form is pending.
        try:
            return self._call_nova(
                max_tokens=max_tokens, system=system, messages=messages
            )
        except Exception as e:
            # Surface the original Claude error if Nova also can't help.
            if last_err:
                raise last_err
            raise e

    def _call(self, user_text: str, context: Optional[str] = None) -> dict:
        messages = []
        if context:
            messages.append({"role": "user", "content": f"Context (read-only):\n{context}"})
            messages.append({"role": "assistant", "content": "Understood, awaiting your request."})
        messages.append({"role": "user", "content": user_text})

        text = self._create_text(
            max_tokens=8192,
            system=self._system_blocks,
            messages=messages,
        )
        return _extract_json_object(text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(self, user_text: str, hint_request: Optional[TimetableRequest] = None) -> dict:
        ctx = None
        if hint_request:
            ctx = (
                "CURRENT TIMETABLE (read-only summary, use partial-name matching):\n"
                + _summarise_request(hint_request)
            )
        return self._call(user_text, context=ctx)

    def explain(
        self,
        req: TimetableRequest,
        tt: Timetable,
        verify: VerificationReport,
        preflight: Optional[PreflightReport] = None,
    ) -> str:
        ctx_obj = {
            "preflight": preflight.model_dump() if preflight else None,
            "timetable_status": tt.status,
            "cost": tt.cost,
            "solve_time_sec": tt.solve_time_sec,
            "violations": [v.model_dump() for v in verify.violations],
            "soft_score": verify.soft_score,
            "notes": tt.notes,
            "class_count": len(tt.classes),
        }
        prompt = (
            "Summarise the solver result for a non-technical user. "
            "If it's infeasible, identify the most likely conflict and suggest one concrete fix. "
            "Reply with a short paragraph (3-5 sentences), not JSON.\n\n"
            + json.dumps(ctx_obj, indent=2)
        )
        return self._create_text(
            max_tokens=600,
            system=self._system_blocks,
            messages=[{"role": "user", "content": prompt}],
        )

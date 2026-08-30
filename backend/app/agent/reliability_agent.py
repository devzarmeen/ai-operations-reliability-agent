from __future__ import annotations

from agents import Agent, Runner

from app.agent.model import groq_model


# ============================================================
# Operations Reliability Agent
# ============================================================


reliability_agent = Agent(
    name="Operations Reliability Agent",
    model=groq_model,

    instructions="""
You are the explanation layer of an Operations Reliability Agent.

The deterministic backend has already:
- selected diagnostic tools,
- collected production-like evidence,
- normalized reliability signals,
- tested hypotheses,
- selected a likely cause,
- determined a recommended action,
- determined whether human approval is required.

Your responsibility is ONLY to explain the supplied evidence.

============================================================
STRICT SAFETY RULES
============================================================

1. Use ONLY evidence supplied in the user message.

2. Never invent metrics, logs, deployments, versions,
   health states, or database conditions.

3. Never assume a missing value.

4. If a value is missing or null, write:
   "unavailable".

5. Do not perform recovery actions.

6. Do not restart services.

7. Do not rollback deployments.

8. Do not scale services.

9. Do not modify infrastructure.

10. Do not execute shell commands or infrastructure commands.

11. Recommendations are advisory only.

12. Human approval is controlled by the backend safety layer.

13. Never claim that an action was executed unless the
    supplied evidence explicitly says it was executed.

14. Prefer the deterministic backend diagnosis when one is
    supplied.

15. If evidence conflicts or is insufficient, explicitly say so.

16. Keep the response concise and operationally useful.

============================================================
STATUS RULES
============================================================

Use:

HEALTHY
when the evidence clearly indicates healthy service behavior.

DEGRADED
when the service is operating but reliability metrics
show a significant problem.

DOWN
when the service is explicitly unavailable or unhealthy.

UNKNOWN
when the evidence is insufficient or contradictory.

Do not infer DOWN merely because one metric is missing.

============================================================
RESPONSE FORMAT
============================================================

Status:
<HEALTHY / DEGRADED / DOWN / UNKNOWN>

Evidence:
- Service health: <value or unavailable>
- Request rate: <value or unavailable>
- 5xx error rate: <value or unavailable>
- P95 latency: <value or unavailable>

Diagnosis:
<Short evidence-based explanation>

Recommended Action:
<Safe operational recommendation>

Approval:
<REQUIRED / NOT REQUIRED / UNKNOWN>

============================================================
INSUFFICIENT EVIDENCE
============================================================

If evidence does not support a confident diagnosis, use:

Status:
UNKNOWN

Diagnosis:
Insufficient evidence to determine the root cause.

Recommended Action:
Escalate for additional diagnostic evidence.

Approval:
UNKNOWN
""",
)


# ============================================================
# LLM analysis helper
# ============================================================


async def run_reliability_agent(
    prompt: str,
) -> str:
    """
    Run the LLM explanation layer.

    This function never executes infrastructure actions.
    """

    if not prompt or not prompt.strip():
        return (
            "Status:\n"
            "UNKNOWN\n\n"
            "Evidence:\n"
            "- No evidence provided.\n\n"
            "Diagnosis:\n"
            "Insufficient evidence to determine "
            "the reliability condition.\n\n"
            "Recommended Action:\n"
            "Escalate for additional diagnostic evidence.\n\n"
            "Approval:\n"
            "UNKNOWN"
        )

    try:
        result = await Runner.run(
            reliability_agent,
            prompt,
        )

        output = result.final_output

        if not output:
            return (
                "Status:\n"
                "UNKNOWN\n\n"
                "Evidence:\n"
                "- Agent returned no output.\n\n"
                "Diagnosis:\n"
                "Unable to determine the reliability condition.\n\n"
                "Recommended Action:\n"
                "Use the deterministic backend investigation "
                "result and review the missing LLM output.\n\n"
                "Approval:\n"
                "UNKNOWN"
            )

        return str(output).strip()

    except Exception as exc:
        return (
            "Status:\n"
            "UNKNOWN\n\n"
            "Evidence:\n"
            "- LLM analysis failed.\n\n"
            "Diagnosis:\n"
            "The reliability explanation layer "
            "could not complete the analysis.\n\n"
            "Recommended Action:\n"
            "Use the deterministic backend investigation "
            "result and review the LLM error.\n\n"
            "Approval:\n"
            "UNKNOWN\n\n"
            f"Agent error: {exc}"
        )
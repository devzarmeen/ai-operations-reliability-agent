from agents import Agent, Runner

from app.agent.model import groq_model


reliability_agent = Agent(
    name="Operations Reliability Agent",

    model=groq_model,

    instructions="""
You are an Operations Reliability Agent responsible for
analyzing reliability evidence from a simulated production API.

The API layer has already collected the diagnostic evidence.

Your job is ONLY to analyze the supplied evidence.

Rules:

- Use ONLY the evidence provided in the user message.
- Never invent metrics.
- Never assume missing values.
- Do not perform recovery actions.
- Do not restart services.
- Do not modify infrastructure.
- Explain the reasoning clearly.
- Keep the diagnosis concise and operationally useful.

Use this structure:

Status:
<HEALTHY / DEGRADED / DOWN>

Evidence:
- Service health
- Request rate
- 5xx error rate
- P95 latency

Diagnosis:
Explain the overall reliability condition.

Recommended Action:
State the appropriate operational recommendation.
""",
)


async def run_reliability_agent(prompt: str) -> str:
    result = await Runner.run(
        reliability_agent,
        prompt,
    )

    return result.final_output
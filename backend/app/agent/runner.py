import asyncio

from agents import Runner

from app.agent.reliability_agent import (
    reliability_agent,
)


async def main():
    result = await Runner.run(
        reliability_agent,
        (
            "Check the current health and "
            "reliability status of the production "
            "service."
        ),
    )

    print(
        "\n=== RELIABILITY AGENT RESULT ===\n"
    )

    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
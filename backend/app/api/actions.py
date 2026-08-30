from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(
    prefix="/api/actions",
    tags=["Actions"],
)


class ExecuteBody(BaseModel):
    action_type: str
    investigation_id: int | None = None
    approval_id: int | None = None


@router.post("/execute")
async def execute_action(
    body: ExecuteBody,
):
    """
    Direct high-impact execution is blocked.

    High-impact actions must pass through the
    investigation approval workflow.
    """

    raise HTTPException(
        status_code=403,
        detail=(
            "High-impact actions are blocked. "
            "Use an investigation approval "
            f"({body.action_type}) after explicit "
            "human approval."
        ),
    )
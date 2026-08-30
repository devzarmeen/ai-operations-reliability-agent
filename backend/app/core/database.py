from sqlmodel import SQLModel, create_engine

from app.core.config import settings
from app.models.alert import AlertRecord
from app.models.incident import Incident
from app.models.investigation import (
    ApprovalRequest,
    Investigation,
    InvestigationEvent,
    RecoveryVerification,
)

# Imported so SQLModel.metadata.create_all() registers the new tables
# without altering the existing incidents table.
_ = (
    AlertRecord,
    Incident,
    ApprovalRequest,
    Investigation,
    InvestigationEvent,
    RecoveryVerification,
)

engine = create_engine(
    settings.database_url,
    echo=False,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)

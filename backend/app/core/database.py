from sqlmodel import SQLModel, create_engine

from app.core.config import settings
from app.models.incident import Incident


engine = create_engine(
    settings.database_url,
    echo=False,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
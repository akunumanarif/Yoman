from sqlmodel import SQLModel, Session, create_engine

from config import settings

DATABASE_URL = f"sqlite:///{settings.db_path}"

engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

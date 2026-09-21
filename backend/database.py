from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

from demo_config import DEMO_MODE

load_dotenv()

Base = declarative_base()

if DEMO_MODE:
    # Portfolio Demo Mode runs against one self-contained in-memory SQLite
    # database, seeded at startup by demo_data.seed(). Neither Postgres nor
    # ERPNext is contacted, so the app starts with no credentials at all.
    # StaticPool keeps every session on the same connection -- an in-memory
    # database vanishes as soon as its last connection closes.
    import uuid

    from sqlalchemy import event
    from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.sql.elements import Extract

    DATABASE_URL = "sqlite://"
    READONLY_DATABASE_URL = DATABASE_URL

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_as_sqlite_json(type_, compiler, **kw):
        # The chat/daily-summary tables declare Postgres JSONB columns;
        # SQLite's JSON type is a drop-in for them through SQLAlchemy.
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def _compile_uuid_as_char(type_, compiler, **kw):
        return "CHAR(36)"

    @compiles(Extract, "sqlite")
    def _compile_extract_sqlite(element, compiler, **kw):
        # Postgres `extract('isodow', ...)` is 1=Monday..7=Sunday.
        # SQLite's default extract compiler has no isodow mapping.
        field = (element.field or "").lower()
        if field == "isodow":
            expr = compiler.process(element.expr, **kw)
            return f"((CAST(strftime('%w', {expr}) AS INTEGER) + 6) % 7 + 1)"
        return compiler.visit_extract(element, **kw)

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_sqlite_functions(dbapi_connection, _connection_record):
        # Those same tables use gen_random_uuid() as a server default.
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))

    # There is no privilege split to enforce over fictional data, so the
    # read-only session factory points at the same database.
    readonly_engine = engine
else:
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)

    READONLY_DATABASE_URL = os.getenv("DATABASE_URL_READONLY")
    readonly_engine = create_engine(READONLY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)


def get_readonly_db():
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

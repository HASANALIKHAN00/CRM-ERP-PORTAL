"""
Compares SQLAlchemy models.py against the real Postgres schema and
reports any column that exists in the database but is missing from
the corresponding model class.
"""
import re
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
inspector = inspect(engine)

# Map each SQLAlchemy model class to its real table name
import models
model_classes = {
    cls.__tablename__: cls
    for cls in models.Base.registry.mappers
    for cls in [cls.class_]
}

print(f"{'Table':<30} {'Missing column in models.py'}")
print("-" * 65)

found_any = False
for table_name in inspector.get_table_names():
    if table_name not in model_classes:
        print(f"{table_name:<30} (entire table not modeled in Python at all)")
        found_any = True
        continue

    model_cls = model_classes[table_name]
    model_columns = {c.name for c in model_cls.__table__.columns}
    db_columns = {c["name"] for c in inspector.get_columns(table_name)}

    missing = db_columns - model_columns
    for col in sorted(missing):
        print(f"{table_name:<30} {col}")
        found_any = True

if not found_any:
    print("None \u2014 models.py matches the real schema exactly.")
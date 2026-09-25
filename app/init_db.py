from pathlib import Path

from app.db import Base, get_engine


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    with engine.begin() as connection:
        for statement in [part.strip() for part in sql.split(";") if part.strip()]:
            connection.exec_driver_sql(statement)


if __name__ == "__main__":
    main()

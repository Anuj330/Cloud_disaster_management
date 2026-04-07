import os
import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def main() -> int:
    db_url = os.getenv(
        "DATABASE_URL",
        (
            f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'druser')}:{os.getenv('POSTGRES_PASSWORD', 'drpass')}@"
            f"{os.getenv('POSTGRES_HOST', 'postgres')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'drdb')}"
        ),
    )

    max_retries = int(os.getenv("DB_WAIT_MAX_RETRIES", "30"))
    sleep_seconds = float(os.getenv("DB_WAIT_INTERVAL_SECONDS", "2"))

    engine = create_engine(db_url)
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database is reachable")
            return 0
        except SQLAlchemyError as exc:
            print(f"Waiting for DB ({attempt}/{max_retries}): {exc}")
            time.sleep(sleep_seconds)

    print("Database not reachable after retries", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

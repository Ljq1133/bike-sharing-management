import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_active_jti_column():
    """Ensure the `active_jti` column exists on `users` table. Runs a safe ALTER TABLE when needed."""
    dialect = engine.dialect.name
    with engine.connect() as conn:
        if dialect == 'postgresql':
            # users.active_jti
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='active_jti'"))
            if res.first() is None:
                conn.execute(text('ALTER TABLE users ADD COLUMN active_jti VARCHAR;'))
            # bikes.rating
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='bikes' AND column_name='rating'"))
            if res.first() is None:
                conn.execute(text('ALTER TABLE bikes ADD COLUMN rating DOUBLE PRECISION DEFAULT 0.0;'))
            # rentals.rating
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='rentals' AND column_name='rating'"))
            if res.first() is None:
                conn.execute(text('ALTER TABLE rentals ADD COLUMN rating INTEGER;'))
        else:
            # sqlite and others: try add column if not exists (sqlite supports ADD COLUMN only)
            try:
                # users
                res = conn.execute(text("PRAGMA table_info('users')"))
                cols = [row[1] for row in res.fetchall()]
                if 'active_jti' not in cols:
                    conn.execute(text('ALTER TABLE users ADD COLUMN active_jti VARCHAR;'))
                # bikes
                res = conn.execute(text("PRAGMA table_info('bikes')"))
                cols = [row[1] for row in res.fetchall()]
                if 'rating' not in cols:
                    conn.execute(text('ALTER TABLE bikes ADD COLUMN rating FLOAT DEFAULT 0.0;'))
                # rentals
                res = conn.execute(text("PRAGMA table_info('rentals')"))
                cols = [row[1] for row in res.fetchall()]
                if 'rating' not in cols:
                    conn.execute(text('ALTER TABLE rentals ADD COLUMN rating INTEGER;'))
            except Exception:
                # best-effort, ignore
                pass

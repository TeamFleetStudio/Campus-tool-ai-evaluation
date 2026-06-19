import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Round(Base):
    __tablename__ = "rounds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    rubric_version = Column(String, default="v1")
    assignment_strategy = Column(String, default="random")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    problems = relationship("Problem", back_populates="round", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="round", cascade="all, delete-orphan")


class Problem(Base):
    __tablename__ = "problems"

    id = Column(String, primary_key=True)
    round_id = Column(String, ForeignKey("rounds.id"), nullable=False)
    title = Column(String, nullable=False)
    difficulty = Column(String, default="intermediate")
    problem_statement = Column(Text, nullable=False)
    approx_tokens = Column(Float, nullable=True)
    problem_type = Column(String, default="prompt_only")
    acceptance_criteria = Column(Text, nullable=True)

    round = relationship("Round", back_populates="problems")
    assignments = relationship("Assignment", back_populates="problem")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("round_id", "participant_id", name="uq_round_participant"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    round_id = Column(String, ForeignKey("rounds.id"), nullable=False)
    participant_id = Column(String, nullable=False)
    problem_id = Column(String, ForeignKey("problems.id"), nullable=False)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    round = relationship("Round", back_populates="assignments")
    problem = relationship("Problem", back_populates="assignments")
    evaluations = relationship("Evaluation", back_populates="assignment", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String, ForeignKey("assignments.id"), nullable=True)
    round_id = Column(String, nullable=True)
    participant_id = Column(String, nullable=True)
    problem_id = Column(String, nullable=True)
    problem_statement = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    rubric_version = Column(String, default="v1")
    total_score = Column(Float, nullable=False)
    criteria_json = Column(Text, nullable=False)
    flags_json = Column(Text, default="[]")
    summary = Column(Text, nullable=True)
    model = Column(String, nullable=True)
    prompt_tokens = Column(Float, nullable=True)
    completion_tokens = Column(Float, nullable=True)
    problem_type = Column(String, nullable=True)
    prompt_score = Column(Float, nullable=True)
    output_score = Column(Float, nullable=True)
    combined_score = Column(Float, nullable=True)
    generated_code_json = Column(Text, nullable=True)
    output_criteria_json = Column(Text, nullable=True)
    evaluation_mode = Column(String, default="prompt_only")
    usage_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assignment = relationship("Assignment", back_populates="evaluations")


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema() -> None:
    """Add new columns to existing SQLite tables if missing."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("problems"):
            cols = {c["name"] for c in insp.get_columns("problems")}
            if "problem_type" not in cols:
                conn.execute(text("ALTER TABLE problems ADD COLUMN problem_type VARCHAR DEFAULT 'prompt_only'"))
            if "acceptance_criteria" not in cols:
                conn.execute(text("ALTER TABLE problems ADD COLUMN acceptance_criteria TEXT"))

        if insp.has_table("evaluations"):
            cols = {c["name"] for c in insp.get_columns("evaluations")}
            migrations = [
                ("problem_type", "VARCHAR"),
                ("prompt_score", "FLOAT"),
                ("output_score", "FLOAT"),
                ("combined_score", "FLOAT"),
                ("generated_code_json", "TEXT"),
                ("output_criteria_json", "TEXT"),
                ("evaluation_mode", "VARCHAR DEFAULT 'prompt_only'"),
                ("usage_json", "TEXT"),
            ]
            for col_name, col_type in migrations:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE evaluations ADD COLUMN {col_name} {col_type}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

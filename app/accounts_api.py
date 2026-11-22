"""Sign-up, sign-in and the per-user history of compliance reports."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    create_token, current_user, find_user_by_email, hash_password, is_valid_email,
    normalize_email, verify_password,
)
from app.db import get_db
from app.models import SavedReport, User

router = APIRouter(prefix="/api/v1")


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    organization: str = Field(min_length=1, max_length=200)
    accepted_terms: bool


class LoginIn(BaseModel):
    email: str
    password: str


class ReportIn(BaseModel):
    document_name: str = Field(min_length=1, max_length=255)
    reporting_date: str | None = None
    classification: dict
    findings: list[dict]


def _user_out(user: User) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "organization": user.organization}


def _session_out(user: User) -> dict:
    return {"token": create_token(user.id), "user": _user_out(user)}


@router.post("/auth/register", status_code=201)
def register(payload: RegisterIn, session: Session = Depends(get_db)) -> dict:
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if not payload.accepted_terms:
        raise HTTPException(status_code=422, detail="You must accept the Terms & Conditions to register.")
    if not payload.full_name.strip() or not payload.organization.strip():
        raise HTTPException(status_code=422, detail="Full name and organization name are required.")
    if find_user_by_email(session, email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        organization=payload.organization.strip(),
        terms_accepted_at=datetime.now(timezone.utc),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # two sign-ups with the same email at once
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    session.refresh(user)
    return _session_out(user)


@router.post("/auth/login")
def login(payload: LoginIn, session: Session = Depends(get_db)) -> dict:
    user = find_user_by_email(session, payload.email)
    # The same message for an unknown email and a wrong password, so the form does not reveal which exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return _session_out(user)


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_out(user)


@router.post("/reports", status_code=201)
def save_report(payload: ReportIn, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict:
    report = SavedReport(
        user_id=user.id,
        document_name=payload.document_name,
        document_type=str(payload.classification.get("document_type", "other")),
        reporting_date=payload.reporting_date,
        classification=payload.classification,
        findings=payload.findings,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _summary(report)


@router.get("/reports")
def list_reports(user: User = Depends(current_user), session: Session = Depends(get_db)) -> list[dict]:
    rows = session.scalars(
        select(SavedReport).where(SavedReport.user_id == user.id).order_by(SavedReport.created_at.desc())
    ).all()
    return [_summary(row) for row in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict:
    report = session.get(SavedReport, report_id)
    if report is None or report.user_id != user.id:  # other users' reports look the same as missing ones
        raise HTTPException(status_code=404, detail="Report not found.")
    return {
        **_summary(report),
        "classification": report.classification,
        "findings": report.findings,
    }


def _summary(report: SavedReport) -> dict:
    statuses = [f.get("status") for f in report.findings]
    return {
        "id": report.id,
        "document_name": report.document_name,
        "document_type": report.document_type,
        "reporting_date": report.reporting_date or None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "counts": {s: statuses.count(s) for s in ("FAIL", "REVIEW", "PASS")},
    }

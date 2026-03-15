from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.schemas.report_schemas import ReportCreate, ReportOut
from app.repositories.repos import ReportRepository

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut)
async def create_report(
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_firebase_token),
):
    repo = ReportRepository(db)
    report = await repo.create(
        user_id=user.get("uid") or user.get("user_id"),
        **body.model_dump(),
    )
    return report


@router.get("", response_model=list[ReportOut])
async def list_reports(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = ReportRepository(db)
    return await repo.list_reports(skip, limit)


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = ReportRepository(db)
    report = await repo.get_by_id(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report

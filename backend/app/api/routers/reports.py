import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Connector, Report, ReportRow
from app.schemas.reports import ReportDetail, ReportGenerateRequest, ReportOut
from app.services.report_service import generate_redmine_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/redmine-deliveries/generate", response_model=ReportOut)
def generate_redmine_deliveries(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    if not payload.project_ids and not payload.query_id:
        raise HTTPException(status_code=400, detail="project_ids or query_id is required")
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    connector = db.query(Connector).filter(Connector.id == payload.connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    report = generate_redmine_report(
        db=db,
        connector=connector,
        project_ids=payload.project_ids,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status_id=payload.status_id,
        query_id=payload.query_id,
    )
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    query = db.query(Report).order_by(Report.generated_at.desc())
    reports = query.offset((page - 1) * page_size).limit(page_size).all()
    return reports


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    rows_query = db.query(ReportRow).filter(ReportRow.report_id == report_id)
    if q:
        ilike = f"%{q}%"
        rows_query = rows_query.filter(
            (ReportRow.cliente.ilike(ilike))
            | (ReportRow.sistema.ilike(ilike))
            | (ReportRow.entrega.ilike(ilike))
            | (ReportRow.source_ref.ilike(ilike))
        )
    total = rows_query.count()
    rows = rows_query.order_by(ReportRow.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReportDetail(
        report=report,
        rows=rows,
        total=total,
        page=page,
        page_size=page_size,
        query=q,
    )


@router.get("/{report_id}/export.csv")
def export_report_csv(
    report_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    rows = db.query(ReportRow).filter(ReportRow.report_id == report_id).order_by(ReportRow.id.asc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Cliente", "Sistema", "Entrega", "source_ref", "source_url"])
    for row in rows:
        writer.writerow([row.cliente, row.sistema, row.entrega, row.source_ref, row.source_url])

    buffer.seek(0)
    filename = f"report-{report_id}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{report_id}/export.pdf")
def export_report_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    rows = db.query(ReportRow).filter(ReportRow.report_id == report_id).order_by(ReportRow.id.asc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Relatorio Redmine - #{report.id}", styles["Title"]),
        Paragraph(f"Status: {report.status}", styles["Normal"]),
        Paragraph(f"Gerado em: {report.generated_at.strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 12),
    ]

    data = [["Cliente", "Sistema", "Entrega", "source_ref", "source_url"]]
    for row in rows:
        data.append([row.cliente or "-", row.sistema or "-", row.entrega or "-", row.source_ref or "-", row.source_url or "-"])

    table = Table(data, repeatRows=1, colWidths=[140, 140, 140, 90, 220])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    filename = f"report-{report_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

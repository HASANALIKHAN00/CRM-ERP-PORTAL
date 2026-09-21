import inspect
from typing import Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, get_readonly_db
import query_functions
from pydantic import BaseModel
import ai_client
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user, create_access_token, resolve_role, COOKIE_NAME, JWT_EXPIRE_MINUTES
import erpnext_client
import models
from auth import get_current_user, create_access_token, resolve_role, COOKIE_NAME, JWT_EXPIRE_MINUTES
import erpnext_client
import models
from fastapi.responses import StreamingResponse
from report_export import build_excel, build_csv, build_pdf
from ai_client import TOOLS
from daily_summary_service import run_daily_summary
from datetime import datetime
import demo_config
app = FastAPI(title="BoxTech Reporting API")

if demo_config.DEMO_MODE:
    import demo_data


@app.on_event("startup")
def seed_demo_data():
    """Populate the in-memory demo database. No-op outside demo mode."""
    if not demo_config.DEMO_MODE:
        return
    counts = demo_data.seed()
    print(f"Demo mode ON \u2014 seeded {sum(counts.values())} fictional records: {counts}")


def resolve_safe_function(function_name: str):
    """
    Look up a reporting function, preferring a demo override for the few
    that read an external system rather than the reporting database.
    """
    if demo_config.DEMO_MODE and function_name in demo_data.SAFE_FUNCTION_OVERRIDES:
        return demo_data.SAFE_FUNCTION_OVERRIDES[function_name]
    return query_functions.SAFE_FUNCTIONS.get(function_name)

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["https://reporting-agent.boxtech.ai", "http://localhost:4200"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInfo(BaseModel):
    email: str
    role: str
    full_name: str


class SessionInfo(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int = 0


class SendMessageRequest(BaseModel):
    question: str

class MessageOut(BaseModel):
    role: str
    content: Optional[str] = None
    records: Optional[List[Any]] = None
    source_note: Optional[str] = None
    sources: Optional[List[Any]] = None
    created_at: datetime


@app.post("/auth/login", response_model=UserInfo)
def login(req: LoginRequest, response: Response):
    email = (req.email or "").strip().lower()
    if demo_config.DEMO_MODE:
        result = demo_config.verify_demo_login(email, req.password)
    else:
        result = erpnext_client.verify_login(email, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # resolve_role reads live ERPNext roles, which demo mode never contacts.
    role = result["role"] if demo_config.DEMO_MODE else resolve_role(email)
    token = create_access_token(email=email, role=role, full_name=result["full_name"])

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        path="/",
    )
    return UserInfo(email=email, role=role, full_name=result["full_name"])


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@app.get("/auth/me", response_model=UserInfo)
def me(user: dict = Depends(get_current_user)):
    return UserInfo(email=user["email"], role=user["role"], full_name=user["full_name"])


@app.get("/health")
def health():
    return {"status": "ok"}


class AppConfig(BaseModel):
    demo_mode: bool
    demo_email: Optional[str] = None


@app.get("/config", response_model=AppConfig)
def get_app_config():
    """
    Unauthenticated so the login screen can label itself before sign-in.
    Exposes only the demo flag and, in demo mode, the account to sign in
    with — never any live configuration.
    """
    if not demo_config.DEMO_MODE:
        return AppConfig(demo_mode=False)
    return AppConfig(demo_mode=True, demo_email=demo_config.DEMO_ADMIN_EMAIL)


@app.get("/query/{function_name}")
def run_query(function_name: str, request: Request, db: Session = Depends(get_readonly_db), user: dict = Depends(get_current_user)):
    fn = resolve_safe_function(function_name)
    if not fn:
        ai_client.log_audit_entry(action="direct_query", detail=function_name, generated_query="REJECTED: unknown function")
        raise HTTPException(status_code=404, detail=f"No such safe function: {function_name}")

    sig = inspect.signature(fn)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name == "db":
            continue
        if name == "user_id":
            kwargs["user_id"] = user["email"]
            continue
        if name == "role":
            kwargs["role"] = user["role"]
            continue
        if name in request.query_params:
            raw = request.query_params[name]
            kwargs[name] = float(raw) if param.annotation is float else (
                int(raw) if param.annotation is int else raw
            )

    result = fn(db, **kwargs)
    ai_client.log_audit_entry(action="direct_query", detail=function_name, generated_query=f"{function_name}({kwargs})")
    return result


@app.get("/reports/catalog")
def get_report_catalog(user: dict = Depends(get_current_user)):
    """
    Report metadata for the frontend to render filter forms dynamically.
    Reuses ai_client.TOOLS as the single source of truth, so a new report
    function only needs to be added in one place, not two.
    """
    catalog = []
    for tool in TOOLS:
        fn_def = tool["function"]
        catalog.append({
            "name": fn_def["name"],
            "description": fn_def["description"],
            "parameters": fn_def["parameters"]["properties"],
        })
    return catalog


EXPORT_FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", build_excel, True),
    "csv": ("text/csv", build_csv, False),
    "pdf": ("application/pdf", build_pdf, True),
}


@app.get("/reports/export/{function_name}")
def export_report(function_name: str, request: Request, format: str = "xlsx", db: Session = Depends(get_readonly_db), user: dict = Depends(get_current_user)):
    fn = resolve_safe_function(function_name)
    if not fn:
        raise HTTPException(status_code=404, detail=f"No such safe function: {function_name}")

    if format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")

    sig = inspect.signature(fn)
    kwargs = {}
    reserved = {"format"}
    for name, param in sig.parameters.items():
        if name == "db" or name in reserved:
            continue
        if name == "user_id":
            kwargs["user_id"] = user["email"]
            continue
        if name == "role":
            kwargs["role"] = user["role"]
            continue
        if name in request.query_params:
            raw = request.query_params[name]
            kwargs[name] = float(raw) if param.annotation is float else (
                int(raw) if param.annotation is int else raw
            )

    result = fn(db, **kwargs)
    ai_client.log_audit_entry(action="report_export", detail=function_name, generated_query=f"{function_name}({kwargs}) [{format}]")

    media_type, builder, needs_function_name = EXPORT_FORMATS[format]
    buffer = builder(result, function_name) if needs_function_name else builder(result)
    filename = f"{function_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.{format}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.get("/reports/daily-summaries")
def list_daily_summaries(limit: int = 14, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Daily summaries are admin-only, since they cover company-wide data.")
    summaries = db.query(models.DailySummary).order_by(models.DailySummary.summary_date.desc()).limit(limit).all()
    return [
        {"id": str(s.id), "summary_date": str(s.summary_date), "content": s.content, "email_sent": s.email_sent}
        for s in summaries
    ]


@app.post("/reports/daily-summaries/generate")
def trigger_daily_summary(send_email: bool = False, user: dict = Depends(get_current_user)):
    """
    Manual trigger, mainly for testing before the scheduled timer is set
    up. send_email defaults to False here so repeated manual tests don't
    spam a real inbox \u2014 pass ?send_email=true explicitly to test the
    email path.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    result = run_daily_summary(send_email=send_email)
    return result

def _get_owned_session(db: Session, session_id: str, user_email: str) -> models.ChatSession:
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id, models.ChatSession.user_id == user_email
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@app.get("/chat/sessions", response_model=List[SessionInfo])
def list_chat_sessions(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    rows = (
        db.query(models.ChatSession, func.count(models.ChatMessage.id).label("message_count"))
        .outerjoin(models.ChatMessage, models.ChatMessage.session_id == models.ChatSession.id)
        .filter(models.ChatSession.user_id == user["email"])
        .group_by(models.ChatSession.id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )
    return [
        SessionInfo(id=str(s.id), title=s.title, created_at=s.created_at, message_count=count)
        for s, count in rows
    ]


@app.post("/chat/sessions", response_model=SessionInfo)
def create_chat_session(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    session = models.ChatSession(user_id=user["email"], title="New chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionInfo(id=str(session.id), title=session.title, created_at=session.created_at)


@app.get("/chat/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_chat_messages(session_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    session = _get_owned_session(db, session_id, user["email"])
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session.id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    return [
        MessageOut(role=m.role, content=m.content, records=m.records, source_note=m.source_note, sources=m.sources, created_at=m.created_at)
        for m in messages
    ]


@app.post("/chat/sessions/{session_id}/messages", response_model=MessageOut)
def send_chat_message(
    session_id: str,
    req: SendMessageRequest,
    db: Session = Depends(get_db),
    readonly_db: Session = Depends(get_readonly_db),
    user: dict = Depends(get_current_user),
):
    session = _get_owned_session(db, session_id, user["email"])

    prior = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session.id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    history = [{"role": m.role, "content": m.content} for m in prior if m.content]

    user_msg = models.ChatMessage(session_id=session.id, role="user", content=req.question)
    db.add(user_msg)

    if session.title == "New chat":
        session.title = req.question[:60]

    db.commit()

    result = ai_client.ask_ai(req.question, readonly_db, user_id=user["email"], role=user["role"], history=history)

    assistant_msg = models.ChatMessage(
        session_id=session.id, role="assistant", content=result.get("summary"),
        records=result.get("records"), source_note=result.get("source"),
        sources=result.get("sources"),
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return MessageOut(
        role="assistant", content=assistant_msg.content, records=assistant_msg.records,
        source_note=assistant_msg.source_note, sources=assistant_msg.sources, created_at=assistant_msg.created_at,
    )


@app.post("/chat/sessions/{session_id}/regenerate", response_model=MessageOut)
def regenerate_chat_message(
    session_id: str,
    db: Session = Depends(get_db),
    readonly_db: Session = Depends(get_readonly_db),
    user: dict = Depends(get_current_user),
):
    session = _get_owned_session(db, session_id, user["email"])
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session.id
    ).order_by(models.ChatMessage.created_at.asc()).all()

    if not messages or messages[-1].role != "assistant":
        raise HTTPException(status_code=400, detail="Nothing to regenerate")

    last_assistant = messages[-1]
    prior_msgs = messages[:-1]
    last_user_index = max((i for i, m in enumerate(prior_msgs) if m.role == "user"), default=None)
    if last_user_index is None:
        raise HTTPException(status_code=400, detail="No prior question found to regenerate")

    last_user_msg = prior_msgs[last_user_index]
    context_msgs = prior_msgs[:last_user_index]
    history = [{"role": m.role, "content": m.content} for m in context_msgs if m.content]

    result = ai_client.ask_ai(last_user_msg.content, readonly_db, user_id=user["email"], role=user["role"], history=history)

    db.delete(last_assistant)
    db.commit()

    new_assistant = models.ChatMessage(
        session_id=session.id, role="assistant", content=result.get("summary"),
        records=result.get("records"), source_note=result.get("source"),
        sources=result.get("sources"),
    )
    db.add(new_assistant)
    db.commit()
    db.refresh(new_assistant)

    return MessageOut(
        role="assistant", content=new_assistant.content, records=new_assistant.records,
        source_note=new_assistant.source_note, sources=new_assistant.sources, created_at=new_assistant.created_at,
    )

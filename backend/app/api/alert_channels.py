from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AlertChannel, AlertEvent
from ..schemas import AlertChannelCreate, AlertChannelOut, AlertChannelUpdate, AlertEventOut
from ..security import get_current_user
from ..services.alerts import send_test_alert
from ..services.daily_report import send_daily_report


router = APIRouter(prefix="/alert-channels", tags=["alert-channels"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlertChannelOut])
def list_channels(db: Session = Depends(get_db)) -> list[AlertChannel]:
    return db.query(AlertChannel).order_by(AlertChannel.id.desc()).all()


@router.get("/events", response_model=list[AlertEventOut])
def list_events(channel_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)) -> list[AlertEvent]:
    query = db.query(AlertEvent).order_by(AlertEvent.id.desc())
    if channel_id is not None:
        query = query.filter(AlertEvent.channel_id == channel_id)
    return query.limit(min(max(limit, 1), 500)).all()


@router.post("", response_model=AlertChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(payload: AlertChannelCreate, db: Session = Depends(get_db)) -> AlertChannel:
    channel = AlertChannel(**payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.put("/{channel_id}", response_model=AlertChannelOut)
def update_channel(channel_id: int, payload: AlertChannelUpdate, db: Session = Depends(get_db)) -> AlertChannel:
    channel = db.query(AlertChannel).filter(AlertChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, db: Session = Depends(get_db)) -> None:
    channel = db.query(AlertChannel).filter(AlertChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    db.delete(channel)
    db.commit()


@router.post("/daily-report/test", response_model=list[AlertEventOut])
async def test_daily_report(db: Session = Depends(get_db)):
    return await send_daily_report(db)


@router.post("/{channel_id}/test", response_model=AlertEventOut)
async def test_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(AlertChannel).filter(AlertChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    return await send_test_alert(db, channel)

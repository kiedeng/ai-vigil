from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SettingsOut, SettingsUpdate
from ..security import get_current_user
from ..services.settings import effective_settings, set_setting_value


router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=SettingsOut)
def get_settings_endpoint(db: Session = Depends(get_db)) -> SettingsOut:
    return SettingsOut(**effective_settings(db))


@router.put("", response_model=SettingsOut)
def update_settings_endpoint(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            set_setting_value(db, key, value)
    return SettingsOut(**effective_settings(db))


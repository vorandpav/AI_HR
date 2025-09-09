from sqlalchemy.orm import Session
from backend import models

def get_meeting_by_token(token: str, db: Session):
    return db.query(models.Meeting).filter(models.Meeting.token == token).first()

def finish_meeting_sync(token: str, session_id: str, db: Session):
    meeting = db.query(models.Meeting).filter(models.Meeting.token == token).first()
    if not meeting:
        raise ValueError("Meeting not found")
    meeting.is_finished = True
    meeting.session_id = session_id  # если поле есть
    db.commit()
    return meeting
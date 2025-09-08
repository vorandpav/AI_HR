from fastapi import Header, HTTPException


def get_requesting_user(x_telegram_user: str | None = Header(None)):
    if not x_telegram_user:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-User header")
    return x_telegram_user

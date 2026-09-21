from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
import jwt
from auth import auth_db
from models.auth import TokenRenewRequest, TokenRenewResp, TokenType, ResponseOK
from stngs import settings as stngs


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/login", refreshUrl="v1/refresh")

router = APIRouter(prefix="/v1", tags=["auth"])

@router.post("/login")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """Авторизует по логин/паролю и возвращает два токена: **access_token** и **refresh_token**"""
    grant_type = form_data.grant_type
    user = auth_db.authenticate_user(form_data.username, form_data.password)
    if user is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect user or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_db.create_access_token(user.user_id)
    refresh_token = auth_db.create_refresh_token(user.user_id)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/token")
async def token_refresh(data: TokenRenewRequest, response: Response) -> TokenRenewResp:
    """Получение новой пары access_token и refresh_token. В теле запроса требуется передать полученный ранее refresh_token"""
    response.headers["Cache-Control"] = 'no-cache, no-store, must-revalidate'
    response.headers["Pragma"] = 'no-cache'
    response.headers["Expires"] = '0'
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = data.refresh_token
    if auth_db.isRefreshTokenValid(token) is False:
        raise credentials_exception
    try:
        payload = jwt.decode(token, stngs.auth.SECRET_KEY.get_secret_value(), algorithms=[stngs.auth.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user_id = int(user_id)
    if int(datetime.now(timezone.utc).timestamp()) - payload['iat'] > stngs.auth.REFRESH_TOKEN_MIN_LIFESPAN_SECONDS:
        auth_db.revokeToken(token)
        new_refresh_token = auth_db.create_refresh_token(user_id)
    else:
        new_refresh_token = token
    access_token = auth_db.create_access_token(user_id)
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@router.get("/users/me")
async def get_own_profile(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, stngs.auth.SECRET_KEY.get_secret_value(), algorithms=[stngs.auth.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user_id = int(user_id)
    user = auth_db.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    roles = auth_db.get_user_roles(user_id)
    return {
        "profile": user.dict(exclude_none=False, exclude_defaults=False, exclude_unset=False, exclude=['pwd_hash', 'version']),
        "role": roles
    }

@router.get("/users/isIamAdmin",
            summary="Checking that current logged-in user has the 'admin' role",
            response_description="'ok' = `true` if authorized user has the 'admin' role, otherwise `false`")
async def isIamAdmin(token: Annotated[str, Depends(oauth2_scheme)]) -> ResponseOK:
    """Проверка на то, что текущий пользователь admin"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, stngs.auth.SECRET_KEY.get_secret_value(), algorithms=[stngs.auth.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user_id = int(user_id)
    return {"ok": auth_db.isAdmin(user_id)}

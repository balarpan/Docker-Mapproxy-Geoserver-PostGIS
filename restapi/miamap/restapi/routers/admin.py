from fastapi import APIRouter, Query, Depends, HTTPException, Response, status, Form
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from auth import auth_db
from models.auth import AdminDisableUserRequest, ResponseOK, AdminRoleListResp, AdminUserListResp, AdminUserListResp, AuthUserCreate, AdminDisableUserRequest, TokenListResp

from stngs import settings as stngs


notAdminExcp = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Grow up a bit to become an admin.",
    headers={"WWW-Authenticate": "Bearer"},
)
async def isAdmin(request: Request):
    user_id = request.state.user
    if user_id is None or not auth_db.isAdmin(user_id) :
        raise notAdminExcp
    return

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/login", refreshUrl="v1/refresh")

#В зависимостях как JWT Bearer, так и проверка, что пользователь в группе администраторов
router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(oauth2_scheme), Depends(isAdmin)])

@router.get("/rolelist")
async def admin_rolelist() -> list[AdminRoleListResp]:
    return auth_db.rolelist()

@router.get("/userlist")
async def admin_userlist(
            user_id: Annotated[int | None, Query(description="ID пользователя, если необходимо ограничить список")] = None
) -> list[AdminUserListResp]:
    """Список существующих пользователей и их ролей"""
    return auth_db.userList(user_id)

@router.patch("/update_user/{user_id}", responses={201: {"model": ResponseOK}})
async def admin_update_user(user_id: int, upd_fields: dict, response: Response) -> ResponseOK:
    """
    Поля, доступные для изменения: 'name', 'email', 'nickname', 'comment', 'disabled', 'password'
    """
    res = auth_db.update_user(user_id, upd_fields)
    if res:
        response.status_code = status.HTTP_201_CREATED
        return {"ok": True}
    return {"ok": False}

@router.patch("/update_user_pass/{user_id}", responses={201: {"model": ResponseOK}})
async def admin_update_user_pass(user_id: int, new_pass: str, response: Response) -> ResponseOK:
    res = auth_db.update_user_pass(user_id, new_pass)
    if res:
        response.status_code = status.HTTP_201_CREATED
        return {"ok": True}
    return {"ok": False}

@router.post(
    "/create_user",
    responses={
        201: {"model": ResponseOK},
        400: {
            "content": {"text/plain": {}},
            "description": "Failed to create new user"
        }
    }
)
async def admin_create_user(new_user: AuthUserCreate, response: Response) -> ResponseOK:
    res = auth_db.add_user(new_user)
    if res is False:
        raise HTTPException(status_code=400, detail="Can't create")
    response.status_code = 201
    return {"ok": True}

@router.post(
    "/set_user_roles/{user_id}",
    responses={
        201: {"model": ResponseOK},
        400: {
            "content": {"text/plain": {}},
            "description": "Failed to set user roles"
        }
    }
)
async def admin_set_user_roles(user_id: int, roles: list[str], response: Response) -> ResponseOK:
    res = auth_db.set_user_roles(user_id, roles)
    if res is False:
        raise HTTPException(status_code=400, detail="Can't create")
    response.status_code = 201
    return {"ok": True}

@router.post(
    "/disable_user/{user_id}",
    responses={
        201: {"model": ResponseOK},
        400: {
            "content": {"text/plain": {}},
            "description": "Failed to set user changes"
        }
    }
)
async def admin_disable_user(user_id: int, disable: AdminDisableUserRequest, response: Response) -> ResponseOK:
    """передайте в теле запроса JSON с параметром 'disable' и требуемым значением"""
    res = auth_db.disable_user(user_id, disable.disable)
    if res is False:
        raise HTTPException(status_code=400, detail="Can't update")
    response.status_code = 201
    return {"ok": True}

@router.get("/key_list")
async def admin_tokenlist() -> list[TokenListResp]:
    """Возвращает список всех выданных и отозванных ключей (**refresh token**)"""
    return auth_db.tokenList()


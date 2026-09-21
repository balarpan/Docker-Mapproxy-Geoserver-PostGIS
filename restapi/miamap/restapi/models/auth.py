from enum import IntEnum
# from ntpath import basename
from typing import Annotated
from pydantic import BaseModel, Field, EmailStr, SecretStr
from datetime import datetime


class TokenType(IntEnum):
    access = 1
    refresh = 2

class AuthUser(BaseModel):
    user_id: int
    name: str | None = None
    email: EmailStr | None = None
    nickname: str
    version: int
    disabled: bool | None = None
    comment: str | None = None
    pwd_hash: SecretStr = None

class AuthUserCreate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    nickname: str
    password: SecretStr 
    disabled: bool = True
    comment: str | None = None

class AuthToken(BaseModel):
    id: int | None = None
    userid: int
    jti: Annotated[str | None, Field(description="JWT Token ID")] = None
    t: TokenType
    exp: Annotated[int, Field(description="Expiration time (Unix timestamp)")]
    iat: Annotated[int | None, Field(description="Issued at (Unix timestamp)")] = None
    uve: Annotated[int, Field(description="version (linked to user)")]

class TokenRenewRequest(BaseModel):
    refresh_token: Annotated[str, Field(description="previously issued refresh token")]

# Responses
class TokenRenewResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Annotated[str, Field(description="Always equal to 'bearer' value for compatibility reasons")] = 'bearer'

class ResponseOK(BaseModel):
    ok: bool

class AdminRoleListResp(BaseModel):
    id: int
    role: str
    comment: str | None
    disabled: bool | None

class AdminUserListResp(BaseModel):
    user_id: int
    name: str | None
    email: str | None
    nickname: str
    created: datetime
    updated: datetime | None
    disabled: bool | None
    version: int
    comment: str | None
    role: list

class AdminDisableUserRequest(BaseModel):
    disable: bool

class TokenListResp(BaseModel):
    id: int
    jti: Annotated[str, Field(description="JWT token ID")]
    type: Annotated[TokenType, Field(description="Вид токена: 1- access, 2 - refresh")]
    user_id: Annotated[int, Field(description="ID пользователя, на которого выписан ключ")]
    version: Annotated[int, Field(description="Векрсия учетной записи пользователя, для которой создавался токен")]
    issued: Annotated[datetime, Field(description="Дата выдачи ключа")]
    expired: Annotated[datetime, Field(description="Дата и время оконачания действия ключа")]
    revoked: Annotated[bool,Field(description="ключ был отозван или нет")]
    nickname: Annotated[str, Field(description="nickname пользователя, на которого выписан ключ")]
    username: Annotated[str, Field(description="Имя пользователя, на которого выписан ключ")]


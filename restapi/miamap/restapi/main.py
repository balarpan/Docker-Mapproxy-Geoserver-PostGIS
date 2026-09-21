from typing import Annotated
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from stngs import settings as stngs
from routers.search import router as search_router
from routers.auth import router as auth_router
from routers.admin import router as admin_router
from auth import JWTAuthBackend, JWTAuthenticationMiddleware


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/token", refreshUrl="v1/refresh")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
]
# stngs = Settings()

app = FastAPI()

# В таком порядке CORS всегда будет отправлен, даже для '401 Unauthorized'
auth_backend = JWTAuthBackend(stngs)
app.add_middleware(
    JWTAuthenticationMiddleware,
    backend=auth_backend,
    exclude_urls=["/sign-up", "/login", "/token", "/ping", "/find_place"],  # Public endpoints
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

v_router = APIRouter(prefix="/v1")

@v_router.get("/")
def read_root(token: Annotated[str, Depends(oauth2_scheme)]):
    global stngs
    return {"Hello": stngs.app_name}
@v_router.get("/ping")
def ping():
    return {"ok": True}

app.include_router(v_router)
app.include_router(search_router)
app.include_router(auth_router)
app.include_router(admin_router)

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from enum import unique
from sqlalchemy import create_engine, text, MetaData
from pydantic import BaseModel
import jwt
from pwdlib import PasswordHash
import time
from functools import lru_cache

from models.auth import AuthUserCreate, AuthUser, AuthToken, TokenType
from .jwt_token import JWTHandler
from stngs import settings as stngs


def ttl_lru_cache(ttl: int, maxsize: int = 128):
    """
    Time aware lru caching, ttl is a seconds

    Examples:
        >> @ttl_lru_cache(ttl=10)
           def expensive(a: int):
               time.sleep(1 + a)
    """
    def wrapper(func):
        @lru_cache(maxsize)
        def inner(__ttl, *args, **kwargs):
            # Note that __ttl is not passed down to func,
            # as it's only used to trigger cache miss after some time
            return func(*args, **kwargs)
        return lambda *args, **kwargs: inner(time.time() // ttl, *args, **kwargs)
    return wrapper

password_hash = PasswordHash.recommended()
def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

engine = create_engine('sqlite:///./auth_db.db')
def exec_sql(query_string: str, params: dict | None =None) -> list:
    if params is None:
        params = {}
    stmt = text(query_string)
    with engine.connect() as connection:
        result = connection.execute(stmt, params)
        # If the query returns rows (like SELECT), convert to dictionaries
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
        return []
def exec_transaction(query_string, params=None) -> int:
    """Executes INSERT, UPDATE, DELETE statements with automatic COMMIT."""
    if params is None:
        params = {}
    stmt = text(query_string)
    # engine.begin() automatically starts a transaction and commits at the end
    with engine.begin() as connection:
        result = connection.execute(stmt, params)
        return result.rowcount  # Returns number of affected rows

exec_sql("""CREATE TABLE IF NOT EXISTS user (
	user_id INTEGER, 
	name VARCHAR(16), 
	email VARCHAR(90), 
	nickname VARCHAR(50) NOT NULL, 
	pwd_hash VARCHAR(190) NOT NULL, 
	created DATETIME NOT NULL, 
	updated DATETIME DEFAULT NULL, 
	disabled BOOLEAN DEFAULT FALSE, 
	version INTEGER NOT NULL, 
	comment VARCHAR(255), 
	PRIMARY KEY (user_id)
)""")
exec_sql("""CREATE TABLE IF NOT EXISTS role (
	id INTEGER NOT NULL, 
	role VARCHAR(60) NOT NULL, 
	comment VARCHAR(120), 
	disabled BOOLEAN DEFAULT TRUE, 
	PRIMARY KEY (id), 
	UNIQUE (role)
)""")
exec_sql("""CREATE TABLE IF NOT EXISTS user_role (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT userrole_unq UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES user (user_id) ON DELETE CASCADE ON UPDATE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES role (id) ON DELETE CASCADE ON UPDATE CASCADE
)""")
exec_sql("""CREATE TABLE IF NOT EXISTS token (
	id INTEGER NOT NULL, 
	jti VARCHAR(40) NOT NULL, 
	type INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	issued DATETIME NOT NULL, 
	expired DATETIME, 
	revoked BOOLEAN DEFAULT FALSE,
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (user_id) ON DELETE CASCADE ON UPDATE CASCADE
)""")

class AuthDB:
    def __init__(self, stngs):
        self.stngs = stngs
        self.SECRET_KEY = stngs.auth.SECRET_KEY.get_secret_value()
        if not hasattr(self, "_initialized"):
            self._jwt_handler = JWTHandler(
                secret=stngs.auth.SECRET_KEY.get_secret_value(),
                algorithm=stngs.auth.ALGORITHM
            )
            self._initialized = True
        self.init_db_defaults()

    def init_db_defaults(self):
        exec_transaction("INSERT INTO role (role, comment, disabled) VALUES \
          ('admin', 'Администратор', FALSE), ('viewer', 'Только просмотр данных', FALSE), \
          ('label_editor', 'Редактор подписей', TRUE), ('terminal', 'Доступ к новостному терминалу', TRUE)\
          ON CONFLICT(role) DO NOTHING")
        for user in stngs.auth.persist_users:
            self.check_def_user(user)

    def check_def_user(self, userCheck: dict) -> bool:
        """Проверка существования и добавление предзаданного пользователя"""
        auser = userCheck.nickname
        apwd = password_hash.hash(userCheck.pwd.get_secret_value())
        rows = exec_sql("SELECT user_id, disabled, version FROM user WHERE nickname=:nickname", {"nickname": auser})
        if 0< len(rows):
            if rows[0]['disabled']:
                print(f"revert back disabled persistent user {auser}")
                exec_transaction("UPDATE user SET disabled=NULL, updated=DateTime('now'), version=:version\
                  WHERE nickname=:nickname", {"nickname": auser, "version": rows[0]['version'] + 1})
        else:
            res = exec_transaction(
                "INSERT INTO user (nickname, pwd_hash, created, version, name, email, comment, disabled)\
                VALUES (:auser, :apwd, DateTime('now'), 0, :name, :email, :comment, FALSE)",
                {"auser": auser, "apwd": apwd, "ctm": datetime.now(timezone.utc), "name": userCheck.name, "email": userCheck.email, "comment": userCheck.comment})
            if res <= 0:
                return False
        user_id = exec_sql("SELECT user_id FROM user WHERE nickname=:nickname", {"nickname": auser})[0]['user_id']
        for role in userCheck.role:
            exec_transaction(
                "INSERT INTO user_role (user_id, role_id) SELECT :userid, id FROM role WHERE role.role=:role\
                ON CONFLICT(user_id, role_id) DO NOTHING",
                {"userid": user_id, "role": role})
        return True

    @ttl_lru_cache(ttl=1)
    def get_user_by_id(self, userid: int) -> AuthUser | None:
        try:
            rows = exec_sql("SELECT * FROM user WHERE user_id=:uid", {"uid": userid})
            if 0 == len(rows):
                return None
            return AuthUser(**rows[0])
        except Exception as e:
            raise Exception(f"Database error: {e}")

    @ttl_lru_cache(ttl=1)
    def get_user_by_nickname(self, nickname: str) -> AuthUser | None:
        try:
            rows = exec_sql("SELECT * FROM user WHERE nickname=:uid", {"uid": nickname})
            if 0 == len(rows):
                return None
            return AuthUser(**rows[0])
        except Exception as e:
            raise Exception(f"Database error: {e}")

    def get_user_tokens(self, user_id: int, type: TokenType | None =None) -> list[AuthToken]:
        qry = f"SELECT * FROM token WHERE user_id = :uid{ f' AND type = :type' if type else ''}"
        ret = exec_sql(qry, {"uid": user_id, "type": type})
        return [AuthToken(**i) for i in ret]

    @ttl_lru_cache(ttl=1)
    def get_user_roles(self, user_id: int) -> list[dict]:
        qry = "SELECT role, comment, disabled FROM user_role ur JOIN role r ON r.id = ur.role_id WHERE ur.user_id = :uid"
        return exec_sql(qry, {"uid": user_id})

    def add_user(self, user: AuthUserCreate) -> bool:
        """Add new user"""
        pwd_hash =  password_hash.hash(user.password.get_secret_value())
        qry = f"""INSERT INTO user (name, email, nickname, pwd_hash, created, version, comment, disabled)\
          VALUES (:uname, :eml, :nickname, :hash, DateTime('now'), 0, :comment, :disabled)"""
        res = exec_transaction(
            qry,
            {"uname": user.name, "eml": user.email, "nickname": user.nickname, "hash": pwd_hash, "comment": user.comment, "disabled": user.disabled})
        return res > 0

    def update_user(self, user_id: int, upd_fields: dict) -> bool:
        db_columns = ['name', 'email', 'nickname', 'comment', 'disabled', 'pwd_hash']
        upd_fields.pop('pwd_hash', None)
        pwd = upd_fields.pop('password', None)
        to_update = {k: v for k,v in upd_fields.items() if k in db_columns}
        if pwd:
            to_update['pwd_hash'] = password_hash.hash(pwd)
        if 'disabled' in to_update:
            to_update['disabled'] = to_update['disabled'] is True
        if 0 == len(to_update.keys()):
            return False
        qry = f"""UPDATE user SET \
            {','.join([' ' + k + '=:' + k for k,v in to_update.items()])}, \
            version=version + 1, updated=DateTime('now') \
            WHERE user_id=:uid"""
        res = exec_transaction(qry, {'uid': user_id} | to_update)
        return res == 1

    def update_user_pass(self, user_id:int, new_pwd: str) -> bool:
        pwd_hash =  password_hash.hash(new_pwd)
        res = exec_transaction("UPDATE user SET pwd_hash=:pwd WHERE user_id=:uid", {"uid": user_id, "pwd": pwd_hash})
        return res == 1

    def set_user_roles(self, user_id: int, roles_to_set: list[str]) -> bool:
        user = auth_db.get_user_by_id(user_id)
        if user is None:
            return False
        rrow = exec_sql("SELECT id, role FROM role WHERE disabled=FALSE")
        exs_roles = [r['role'] for r in rrow]
        roles = [r for r in roles_to_set if r in exs_roles]
        if 0 == len(roles):
            return False
        exec_transaction("DELETE from user_role where user_id=:uid", {"uid": user_id})
        for role in roles:
            try:
                role_id = [r['id'] for r in rrow if r['role'] == role][0]
            except ValueError:
                continue
            exec_transaction("INSERT INTO user_role (user_id, role_id) VALUES(:uid, :rid)", {"uid": user_id, "rid": role_id})
            exec_transaction("UPDATE user SET version=version + 1 WHERE user_id=:uid", {"uid":user_id})
        return True

    def disable_user(self, user_id, disabled: bool) -> bool:
        res = exec_transaction("UPDATE user SET disabled = :dis WHERE user_id = :uid", {"uid": user_id, "dis": bool(disabled)})
        return res > 0

    def authenticate_user(self, username: str, password: str) -> AuthUser | bool:
        """Authenticate user via login and password

        Args:
            username (str):  username
            password (str):  provided password

        Returns:
            AuthUser|bool:  `False` if authentication is failed, otherwise AuthUser instance
        """
        user = self.get_user_by_nickname(username)
        if not user:
            return False
        if not verify_password(password, user.pwd_hash.get_secret_value()):
            return False
        return user
        
    def add_token(self, token: str) -> bool:
        """Put refresh token in DB"""
        try:
            data = jwt.decode(token, self.SECRET_KEY, algorithms=[stngs.auth.ALGORITHM])
        except jwt.InvalidTokenError:
            return False
        if not all(p in data for p in ['t', 'jti', 'uve']):
            return False
        qry = "INSERT INTO token (jti, type, user_id, version, issued, expired)\
          VALUES (:jti, :type, :uid, :version, :iat, :etm)"
        if 0 >= exec_transaction(
            qry,
            {"jti":data['jti'], "type": int(data['t']), "uid": int(data['sub']),
             "version": int(data['uve']),
             "iat": datetime.utcfromtimestamp(data['iat']) if data['iat'] else datetime.now(timezone.utc),
             "etm": datetime.utcfromtimestamp(data['exp'])}
        ):
            return False
        qry = "DELETE FROM token WHERE expired < DateTime('now')"
        exec_transaction(qry, {"ct": datetime.now(timezone.utc)})
        return True

    def create_access_token(self, user_id) -> str | None:
        token = self.create_token( {"sub": user_id},
            expiration=timedelta(seconds=stngs.auth.ACCESS_TOKEN_EXPIRE_SECONDS),
            token_type=TokenType.access)
        return token

    def create_refresh_token(self, user_id) -> str | None:
        token = self.create_token( {"sub": user_id},
            expiration=timedelta(seconds=stngs.auth.REFRESH_TOKEN_EXPIRE_SECONDS),
            token_type=TokenType.refresh)
        return token
    
    def isRefreshTokenValid(self, token: str) -> bool:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[stngs.auth.ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                return False
        except jwt.InvalidTokenError:
            return False
        except Exception as e:
            return False
        user_id = int(user_id)
        user = self.get_user_by_id(user_id)
        if user is None or int(payload['uve']) != user.version:
            return False
        rows = exec_sql("SELECT * FROM token WHERE jti=:jti AND type=:type AND revoked=False AND expired > DateTime('now')",
                        {"jti": payload['jti'], "type": TokenType.refresh})
        if 1 != len(rows):
            return False
        return True

    def create_token( self, user_data: dict | BaseModel,
                     expiration: int | float | timedelta | None = None,
                     token_type: TokenType = TokenType.access
    ) -> str | None:
        """
        Create a JWT token with an optional expiration time.

        Args:
            user_data (Union[Dict[str, Any], BaseModel]): The payload data to encode into the JWT.
            expiration (Optional[Union[int, float, datetime.timedelta]]): Expiration time in seconds or timedelta.
            token_type (TokenType): Token type.

        Returns:
            str | None: The generated JWT token string or None if user not found.

        Examples:
            >>> backend = JWTAuthBackend()
            >>> token = await backend.create_token({"user_id": 123}, expiration=3600, TokenType.access)
            >>> print(f"Generated token: {token}")
        """
        if isinstance(user_data, BaseModel):
            payload = {"sub": str(user_data.user_id)}
        else:
            payload = user_data
            if 'user_id' in payload:
                payload['sub'] = str(user_data['user_id'])
                payload.pop('user_id')
            else:
                payload['sub'] = str(payload['sub'])
        if expiration is None:
            expiration = datetime.now(timezone.utc) + timedelta(seconds=stngs.auth.ACCESS_TOKEN_EXPIRE_SECONDS)
        else:
            expiration = (
                datetime.now(timezone.utc) + expiration
                if isinstance(expiration, timedelta)
                else int(expiration)
            )
        payload['exp'] = expiration
        payload['t'] = token_type
        if TokenType.refresh == token_type:
            user = self.get_user_by_id(int(payload['sub']))
            if user is None:
                return None
            payload.update({"uve": user.version, "jti": str(uuid4()), "iat": int(datetime.now(timezone.utc).timestamp())})
        token = jwt.encode(payload, self.SECRET_KEY, algorithm=stngs.auth.ALGORITHM)
        if 't' in payload and int(payload['t']) == TokenType.refresh:
            self.add_token(token)
        return token

    def revokeToken(self, token:str):
        payload = None
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[stngs.auth.ALGORITHM])
        except jwt.InvalidTokenError:
            pass 
        except Exception as e:
            pass
        if payload and payload['jti']:
            exec_transaction("UPDATE token SET revoked=True WHERE jti=:jti", {"jti": payload['jti']})

    @ttl_lru_cache(ttl=1)
    def isAdmin(self, user_id) -> bool:
        rows = exec_sql(
            "SELECT r.role FROM user_role ur JOIN role r ON ur.role_id = r.id WHERE ur.user_id=:uid AND r.role='admin'",
            {"uid": user_id}
        )
        return len(rows) == 1

    @ttl_lru_cache(ttl=2)
    def rolelist(self):
        """Список существующих ролей"""
        return exec_sql( "SELECT id, role, comment, disabled FROM role")

    def userList(self, user_id: int | None):
        """Список существующих пользователей"""
        users = exec_sql(f"SELECT * FROM user {"WHERE user_id=:uid" if user_id is not None else ''}", {"uid": user_id});
        for user in users:
            user.pop('pwd_hash', None)
            if user['created'][-1] != 'Z':
                user['created'] = user['created']+'Z'
            if user['updated'] is not None and user['updated'][-1] != 'Z':
                user['updated'] = user['updated']+'Z'
            roles = exec_sql(
                "SELECT r.id, r.role FROM user_role ur JOIN role r ON r.id = ur.role_id WHERE ur.user_id = :uid",
                {"uid": user['user_id']}
            )
            user['role'] = roles
        return users

    def tokenList(self) -> list[dict]:
        tokens = exec_sql("SELECT t.*, u.nickname, u.name AS username FROM token t LEFT JOIN user u on u.user_id = t.user_id")
        for token in tokens:
            if token['issued'][-1] != 'Z':
                token['issued'] = token['issued'] + 'Z'
            if token['expired'][-1] != 'Z':
                token['expired'] = token['expired'] + 'Z'
        return tokens


auth_db = AuthDB(stngs)

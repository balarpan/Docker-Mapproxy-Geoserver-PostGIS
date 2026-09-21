"""backend forJWT authentication. Insipred by https://github.com/deepmancer/fastapi-auth-jwt/"""

import json
from datetime import datetime
from typing import Any, Dict, Optional, Type, Union
import jwt
from models.auth import TokenType
from pydantic import BaseModel
from .jwt_token import JWTHandler


class JWTAuthBackend:
    """
    A backend class for handling JWT-based authentication.

    Attributes:
        _jwt_handler (JWTHandler): Handler for encoding and decoding JWT tokens.

    Methods:
        authenticate(token: str) -> Optional[BaseModel]: Authenticate a user based on a provided JWT token.
        create_token(user_data: Union[Dict[str, Any], pydantic.BaseModel], expiration: Optional[Union[int, float, timedelta]]) -> str: Create a JWT token with an optional expiration time.
        invalidate_token(token: str) -> None: Invalidate a JWT token by removing it from the cache.
        get_jwt_user(token: str) -> Optional[BaseModel]: Retrieve the current user based on a JWT token.
        get_instance() -> Optional["JWTAuthBackend"]: Get the singleton instance of the JWTAuthBackend class.
    """

    _instance: Optional["JWTAuthBackend"] = None

    def __new__(cls, *args, **kwargs) -> "JWTAuthBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__( self, stngs):
        if not hasattr(self, "_initialized"):
            self._jwt_handler = JWTHandler(
                secret=stngs.auth.SECRET_KEY.get_secret_value(),
                algorithm=stngs.auth.ALGORITHM
            )
            self._initialized = True

    async def authenticate(self, token: str) -> int | None:
        """
        Authenticate a user based on a provided JWT access token.

        Args:
            token (str): The JWT token to authenticate.

        Returns:
            int|None: user_id or None if authentication failed

        Raises:
            jwt.PyJWTError: If there is an issue with decoding the JWT token.
            Exception: For any other unexpected errors.

        Examples:
            >>> backend = JWTAuthBackend(stngs)
            >>> user_id = await backend.authenticate("some_jwt_token")
            >>> if user_id is not None:
            >>>     print(f"Authenticated user: {user_id}")
        """
        try:
            data = self.jwt_handler.decode(token)
        except jwt.ExpiredSignatureError  as e:
            return None
        except jwt.PyJWTError as e:
            raise e
        except Exception as e:
            raise Exception(f"An unexpected error occurred during authentication: {e}")
        if 't' not in data or TokenType.access != data['t']:
            return None
        return int(data['sub'])


    async def invalidate_token(self, token: str) -> None:
        """
        Invalidate a JWT token by removing it from the cache.

        Args:
            token (str): The JWT token to invalidate.

        Returns:
            None

        Examples:
            >>> backend = JWTAuthBackend()
            >>> await backend.invalidate_token("some_jwt_token")
        """
        try:
            self.jwt_handler.decode(token, verify=True)
        finally:
            await self.cache.delete(token)

    async def get_jwt_user(self, token: str) -> Optional[BaseModel]:
        """
        Retrieve the user based on a JWT token.

        Args:
            token (str): The JWT token to decode and validate.

        Returns:
            Optional[BaseModel]: The validated user model, or None if validation fails.

        Raises:
            jwt.InvalidTokenError: If the token payload does not match the cached payload.
            Exception: For any other unexpected errors.

        Examples:
            >>> backend = JWTAuthBackend()
            >>> user = await backend.get_jwt_user("some_jwt_token")
            >>> if user:
            >>>     print(f"Current user: {user}")
        """
        token_payload = self.jwt_handler.decode(token)
        try:
            cached_payload = await self.cache.get(token)
            cached_payload = json.loads(cached_payload) if cached_payload else None
        except Exception as e:
            raise Exception(f"Failed to retrieve token from cache: {e}")

        if not cached_payload:
            return None

        for key, value in token_payload.items():
            if value is None:
                continue
            if key not in cached_payload or cached_payload[key] != value:
                raise jwt.InvalidTokenError(f"Token payload mismatch for key: {key}")

        return self.user_schema.model_construct(
            token=token,
            **cached_payload,
        )

    @classmethod
    def get_instance(cls) -> Optional["JWTAuthBackend"]:
        """
        Get the singleton instance of the JWTAuthBackend class.

        Returns:
            Optional[JWTAuthBackend]: The singleton instance.

        Examples:
            >>> backend = JWTAuthBackend.get_instance()
            >>> if backend:
            >>>     print("JWTAuthBackend instance exists.")
        """
        return cls._instance

    @property
    def jwt_handler(self) -> JWTHandler:
        """Get the current JWT handler."""
        return self._jwt_handler

    @jwt_handler.setter
    def jwt_handler(self, value: JWTHandler) -> None:
        """Set a new JWT handler."""
        self._jwt_handler = value


__all__ = ["JWTAuthBackend"]

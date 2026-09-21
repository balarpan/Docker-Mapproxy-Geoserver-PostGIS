import asyncio
from stngs import settings as stngs
from auth.auth_db import AuthDB
from auth import JWTAuthBackend, JWTAuthenticationMiddleware

async def main():
    a = AuthDB(stngs)
    print( 'user id=1', a.get_user_by_id(1) )
    print( 'user admin', a.get_user_by_nickname('admin') )
    print( 'user access tokens', a.get_user_tokens(1, 'access') )
    print( 'user refresh tokens', a.get_user_tokens(1, 'refresh') )
    print( 'auth attempt:', a.authenticate_user('admin', '1') )

    b = JWTAuthBackend(stngs)
    token = a.create_access_token(1)
    print('token', token)
    user_id_token = await b.authenticate(token)
    print('token authenticate:', user_id_token)

if __name__ == "__main__":
    asyncio.run(main())
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
    # loop.close()

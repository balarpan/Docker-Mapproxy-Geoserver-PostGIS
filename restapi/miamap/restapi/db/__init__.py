from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import os
# import urllib.parse

class PgDbHandler:
    def __init__(self, stngs):
        """Initializes the database engine using SQLAlchemy connection URL."""
        self.connection_url = URL.create(
            drivername="postgresql+psycopg",  # Uses the standard psycopg2 driver
            username=stngs.db.user,
            password=stngs.db.upw.get_secret_value(),
            host=stngs.db.host,
            port=stngs.db.port,
            database=stngs.db.database
        )
        # pool_pre_ping=True helps detect and reconnect dropped connections
        self.engine = create_engine(self.connection_url, pool_pre_ping=True)
        # conn_str = f"postgresql+psycopg://{urllib.parse.quote_plus(stngs.db.user)}:{urllib.parse.quote_plus(stngs.db.upw.get_secret_value())}@{stngs.db.host}:{stngs.db.port}/{stngs.db.database}"
        # self.engine = create_engine(conn_str, pool_pre_ping=True)

    def exec_query(self, query_string, params: dict | None =None) -> list:
        """Executes a SELECT query and returns rows as dictionaries."""
        if params is None:
            params = {}
        stmt = text(query_string)
        with self.engine.connect() as connection:
            result = connection.execute(stmt, params)
            # If the query returns rows (like SELECT), convert to dictionaries
            if result.returns_rows:
                return [dict(row._mapping) for row in result]
            return []

    def exec_transaction(self, query_string, params=None) -> int:
        """Executes INSERT, UPDATE, DELETE statements with automatic COMMIT."""
        if params is None:
            params = {}
        stmt = text(query_string)
        # engine.begin() automatically starts a transaction and commits at the end
        with self.engine.begin() as connection:
            result = connection.execute(stmt, params)
            return result.rowcount  # Returns number of affected rows

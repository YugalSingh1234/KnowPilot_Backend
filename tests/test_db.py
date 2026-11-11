from sqlalchemy.pool import NullPool

from app.db import _engine_kwargs


def test_serverless_uses_nullpool_and_disables_prepared_statements_for_transaction_pooler():
    kw = _engine_kwargs("postgresql+psycopg://u:p@host:6543/db", serverless=True)
    assert kw["poolclass"] is NullPool and "pool_size" not in kw
    assert kw["connect_args"] == {"prepare_threshold": None}


def test_long_running_server_keeps_pool():
    kw = _engine_kwargs("postgresql+psycopg://u:p@host:5432/db", serverless=False)
    assert kw["pool_size"] == 5 and "poolclass" not in kw and "connect_args" not in kw

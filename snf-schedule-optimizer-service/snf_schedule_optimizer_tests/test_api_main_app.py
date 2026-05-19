import fastapi

from snf_schedule_optimizer.api.main import app


def test_main_module_exports_app() -> None:
    assert isinstance(app, fastapi.FastAPI)

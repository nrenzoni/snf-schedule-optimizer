import fastapi


def test_main_module_exports_app() -> None:
    from snf_schedule_optimizer.api.main import app

    assert isinstance(app, fastapi.FastAPI)

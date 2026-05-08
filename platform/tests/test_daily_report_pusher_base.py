import pytest
from platform_app.daily_report.pushers import base


def test_pusher_is_abstract():
    with pytest.raises(TypeError):
        base.Pusher()


def test_push_result_dataclass():
    r = base.PushResult(success=True, error=None)
    assert r.success is True
    assert r.error is None

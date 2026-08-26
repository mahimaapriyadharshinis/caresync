from backend.controller_client import ControllerClient


def test_disabled_by_default_and_noop():
    client = ControllerClient(base_url=None)
    assert not client.enabled
    client.mark_critical("00:00:00:00:00:01")  # must not raise
    client.clear_critical("00:00:00:00:00:01")  # must not raise


def test_enabled_when_base_url_given():
    client = ControllerClient(base_url="http://example.invalid:8080")
    assert client.enabled


def test_unreachable_controller_does_not_raise():
    client = ControllerClient(base_url="http://127.0.0.1:1", timeout=0.2)
    client.mark_critical("00:00:00:00:00:01")  # nothing is listening — must not raise

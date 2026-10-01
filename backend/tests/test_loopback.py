from app.main import _is_loopback


def test_is_loopback_hosts():
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert _is_loopback("127.1.2.3")
    assert not _is_loopback("0.0.0.0")
    assert not _is_loopback("192.168.1.1")

"""downloader._get の再試行ポリシーを検証する。

自治体サイトの WAF は CI（データセンター IP）からのアクセスに対し間欠的に 403 を返す
ことがあるため、403/429/5xx などの一時的エラーは再試行し、404 などの永続的エラーは
即座に諦める、という挙動を担保する。
"""
from __future__ import annotations

import requests
import pytest

from fukuoka_gtfs import downloader


class _Resp:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


class _FakeSession:
    """あらかじめ与えた応答列（例外も可）を順に返すダミー Session。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(downloader.time, "sleep", lambda *_: None)


def test_retries_transient_403_then_succeeds():
    session = _FakeSession([_Resp(403), _Resp(403), _Resp(200, b"OK")])
    content = downloader._get(session, "https://example.test/file.xls", retries=4)
    assert content == b"OK"
    assert session.calls == 3  # 403 を 2 回再試行し 3 回目で成功


def test_retries_429_and_5xx():
    session = _FakeSession([_Resp(429), _Resp(503), _Resp(200, b"DATA")])
    content = downloader._get(session, "https://example.test/file.xls", retries=4)
    assert content == b"DATA"
    assert session.calls == 3


def test_permanent_404_is_not_retried():
    session = _FakeSession([_Resp(404), _Resp(200, b"never")])
    with pytest.raises(RuntimeError):
        downloader._get(session, "https://example.test/missing.xls", retries=4)
    assert session.calls == 1  # 404 は再試行しない


def test_connection_error_is_retried():
    session = _FakeSession([requests.ConnectionError("boom"), _Resp(200, b"OK")])
    content = downloader._get(session, "https://example.test/file.xls", retries=4)
    assert content == b"OK"
    assert session.calls == 2


def test_exhausts_retries_on_persistent_403():
    session = _FakeSession([_Resp(403)] * 3)
    with pytest.raises(RuntimeError):
        downloader._get(session, "https://example.test/file.xls", retries=3)
    assert session.calls == 3  # retries 回試して諦める


def test_sends_browser_user_agent_and_referer():
    captured = {}

    class _CaptureSession:
        def get(self, url, headers=None, timeout=None):
            captured["referer"] = (headers or {}).get("Referer")
            return _Resp(200, b"OK")

    downloader._get(_CaptureSession(), "https://subway.example.lg.jp/a/b/c.xls", retries=2)
    assert captured["referer"] == "https://subway.example.lg.jp/"
    # ブラウザ UA がセッション既定ヘッダに含まれること
    assert "Mozilla/5.0" in downloader._HEADERS["User-Agent"]

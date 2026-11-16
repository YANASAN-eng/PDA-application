"""CLAUDE.md の「テストは外部に出ない」をテストで守る(tests/conftest.py の仕掛けの確認)。"""

import socket
import urllib.request

import pytest


def test_テストから外部のホストの名前解決はできない():
    with pytest.raises(RuntimeError, match="テストからネットワークに出ようとしました"):
        socket.getaddrinfo("example.com", 443)


def test_テストから外部のアドレスへは接続できない():
    with pytest.raises(RuntimeError, match="テストからネットワークに出ようとしました"):
        socket.create_connection(("93.184.215.14", 80), timeout=1)


def test_本物のHTTP取得もテストでは止まる():
    with pytest.raises(Exception) as e:
        urllib.request.urlopen("https://example.com/", timeout=1)
    assert "テストからネットワークに出ようとしました" in str(e.value)


def test_自分自身への接続は許す():
    # TestClient の内部などが使うため。待ち受けていないポートなので接続は断られるが、仕掛けでは止めない
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", 9), timeout=1)

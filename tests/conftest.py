"""全テスト共通の設定。

CLAUDE.md の「テストは外部に出ない」を仕掛けで守る:
すべてのテストで、外部のホストへの名前解決と接続をエラーにする(自分自身 127.0.0.1 / localhost は許す)。
RSS は tests/fixtures/ の XML、取得は Fake を使うこと。
"""

import socket

import pytest

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "", None}
_MESSAGE = "テストからネットワークに出ようとしました(Fake を使ってください): {}"


def _host_of(address) -> object:
    return address[0] if isinstance(address, tuple) else address


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL_HOSTS:
            raise RuntimeError(_MESSAGE.format(host))
        return original_getaddrinfo(host, *args, **kwargs)

    def connect(self, address):
        if _host_of(address) not in _LOCAL_HOSTS:
            raise RuntimeError(_MESSAGE.format(address))
        return original_connect(self, address)

    def connect_ex(self, address):
        if _host_of(address) not in _LOCAL_HOSTS:
            raise RuntimeError(_MESSAGE.format(address))
        return original_connect_ex(self, address)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)

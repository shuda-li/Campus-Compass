import re
import threading
import os

_default_proxy = os.environ.get('DEFAULT_PROXY', 'http://127.0.0.1:7897')

_store = threading.local()


def set_proxy(address: str):
    if address:
        _store.proxies = {"http": address, "https": address}
    else:
        _store.proxies = None


def get_proxy() -> dict:
    if hasattr(_store, 'proxies') and _store.proxies is not None:
        return _store.proxies
    if _default_proxy:
        return {"http": _default_proxy, "https": _default_proxy}
    return None


def clear_proxy():
    _store.proxies = None


def get_default() -> str:
    return _default_proxy


def validate(address: str) -> tuple:
    if not address or not address.strip():
        return False, "代理地址不能为空"

    address = address.strip()

    pattern = r'^https?://[\w.\-]+(:\d{1,5})?$'
    if not re.match(pattern, address):
        return False, "格式错误：需要 http(s)://地址:端口 (如 http://127.0.0.1:7897)"

    try:
        import requests
        resp = requests.get(
            "https://www.baidu.com",
            proxies={"http": address, "https": address},
            timeout=5
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"代理响应异常 (HTTP {resp.status_code})"
    except requests.exceptions.ConnectTimeout:
        return False, "连接超时，代理不可达"
    except requests.exceptions.ProxyError:
        return False, "代理连接被拒绝"
    except requests.exceptions.ConnectionError:
        return False, "连接失败，请检查代理地址"
    except Exception as e:
        return False, f"验证失败: {str(e)[:50]}"

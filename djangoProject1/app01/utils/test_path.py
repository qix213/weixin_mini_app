import base64
import hashlib
import hmac
import time
import urllib.request
from datetime import datetime
from urllib.parse import urlencode


def sign(algorithm: str, data: bytes, secret: bytes) -> str:
    if algorithm == "md5-salt":
        h = hashlib.md5()
        h.update(data)
        return h.digest().hex()
    # 其他算法保持不变...
    raise NotImplemented("Algorithm " + algorithm + " not supported yet")


if __name__ == "__main__":
    opener = urllib.request.build_opener()

    # 1. 使用截图中的正确环境地址
    base_uri = "https://test-api.jdl.com"

    # 2. 填入截图中的真实配置
    app_key = "62d07644754843cc882fca7c01476c4f"
    app_secret = "0c2c8b6b7c10481ea639f6daa09ac02e"
    access_token = "78c246c0ab564e67add6296a9eaf04a1"
    domain = "ECAP"

    path = "/ecap/v1/orders/status/get"
    algorithm = "md5-salt"

    # 3. 更新请求体：使用真实的 customerCode 和运单号
    # 注意：不要使用带 * 号的占位符，接口会解析失败
    body = '[{"customerCode":"27K1234912s","waybillCode":"JDV999888776","orderCode":"JDV999888776"}]'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 签名内容拼接
    content = "".join([
        app_secret,
        "access_token", access_token,
        "app_key", app_key,
        "method", path,
        "param_json", body,
        "timestamp", timestamp,
        "v", "2.0",
        app_secret
    ])

    sign_ = sign(algorithm, content.encode("UTF-8"), app_secret.encode("UTF-8"))

    uri = base_uri + path
    queries = {
        "LOP-DN": domain,
        "app_key": app_key,
        "access_token": access_token,
        "timestamp": timestamp,
        "v": "2.0",
        "sign": sign_,
        "algorithm": algorithm
    }

    offset = str(int(-time.timezone / 3600))
    headers = {
        "lop-tz": offset,
        "User-Agent": "lop-http/python3",
        "content-type": "application/json;charset=utf-8",
    }

    url = uri + "?" + urlencode(queries)
    http_request = urllib.request.Request(url=url, data=body.encode("UTF-8"), headers=headers)

    try:
        http_response = opener.open(http_request)
        print("状态码:", http_response.status)
        print("响应:", http_response.read().decode("UTF-8"))
    except Exception as e:
        print("请求报错:", e)
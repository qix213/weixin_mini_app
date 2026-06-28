import base64
import hashlib
import hmac
import time
import urllib.request
import json
import logging
from datetime import datetime
from urllib.parse import urlencode
from django.conf import settings

logger = logging.getLogger('django')


class JDLClient:
    def __init__(self):
        # 从 settings 读取配置，提供沙盒环境的默认兜底
        self.app_key = getattr(settings, 'JDL_APP_KEY', '')
        self.app_secret = getattr(settings, 'JDL_APP_SECRET', '')
        self.access_token = getattr(settings, 'JDL_ACCESS_TOKEN', '')
        self.domain = getattr(settings, 'JDL_LOP_DN', 'ECAP')
        self.base_uri = getattr(settings, 'JDL_BASE_URL', 'https://test-api.jdl.com')

    def sign(self, algorithm: str, data: bytes, secret: bytes) -> str:
        """官方签名算法实现"""
        if algorithm == "md5-salt":
            h = hashlib.md5()
            h.update(data)
            return h.digest().hex()
        elif algorithm == "HMacMD5":
            return base64.b64encode(hmac.new(secret, data, hashlib.md5).digest()).decode("UTF-8")
        elif algorithm == "HMacSHA1":
            return base64.b64encode(hmac.new(secret, data, hashlib.sha1).digest()).decode("UTF-8")
        elif algorithm == "HMacSHA256":
            return base64.b64encode(hmac.new(secret, data, hashlib.sha256).digest()).decode("UTF-8")
        elif algorithm == "HMacSHA512":
            return base64.b64encode(hmac.new(secret, data, hashlib.sha512).digest()).decode("UTF-8")
        raise NotImplementedError("Algorithm " + algorithm + " not supported yet")

    def send_request(self, api_path: str, body_data):
        """
        发起京东物流 API 请求 (100% 对齐官方 urllib 实现)
        :param api_path: 接口路径，如 "/ecap/v1/orders/precheck"
        :param body_data: 请求体 (可以是字典、列表，或直接传 JSON 字符串)
        :return: 响应字典
        """
        # 1. 确保请求体是严格的 JSON 字符串
        # 很多报错是因为 json.dumps 的空格问题，官方不传 separators 时默认带有空格
        if isinstance(body_data, (dict, list)):
            body_str = json.dumps(body_data, ensure_ascii=False)
        else:
            body_str = str(body_data)

        algorithm = "md5-salt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. 拼接签名明文
        content = "".join([
            self.app_secret,
            "access_token", self.access_token,
            "app_key", self.app_key,
            "method", api_path,
            "param_json", body_str,
            "timestamp", timestamp,
            "v", "2.0",
            self.app_secret
        ])

        # 3. 计算签名
        sign_str = self.sign(algorithm, content.encode("UTF-8"), self.app_secret.encode("UTF-8"))

        # 4. 构建 URL Queries
        queries = {
            "LOP-DN": self.domain,
            "app_key": self.app_key,
            "access_token": self.access_token,
            "timestamp": timestamp,
            "v": "2.0",
            "sign": sign_str,
            "algorithm": algorithm
        }

        # 5. 构建 Headers 和 URL
        offset = str(int(-time.timezone / 3600))
        headers = {
            "lop-tz": offset,
            "User-Agent": "lop-http/python3",
            "content-type": "application/json;charset=utf-8",
        }

        uri = self.base_uri + api_path
        url = uri + "?" + urlencode(queries)

        logger.info(f"【JDL发起请求】URL: {url}")
        logger.info(f"【JDL请求参数】: {body_str}")

        # 6. 使用官方的 urllib 发起请求 (避免第三方 requests 库可能导致的请求头篡改)
        opener = urllib.request.build_opener()
        http_request = urllib.request.Request(url=url, data=body_str.encode("UTF-8"), headers=headers)

        try:
            http_response = opener.open(http_request)
            resp_bytes = http_response.read()
            resp_str = resp_bytes.decode("UTF-8")

            logger.info(f"【JDL接口返回】状态码: {http_response.status} | 返回值: {resp_str}")
            return json.loads(resp_str)

        except urllib.error.HTTPError as e:
            # 捕获 HTTP 级别的错误并解析京东的报错明细
            err_str = e.read().decode("UTF-8") if getattr(e, 'read', None) else str(e)
            logger.error(f"【JDL接口报错】HTTP状态码: {e.code} | 详情: {err_str}")
            raise Exception(f"请求失败 (HTTP {e.code}): {err_str}")
        except Exception as e:
            logger.error(f"【JDL通信异常】: {str(e)}")
            raise
import requests
import time
import hashlib
import base64
import json
import uuid

# --- 基础配置 ---
# PARTNER_ID = "LSQJS1HHHWZW"
# CHECK_WORD = "zfIRMBfdRKaZiJfOea1vm40V7utd9x2z"

PARTNER_ID = "LSQJS1HHHWZW"
CHECK_WORD = "qEYqHNbhz891YuowgViGajMrpj7h8YBm"
# 根据文档 2.1 节更新生产地址
# URL = "https://sfapi-sbox.sf-express.com/std/service"
URL = "https://bspgw.sf-express.com/std/service"
def query_sf_routes_fixed():
    # 1. 业务数据 (msgData) [cite: 47, 51-54]
    biz_content = {
        "language": "zh-CN",        # 文档建议 zh-CN [cite: 25]
        "trackingType": "1",        # 1: 运单号查询 [cite: 25]
        "trackingNumber": ["SF5128360730775", "SF5109400642616"], # 最多10个
        "methodType": "1"           # 1: 标准路由 [cite: 25]
    }
    msg_data = json.dumps(biz_content, separators=(',', ':'))

    # 2. 公共请求参数
    request_id = str(uuid.uuid4()).replace("-", "") # 必传：请求唯一号
    timestamp = str(int(time.time() * 1000))        # 文档要求 long
    service_code = 'EXP_RECE_SEARCH_ROUTES'        # 接口代码

    # 3. 数字签名 (msgDigest) [cite: 23, 77]
    # 公式: Base64(MD5(msgData + timestamp + checkWord))
    origin_str = f"{msg_data}{timestamp}{CHECK_WORD}"
    md5_hash = hashlib.md5(origin_str.encode('utf-8')).digest()
    msg_digest = base64.b64encode(md5_hash).decode('utf-8')

    # 4. 构造 Form 表单负载
    payload = {
        'partnerID': PARTNER_ID,
        'requestID': request_id,    # 补齐缺失的必传字段
        'serviceCode': service_code,
        'timestamp': timestamp,
        'msgDigest': msg_digest,
        'msgData': msg_data,
        'format': 'json'
    }

    # 5. 发送请求 [cite: 16-19]
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    }

    response = requests.post(URL, data=payload, headers=headers)
    print(f"发送的 requestID: {request_id}")
    print(f"响应结果: {response.text}")
    return response.text



import json
import re


def extract_sf_logistics_info(raw_json_str):
    # 1. 解析外层JSON
    outer_data = json.loads(raw_json_str)
    # 2. 解析内层物流数据
    inner_data = json.loads(outer_data["apiResultData"])

    # 正则：提取手机号
    phone_pattern = re.compile(r'1[3-9]\d{9}')
    # 正则：提取派件人姓名（匹配【杜保奎，联系电话：...】）
    name_pattern = re.compile(r'【([^，\s]+)，(联系电话|电话)：')

    result = []
    route_resps = inner_data["msgData"]["routeResps"]

    for resp in route_resps:
        mail_no = resp["mailNo"]
        for route in resp["routes"]:
            accept_time = route["acceptTime"]
            accept_address = route["acceptAddress"]
            status = f"{route['firstStatusName']}({route['secondaryStatusName']})"
            remark = route["remark"]

            # 提取电话
            phone = phone_pattern.search(remark).group() if phone_pattern.search(remark) else None
            # 提取派件联系人
            contact = name_pattern.search(remark).group(1) if name_pattern.search(remark) else None

            result.append({
                "运单号": mail_no,
                "时间": accept_time,
                "地点": accept_address,
                "物流状态": status,
                "派件联系人": contact,
                "联系电话": phone
            })
    return result


# 执行提取并打印结果
if __name__ == "__main__":
    raw_data = query_sf_routes_fixed()
    logistics_info = extract_sf_logistics_info(raw_data)
    # 格式化打印提取结果
    print("=== 顺丰物流关键信息提取结果 ===")
    for idx, info in enumerate(logistics_info, 1):
        print(f"\n【轨迹{idx}】")
        for key, value in info.items():
            print(f"{key}：{value}")
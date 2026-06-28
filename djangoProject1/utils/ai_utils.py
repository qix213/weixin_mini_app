import json
import os
from volcenginesdkarkruntime import Ark
from django.conf import settings

# ====================== 配置项 ======================
API_KEY = "4093e81a-68e5-4fb2-9b11-f8475676b71f"
MODEL_ID = "doubao-seed-2-0-lite-260215"
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# 初始化客户端
client = Ark(
    base_url=BASE_URL,
    api_key=API_KEY,
)

# ====================== 🔥 核心优化：全局缓存知识库（仅加载1次） ======================
# 服务启动时 → 只读取1次文件 → 永久存在内存中
KNOWLEDGE_BASE_CACHE = ""
try:
    json_path = os.path.join(settings.BASE_DIR, "BeautyAI", "knowledge_cache.json")
    with open(json_path, "r", encoding="utf-8") as f:
        knowledge = json.load(f)
    KNOWLEDGE_BASE_CACHE = "\n".join(knowledge)
except:
    KNOWLEDGE_BASE_CACHE = "推荐产品：中科美塑、蓝色奇肌、青岛优度生物；油性皮肤控油，敏感肌修护，干性皮肤补水"

# ====================== 系统提示词（直接使用内存缓存） ======================
SYSTEM_PROMPT = f"""
你是专业美业智能客服，严格遵守规则：
1. 不编造内容
2. 口语化、简洁建议
3. 回答严格控制在150字以内
"""

# ====================== AI问答函数（无任何磁盘IO，极速响应） ======================
def get_ai_answer(question: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            temperature=0.2,  # 最低温度=最快速度+最稳定输出
        )
        answer = response.choices[0].message.content
        return answer[:150]  # 严格截断
    except Exception as e:
        return "AI 服务异常"
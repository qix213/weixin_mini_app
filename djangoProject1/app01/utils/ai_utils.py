import requests
from volcenginesdkarkruntime import Ark

# ====================== 配置项 ======================
# 1. 专业大模型配置（云端扣费版 - 豆包）
ARK_API_KEY = "4093e81a-68e5-4fb2-9b11-f8475676b71f"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
PRO_MODEL_ID = "doubao-seed-2-0-lite-260215"

# 2. 快速小模型配置（本地免费版 - Ollama Qwen）
OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"
LITE_MODEL_ID = "qwen2.5:3b"

# 初始化大模型客户端
client = Ark(
    base_url=ARK_BASE_URL,
    api_key=ARK_API_KEY,
)

# ====================== 系统提示词 ======================
SYSTEM_PROMPT = """
你是专业美业智能客服，严格遵守规则：
1. 不编造内容
2. 只回答美容、护肤行业相关问题，其他问题一概回答：“这个问题我不知道呢，我只能回答美容、护肤相关问题。”
3. 回答严格控制在150字以内
4. 语气拟人化，专业，温柔，善解人意
"""


# ====================== AI问答函数（混合双擎） ======================
def get_ai_answer(question: str, model_type: str = "lite") -> dict:
    """
    请求 AI 并返回结果
    :param question: 用户提问
    :param model_type: 'lite' (本地Qwen免费) 或 'pro' (云端Doubao扣费)
    :return: dict 包含 'status', 'answer' 和 'total_tokens' (lite固定为0)
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    if model_type == "pro":
        # ---------------- 调用专业大模型 (Doubao) ----------------
        try:
            response = client.chat.completions.create(
                model=PRO_MODEL_ID,
                messages=messages,
                temperature=0.2,
            )
            answer = response.choices[0].message.content
            total_tokens = response.usage.total_tokens

            return {
                "status": "success",
                "answer": answer[:500],  # 专业版字数放宽
                "total_tokens": total_tokens  # 返回实际消耗，用于扣除积分
            }
        except Exception as e:
            print(f"Doubao 接口调用失败: {e}")
            return {"status": "error", "answer": "专业护肤专家正在休息中，请稍后再试哦~", "total_tokens": 0}

    else:
        # ---------------- 调用快速小模型 (Ollama Qwen2.5:3b) ----------------
        try:
            payload = {
                "model": LITE_MODEL_ID,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.2
                }
            }
            # 发送请求给本地 Ollama
            res = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()

            answer = data.get("message", {}).get("content", "")

            # 🚀 核心修改：本地小模型免费使用，强制将 token 消耗设为 0
            return {
                "status": "success",
                "answer": answer[:150],  # 快速版严格截断
                "total_tokens": 0
            }
        except Exception as e:
            print(f"Ollama 接口调用失败: {e}")
            return {"status": "error", "answer": "快速小助手跑丢了，请稍后再试哦~", "total_tokens": 0}
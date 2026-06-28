import os
import django

# 🌟 已经为你自动替换为你的项目配置路径
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject1.settings')
django.setup()

from app01.models import ExamQuestion


def add_dermatology_questions():
    # 统一指定分类为：1 (皮肤学)
    course_type_id = 1

    mock_data = [
        # ================= 单选题 =================
        {
            "question": "皮肤由外向内，大致可以分为哪三层结构？",
            "question_type": 1,
            "option_a": "角质层、透明层、颗粒层",
            "option_b": "表皮层、真皮层、皮下组织",
            "option_c": "真皮层、基底层、脂肪层",
            "option_d": "表皮层、肌肉层、骨骼层",
            "answer": "B",
            "explanation": "皮肤是人体最大的器官，由外向内分为表皮层、真皮层和皮下组织。角质层、透明层等属于表皮层的细分。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "在表皮层中，负责细胞不断分裂增生、产生新细胞的是哪一层？",
            "question_type": 1,
            "option_a": "角质层",
            "option_b": "透明层",
            "option_c": "颗粒层",
            "option_d": "基底层",
            "answer": "D",
            "explanation": "基底层位于表皮最深处，是表皮细胞的“生发中心”，不断分裂产生新生细胞并向上推移。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "正常健康的成年人，表皮细胞的新陈代谢周期（即皮肤更新周期）大约是多久？",
            "question_type": 1,
            "option_a": "7天",
            "option_b": "14天",
            "option_c": "28天",
            "option_d": "60天",
            "answer": "C",
            "explanation": "健康皮肤的更新周期约为28天（基底细胞上行到角质层约14天，在角质层停留脱落约14天）。随着年龄增长，这个周期会变长。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "紫外线中能穿透云层和玻璃，直达真皮层，导致皮肤“光老化”（产生皱纹、松弛）的主要波段是？",
            "question_type": 1,
            "option_a": "UVC (短波)",
            "option_b": "UVB (中波)",
            "option_c": "UVA (长波)",
            "option_d": "蓝光",
            "answer": "C",
            "explanation": "UVA穿透力极强，能直达真皮层破坏胶原蛋白和弹力纤维，是导致皮肤老化（Aging）的主要元凶；而UVB主要导致皮肤晒伤（Burn）。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },

        # ================= 多选题 =================
        {
            "question": "皮脂膜是皮肤的第一道天然屏障，它主要由以下哪些成分混合而成？（多选题）",
            "question_type": 2,
            "option_a": "皮脂腺分泌的皮脂",
            "option_b": "汗腺分泌的汗液",
            "option_c": "脱落的角质细胞",
            "option_d": "真皮层的胶原蛋白",
            "answer": "A,B,C",
            "explanation": "皮脂膜是一层弱酸性的保护膜，主要由皮脂、汗液以及少量脱落的角质细胞乳化混合而成。胶原蛋白存在于深层的真皮层中。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "真皮层主要由哪些成分构成，它们共同决定了皮肤的弹性和紧致度？（多选题）",
            "question_type": 2,
            "option_a": "胶原纤维",
            "option_b": "弹力纤维",
            "option_c": "基质（如透明质酸）",
            "option_d": "黑色素细胞",
            "answer": "A,B,C",
            "explanation": "真皮层主要由胶原纤维（提供支撑力）、弹力纤维（提供弹性）和基质（透明质酸，提供水分）组成。黑色素细胞位于表皮的基底层。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "健康的角质层（砖墙结构）具有以下哪些重要生理功能？（多选题）",
            "question_type": 2,
            "option_a": "保水锁水，防止体内水分大量散失",
            "option_b": "抵御外界物理和化学物质的刺激",
            "option_c": "阻挡部分外界微生物的入侵",
            "option_d": "分泌大量的黑色素",
            "answer": "A,B,C",
            "explanation": "角质层犹如一堵“砖墙”，起到极佳的物理和化学防护作用，且能锁住水分。分泌黑色素是基底层黑色素细胞的工作。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },

        # ================= 判断题 =================
        {
            "question": "黑色素细胞产生黑色素的初衷，是为了像一把“遮阳伞”一样，保护皮肤深层细胞的DNA免受紫外线的严重伤害。（判断题）",
            "question_type": 3,
            "option_a": "对",
            "option_b": "错",
            "option_c": "",
            "option_d": "",
            "answer": "A",
            "explanation": "正确。黑色素的形成其实是皮肤的一种自我保护防御机制，防止紫外线进一步长驱直入破坏细胞核变异。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "皮肤出油越多的地方，说明皮肤内部的水分极其充足，日常护理时不需要再进行任何补水保湿工作。（判断题）",
            "question_type": 3,
            "option_a": "对",
            "option_b": "错",
            "option_c": "",
            "option_d": "",
            "answer": "B",
            "explanation": "错误。很多时候过度出油是因为皮肤内部极度缺水，大脑接收到缺水信号后，指令皮脂腺分泌更多油脂来试图“锁水”，这就是典型的“外油内干”代偿性出油。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        },
        {
            "question": "敏感肌的根本原因通常是“砖墙结构”受损，即角质细胞（砖块）和细胞间脂质（灰浆）流失，导致皮肤屏障功能严重下降。（判断题）",
            "question_type": 3,
            "option_a": "对",
            "option_b": "错",
            "option_c": "",
            "option_d": "",
            "answer": "A",
            "explanation": "正确。屏障受损后，外界刺激物长驱直入引发炎症，内部水分则迅速蒸发，从而导致泛红、刺痛、干绷等敏感症状。",
            "score": 10,
            "course_type": course_type_id,
            "is_active": True
        }
    ]

    print(f"正在向分类【皮肤学(course_type={course_type_id})】注入题库...")

    # 防止重复执行时重复写入相同题目，先做个简单的清理（可选）
    ExamQuestion.objects.filter(question__contains="表皮细胞的新陈代谢周期").delete()
    ExamQuestion.objects.filter(question__contains="紫外线中能穿透云层").delete()

    success_count = 0
    for item_data in mock_data:
        # 为了防止完全重复，用 question 查重
        if not ExamQuestion.objects.filter(question=item_data["question"]).exists():
            ExamQuestion.objects.create(**item_data)
            success_count += 1
            print(f"✅ 成功写入题目: {item_data['question'][:20]}...")
        else:
            print(f"⚠️ 题目已存在，跳过: {item_data['question'][:20]}...")

    print(f"🎉 恭喜！成功新增 {success_count} 道【皮肤学】专业测试题，总分 100 分！")


if __name__ == '__main__':
    add_dermatology_questions()
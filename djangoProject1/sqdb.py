# fix_db.py
import sqlite3

# 连接项目的 SQLite 数据库（自动匹配你的文件）
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

try:
    # 核心：给 app01_user 表添加缺失的 parent_user_id 字段
    # 完全匹配你的模型：整数、允许为空、外键自关联、删除置空
    sql = """
    ALTER TABLE app01_user 
    ADD COLUMN parent_user_id INTEGER NULL 
    REFERENCES app01_user(id) 
    ON DELETE SET NULL;
    """
    cursor.execute(sql)
    conn.commit()
    print("✅ 修复成功！已自动添加 parent_user_id 字段")

except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ 字段已存在，无需修复")
    else:
        print(f"❌ 修复失败：{e}")

finally:
    # 关闭数据库连接
    cursor.close()
    conn.close()
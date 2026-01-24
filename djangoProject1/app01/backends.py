# app01/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

# 获取自定义 User 模型
User = get_user_model()

class NicknameAuthBackend(ModelBackend):
    """
    自定义认证后端：支持通过昵称登录
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # 关键：通过 nickname 字段查询用户（替换默认的 username/email）
            # 若需同时支持手机号/昵称登录，可改为 Q(nickname=username) | Q(phone=username)
            user = User.objects.get(Q(nickname=username))
            # 验证密码是否正确（Django 自带密码校验）
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            # 无该用户时，返回 None（认证失败）
            return None
        except User.MultipleObjectsReturned:
            # 存在多个相同昵称用户时（应避免，昵称需唯一），返回第一个
            user = User.objects.filter(Q(nickname=username)).first()
            if user.check_password(password):
                return user
        return None
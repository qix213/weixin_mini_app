# permissions.py
from rest_framework.permissions import BasePermission

class IsFinanceUser(BasePermission):
    """
    自定义权限：仅限财务人员访问
    """
    def has_permission(self, request, view):
        # 假设你的 User 表里有 is_finance 字段，或者通过所在的分组/角色判断
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'is_finance', False))
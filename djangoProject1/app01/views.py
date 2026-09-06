# ===================== 1. Python 标准库 =====================
import base64
import hashlib
import hmac
import json
import logging
import math
import random
import re, os
import time
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from django.db.models import Q
# ===================== 2. 第三方库 =====================
import requests
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import AcsRequest

# ===================== 3. Django 核心组件 =====================
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.core.files.storage import default_storage
# ===================== 4. Django REST Framework (DRF) 相关 =====================
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.mixins import (
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser

# ===================== 5. 本地应用导入 =====================
# 工具类与表单
from .forms import ExpressCreateForm
from .utils.ai_utils import get_ai_answer
from .utils.jd_logistics import JDLClient
from .services import (calculate_and_grant_commission, calculate_offline_commission,
                       pay_order_with_wallet, handle_recharge_success ,grant_member_assets)
# 数据模型 (Models & Constants)
from .models import (
    Address, AIChatMessage, AIChatSession, Area, Banner, Cart, Category,
    Coupon, ExamQuestion, ExamRecord, ExpressLogistics,
    Goods, Index_Annonce, Notice, Order, OrderItem, PointsRecord,
    Recipient, SF_STATUS_MAP, StoreSenderAddress, OfflineCertification,
    StudyCheckIn, User, UserCoupon, VideoCourse, VideoWatchLog, Welcome,
    UpgradeOrder,MemberPrivilege, WithdrawRecord, CommissionRecord,
    UserWallet, WalletTransaction, RechargeActivity, RechargeOrder
)

# 序列化器 (Serializers)
from .serializer import (
    AddressSerializer, BannerSerializer, BenefitSerializer, CartAddSerializer,
    CartSerializer, CategorySerializer,
    ExamQuestionSerializer, ExamRecordSerializer, GoodsSerializer,
    IndexSerializer, MemberInfoSerializer, NoticeSerializer,
    OrderAddSerializer, PointsRecordSerializer, RecipientSerializer,
    RegisterSerializer, StudyCheckInSerializer,
    UserCouponSerializer, UserCouponStatsSerializer, UserProfileSerializer,
    VideoCourseSerializer
)

# 全局日志配置
logger = logging.getLogger(__name__)
# 👇 定义全局基础URL（统一调用）
BASE_URL = settings.SERVER_BASE_URL

# 阿里云短信配置
ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
REGION_ID = "cn-hangzhou"
client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION_ID)

def find_root_enterprise(user):
    """
    自底向上追溯：通过 parent_user 链条，寻找最近的顶级 Ta创+ (user_type == 5)
    """
    if not user:
        return None

    # 防止死循环的安全计数器（最多追溯20层）
    visited = set()
    current_gap = user

    while current_gap and len(visited) < 20:
        if current_gap.pk in visited:
            break  # 发现循环引用，安全退出
        visited.add(current_gap.pk)

        # 如果当前节点自己就是 Ta创+，直接返回
        if getattr(current_gap, 'user_type', 0) == 5:
            return current_gap

        # 否则继续往上找
        current_gap = getattr(current_gap, 'parent_user', None)

    return None

def wx_get_openid_and_phone(login_code, phone_code):
    """
    统一的微信授权解析：用code换openid + 解密手机号
    带access_token缓存，全面加固网络与错误校验
    """
    appid = settings.WECHAT_PAY['APPID']
    secret = settings.WECHAT_PAY['APP_SECRET']  # 确保你的 settings 里配置了这个名字

    # 1. 换openid
    session_url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": appid,
        "secret": secret,
        "js_code": login_code,
        "grant_type": "authorization_code"
    }
    try:
        session_res = requests.get(session_url, params=params, timeout=10).json()
    except Exception as e:
        logger.error(f"【微信登录】请求 jscode2session 网络异常: {str(e)}")
        raise ValueError("微信服务器连接超时，请稍后重试")

    # 严格校验微信返回的错误码
    if 'errcode' in session_res and session_res['errcode'] != 0:
        logger.error(f"【微信登录】jscode2session 返回业务错误: {session_res}")
        raise ValueError(f"微信登录失败: {session_res.get('errmsg')}")

    openid = session_res.get('openid')
    if not openid:
        logger.error(f"【微信登录】微信未返回 openid: {session_res}")
        raise ValueError("微信返回数据缺失唯一标识")

    # 2. 取access_token（缓存7000秒）
    access_token = cache.get('wx_access_token')
    if not access_token:
        token_url = "https://api.weixin.qq.com/cgi-bin/token"
        token_params = {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret
        }
        try:
            token_res = requests.get(token_url, params=token_params, timeout=10).json()
        except Exception as e:
            logger.error(f"【微信Token】请求 access_token 网络异常: {str(e)}")
            raise ValueError("获取微信全局凭证失败，网络异常")

        if 'errcode' in token_res and token_res['errcode'] != 0:
            logger.error(f"【微信Token】获取 access_token 返回业务错误: {token_res}")
            raise ValueError(f"获取微信凭证失败: {token_res.get('errmsg')}")

        access_token = token_res.get('access_token')
        if not access_token:
            raise ValueError("微信全局凭证数据缺失")

        # 写入缓存
        cache.set('wx_access_token', access_token, timeout=7000)

    # 3. 解密手机号
    phone_url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
    try:
        phone_res = requests.post(phone_url, json={"code": phone_code}, timeout=10).json()
    except Exception as e:
        logger.error(f"【微信手机号】请求 getuserphonenumber 网络异常: {str(e)}")
        raise ValueError("解析手机号网络超时")

    if phone_res.get('errcode') != 0:
        logger.error(f"【微信手机号】手机号解析返回业务错误: {phone_res}")
        # ⚠️ 踩坑提示：如果 access_token 过期，微信会返回 40001。
        # 此时可以清理缓存：cache.delete('wx_access_token')，这里抛出异常让用户重试即可
        if phone_res.get('errcode') == 40001:
            cache.delete('wx_access_token')
        raise ValueError(f"手机号解密失败: {phone_res.get('errmsg')}")

    phone_info = phone_res.get('phone_info')
    if not phone_info or 'phoneNumber' not in phone_info:
        logger.error(f"【微信手机号】结构异常: {phone_res}")
        raise ValueError("微信手机号结构解析异常")

    real_phone = phone_info['phoneNumber']
    return openid, real_phone

def create_register_user(data):
    """
    统一的用户注册核心逻辑（适配全新 6 档会员体系与默认 1000 积分）
    """
    login_code = data.get('login_code')
    phone_code = data.get('phone_code')
    openid = data.get('openid', None)

    # ==============================================================
    # 模拟支付核心修改：放行微信服务器通信，无授权码时改用前端模拟参数
    # ==============================================================
    if login_code and phone_code:
        try:
            wechat_openid, real_phone = wx_get_openid_and_phone(login_code, phone_code)
            data['phone'] = real_phone
            data['username'] = real_phone
            openid = wechat_openid
        except Exception as e:
            print(f"[测试提示] 微信接口请求失败，自动降级为模拟数据。原因: {str(e)}")

    if not data.get('phone'):
        import random
        mock_phone = data.get('phone', f"138{random.randint(10000000, 99999999)}")
        data['phone'] = mock_phone
        data['username'] = mock_phone

    if not openid:
        openid = f"MOCK_OPENID_{data['phone']}"

    serializer = RegisterSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    update_fields = []
    if hasattr(user, 'openid'):
        user.openid = openid
        update_fields.append('openid')

    if user.user_type > 1:
        user.expire_time = timezone.now() + timedelta(days=365)
        update_fields.append('expire_time')

    if update_fields:
        user.save(update_fields=update_fields)

    birth_date = data.get('birth_date')
    if birth_date:
        user.birth_date = birth_date
        user.last_birth_date_modify = timezone.now()
        user.save(update_fields=['birth_date', 'last_birth_date_modify'])

    # 🌟 核心更新：固定赠送 1000 注册积分
    try:
        user.add_points(
            points=1000,
            points_type=1,
            related_desc='欢迎开启仙女肌养肤之旅，赠送注册积分'
        )
    except Exception as e:
        print(f"赠送注册积分失败：{str(e)}")

    # 🌟 核心更新：对齐全新的 6 档价格体系
    amount_paid = data.get('amount')
    if not amount_paid:
        LEVEL_PRICE_MAP = {
            1: 0.00,      # 0星: 0元
            2: 980.00,    # 1星: 980元
            3: 1980.00,   # 2星: 1980元
            4: 3800.00,   # 3星: 3800元
            5: 9800.00,   # 4星: 9800元
            6: 39800.00   # 5星: 39800元
        }
        amount_paid = LEVEL_PRICE_MAP.get(int(user.user_type), 0.00)

    # 派发资产
    grant_member_assets(
        user=user,
        target_level=int(user.user_type),
        amount_paid=amount_paid,
        remark_text="新用户注册首充资产入账"
    )

    return user, None, None

# ===================== 基础视图 =====================
def index(request):
    time.sleep(1)
    return JsonResponse({'name': '嘉俊', 'sex': '男', 'age': '18'})

def welcome(request):
    res = Welcome.objects.all().order_by('-order').first()
    # ✅ 修复：使用变量，无硬编码IP
    img = f"{BASE_URL}/media/{res.img}"
    return JsonResponse({'code': 100, 'msg': '成功', 'result': img})

def get_member_privilege(request):
    """获取启用的会员权益图"""
    # 查找最新启用的那张图
    res = MemberPrivilege.objects.filter(is_active=True).first()

    if res and res.image:
        # ✅ 使用变量拼接绝对路径，与你之前的逻辑保持完全一致
        img_url = f"{BASE_URL}/media/{res.image.name}"

        return JsonResponse({
            'code': 200,
            'msg': '成功',
            'result': img_url
        })
    else:
        # 兜底：如果后台没传图，返回空字符串，让前端处理
        return JsonResponse({
            'code': 404,
            'msg': '未配置权益图',
            'result': ''
        })

def get_offline_certification(request):
    # 查找最新启用的那张图
    res = OfflineCertification.objects.filter(is_active=True).first()

    if res and res.image:
        # ✅ 使用变量拼接绝对路径，与你之前的逻辑保持完全一致
        img_url = f"{BASE_URL}/media/{res.image.name}"

        return JsonResponse({
            'code': 200,
            'msg': '成功',
            'result': img_url
        })
    else:
        # 兜底：如果后台没传图，返回空字符串，让前端处理
        return JsonResponse({
            'code': 404,
            'msg': '未配置权益图',
            'result': ''
        })
# ===================== Banner/公告视图 =====================
class BannerView(ListModelMixin, GenericViewSet):
    queryset = Banner.objects.filter(is_delete=False).order_by('order')[:5]
    permission_classes = [AllowAny]
    serializer_class = BannerSerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        notice = Notice.objects.all().order_by('create_time').first()
        serializer_notice = NoticeSerializer(instance=notice)
        return Response({'code': 100, 'msg': '成功', 'banner': res.data, 'notice': serializer_notice.data})


# ===================== 商品分类/商品视图 =====================
class CategoryView(ListModelMixin, GenericViewSet):
    permission_classes = [AllowAny]
    queryset = Category.objects.all().order_by('sort_order', 'id')
    serializer_class = CategorySerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        return Response({
            'code': 200,
            'msg': 'success',
            'data': res.data
        })

class GoodsViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [AllowAny]
    queryset = Goods.objects.all().order_by('sort_order', 'id').prefetch_related('images')
    serializer_class = GoodsSerializer

    # views.py 仅需调整 _adjust_price_for_user 方法，去掉价格覆盖
    def _adjust_price_for_user(self, request, item_data):
        # 只需要修正 point_price，不需要覆盖 member_price
        item_dict = dict(item_data)

        # 动态修正积分定价逻辑
        if item_dict.get('is_support_point_exchange'):
            # 积分定价始终参考会员价
            current_price = float(item_dict.get('member_price', 0))
            item_dict['point_price'] = int(current_price * 100)
        else:
            item_dict['point_price'] = 0

        return item_dict

    def list(self, request, *args, **kwargs):
        keyword = request.query_params.get('keyword', '')
        category_id = request.query_params.get('category_id', '')

        queryset = self.get_queryset()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        if category_id and category_id.isdigit():
            queryset = queryset.filter(category_id=int(category_id))

        self.queryset = queryset
        res = super().list(request, *args, **kwargs)

        # 拦截并处理列表数据（兼容分页和不分页两种情况）
        response_data = res.data
        if isinstance(response_data, list):
            # 不分页情况
            adjusted_data = [self._adjust_price_for_user(request, item) for item in response_data]
        elif isinstance(response_data, dict) and 'results' in response_data:
            # 分页情况
            response_data['results'] = [self._adjust_price_for_user(request, item) for item in response_data['results']]
            adjusted_data = response_data
        else:
            adjusted_data = response_data

        return Response({
            'code': 200,
            'msg': 'success',
            'data': adjusted_data
        })

    def retrieve(self, request, *args, **kwargs):
        try:
            res = super().retrieve(request, *args, **kwargs)

            # 拦截并处理单条商品数据
            adjusted_data = self._adjust_price_for_user(request, res.data)

            return Response({
                'code': 200,
                'msg': 'success',
                'data': adjusted_data
            })
        except Exception as e:
            return Response({
                'code': 404,
                'msg': '商品不存在',
                'data': {}
            })

from rest_framework import status
from .models import OfflineServiceRecord, UserOfflineProject
from .serializer import OfflineServiceRecordSerializer, UserOfflineProjectSerializer

class OfflineServiceViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OfflineServiceRecordSerializer
    queryset = OfflineServiceRecord.objects.all()

    def get_queryset(self):
        """ 权限隔离：店长(5)看所有，客户看自己 """
        user = self.request.user
        user_type = getattr(user, 'user_type', 1)

        if user_type == 5:
            queryset = OfflineServiceRecord.objects.all()
            customer_id = self.request.query_params.get('customer_id')
            if customer_id:
                queryset = queryset.filter(user_id=customer_id)
        else:
            queryset = OfflineServiceRecord.objects.filter(user=user)

        return queryset.select_related('user', 'manager', 'project').order_by('-create_time')

    @action(detail=False, methods=['get'])
    def query_assets(self, request):
        """ 【双端通用】查询用户剩余项目资产 """
        user = request.user
        user_type = getattr(user, 'user_type', 1)

        if user_type == 5:
            customer_id = request.query_params.get('customer_id')
            if customer_id:
                assets = UserOfflineProject.objects.select_related('user', 'project').filter(user_id=customer_id)
            else:
                assets = UserOfflineProject.objects.select_related('user', 'project').all()
        else:
            assets = UserOfflineProject.objects.select_related('user', 'project').filter(user=user)

        assets = assets.filter(total_times__gt=0)
        serializer = UserOfflineProjectSerializer(assets, many=True)
        return Response({"code": 200, "msg": "success", "data": serializer.data})

    @action(detail=False, methods=['post'])
    def book_appointment(self, request):
        """ 【店长端】第一步：为客户选定预约时间 """
        member_id_str = request.data.get('customer_id')
        project_id = request.data.get('project_id')
        appt_time = request.data.get('appointment_time')

        if not all([member_id_str, project_id, appt_time]):
            return Response({"code": 400, "msg": "缺少必要参数"}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            customer = User.objects.get(member_id=member_id_str)
        except User.DoesNotExist:
            return Response({"code": 404, "msg": "找不到该客户"}, status=404)

        try:
            record = OfflineServiceRecord.objects.create(
                user=customer,
                manager=request.user,
                project_id=project_id,
                appointment_time=appt_time,
                status=0  # 状态0：已预约
            )
            return Response({"code": 200, "msg": "预约成功"})
        except Exception as e:
            return Response({"code": 500, "msg": f"预约失败: {str(e)}"}, status=500)

    @action(detail=True, methods=['post'])
    def confirm_service(self, request, pk=None):
        """ 【客户端】第二步：服务完成后，客户在手机端点击确认核销 """
        customer = request.user
        try:
            with transaction.atomic():
                # 1. 锁定服务记录
                record = OfflineServiceRecord.objects.select_for_update().get(pk=pk, user=customer)

                if record.status not in [0, 1]:
                    return Response({"code": 400, "msg": "该服务记录当前状态无法进行核销确认"}, status=400)

                # 2. 锁定并获取用户资产
                asset = UserOfflineProject.objects.select_for_update().filter(
                    user=customer, project=record.project
                ).first()

                if not asset or asset.remain_times <= 0:
                    return Response({"code": 400, "msg": "您的项目剩余次数不足，确认失败"}, status=400)

                # 3. 扣减资产并推进状态至 2 (已完成)
                asset.remain_times -= 1
                asset.save(update_fields=['remain_times', 'update_time'])

                record.status = 2  # 已完成
                record.confirm_time = timezone.now()
                record.save(update_fields=['status', 'confirm_time'])

                # ==============================================
                # 🌟🌟 核心植入：触发单次核销分佣机制 🌟🌟
                # ==============================================
                calculate_offline_commission(record, asset)

                return Response({
                    "code": 200,
                    "msg": "核销成功，次数已扣减",
                    "data": {"remain_times": asset.remain_times}
                })

        except OfflineServiceRecord.DoesNotExist:
            return Response({"code": 404, "msg": "未找到对应的服务记录"}, status=404)
        except Exception as e:
            logger.error(f"确认服务接口故障: {str(e)}", exc_info=True)
            return Response({"code": 500, "msg": "服务器内部错误，核销失败"}, status=500)

    # 🌟 核心整合：直接在这里接收图片上传，不需要改 urls.py 路由
    @action(detail=False, methods=['post'], parser_classes=(MultiPartParser, FormParser))
    def upload_image(self, request):
        """ 【客户端】中间件：通用图片上传 """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"code": 400, "msg": "未接收到图片文件"}, status=400)
        try:
            ext = file_obj.name.split('.')[-1]
            filename = f"reviews/{uuid.uuid4().hex}.{ext}"
            file_path = default_storage.save(filename, file_obj)
            file_url = request.build_absolute_uri(default_storage.url(file_path))
            return Response({"code": 200, "msg": "上传成功", "data": {"url": file_url}})
        except Exception as e:
            return Response({"code": 500, "msg": f"保存失败: {str(e)}"}, status=500)

    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """ 【客户端】第三步：核销完成后提交评价 """
        customer = request.user
        rating = request.data.get('rating')
        review_content = request.data.get('review_content', '')
        review_images = request.data.get('review_images', [])

        try:
            record = OfflineServiceRecord.objects.get(pk=pk, user=customer)

            # 🌟 核心修正：核销完状态已经变成 2 了，这里必须验证等于 2！
            if record.status != 2:
                return Response({"code": 400, "msg": "请先完成项目核销确认，再进行评价"}, status=400)

            if record.rating is not None:
                return Response({"code": 400, "msg": "该次服务您已评价过，无法重复提交"}, status=400)

            if rating:
                record.rating = int(rating)
            if review_content:
                record.review_content = review_content
            if isinstance(review_images, list) and review_images:
                record.review_images = review_images

            record.review_time = timezone.now()
            record.save(update_fields=['rating', 'review_content', 'review_images', 'review_time'])

            return Response({"code": 200, "msg": "评价提交成功，感谢您的反馈！"})

        except OfflineServiceRecord.DoesNotExist:
            return Response({"code": 404, "msg": "未找到对应的服务记录"}, status=404)

    @action(detail=False, methods=['post'])
    def buy_project(self, request):
        """ 【模拟商城下发资产】（保持不变） """
        user = request.user
        goods_id = request.data.get('goods_id')
        if not goods_id:
            return Response({"code": 400, "msg": "缺少项目ID参数"}, status=400)
        try:
            project = Goods.objects.get(id=goods_id, goods_type=2)
            with transaction.atomic():
                asset, created = UserOfflineProject.objects.get_or_create(
                    user=user, project=project, defaults={'total_times': 0, 'remain_times': 0}
                )
                add_times = project.service_times if project.service_times > 0 else 1
                asset.total_times += add_times
                asset.remain_times += add_times
                asset.save(update_fields=['total_times', 'remain_times', 'update_time'])
            return Response({"code": 200, "msg": "资产下发成功", "data": {"remain_times": asset.remain_times}})
        except Goods.DoesNotExist:
            return Response({"code": 404, "msg": "该项目不存在或非线下项目"}, status=404)


from rest_framework import viewsets
from .models import CourseCategory
from .serializer import CourseCategorySerializer
class CourseCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    # 只返回启用的分类，并按排序字段从小到大排
    queryset = CourseCategory.objects.filter(is_active=True).order_by('sort_order')
    serializer_class = CourseCategorySerializer

class VideoCourseViewSet(ModelViewSet):
    queryset = VideoCourse.objects.filter(is_publish=True)
    serializer_class = VideoCourseSerializer
    permission_classes = [IsAuthenticated]

    # 🌟 核心修改 1：彻底关闭后端分页，一口气返回纯数组给前端！
    pagination_class = None

    def get_queryset(self):
        queryset = VideoCourse.objects.filter(is_publish=True)

        # 1. 标题搜索过滤
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(title__icontains=search)

        # 2. 接收前端传来的分类 ID 并过滤
        category_id = self.request.query_params.get('category', '')
        if category_id and category_id.isdigit():
            queryset = queryset.filter(category_id=int(category_id))

        # 🌟 核心修改 2：强制只按序号 (sort_order) 从小到大正序排列！
        # 完全抛弃 create_time，谁的序号小谁就排在前面
        queryset = queryset.order_by('sort_order')

        return queryset

    @action(detail=True, methods=['get'])
    def check_permission(self, request, pk=None):
        try:
            video = self.get_object()

            video_link = ""
            if video.video_url:
                raw_path = video.video_url.strip()

                if raw_path.startswith('http'):
                    video_link = raw_path
                else:
                    if not raw_path.startswith('/'):
                        raw_path = '/' + raw_path
                    video_link = f"https://video.lansik2026.com{raw_path}"

            # 🌟 增加日志：明确告诉后端，发给前端的链接到底长什么样
            logger.info(f"👉 [check_permission] ID: {pk}, 原始路径: {video.video_url}, 最终下发播放直链: {video_link}")

            return Response({
                "code": 200,
                "msg": "允许观看",
                "has_permission": True,
                "video_url": video_link
            })
        except Exception as e:
            logger.error(f"❌ check_permission接口错误：{str(e)}", exc_info=True)
            return Response({
                "code": 500,
                "msg": "获取视频失败"
            }, status=500)

    @action(detail=True, methods=['post'])
    def add_play_count(self, request, pk=None):
        try:
            video = self.get_object()
            video.play_count += 1
            video.save(update_fields=['play_count'])
            return Response({
                "code": 200,
                "msg": "播放次数更新成功",
                "play_count": video.play_count
            })
        except Exception as e:
            logger.error(f"add_play_count接口错误：{str(e)}")
            return Response({
                "code": 500,
                "msg": "播放次数更新失败"
            }, status=500)

    @action(detail=True, methods=['post'])
    def watch_start(self, request, pk=None):
        try:
            if not request.user.is_authenticated:
                return Response({
                    "code": 401,
                    "msg": "请先登录"
                }, status=status.HTTP_401_UNAUTHORIZED)

            video = self.get_object()
            log, created = VideoWatchLog.objects.get_or_create(
                user=request.user,
                video=video,
                defaults={
                    "watch_start": timezone.now(),
                    "total_watch_sec": 0,
                    "last_progress_sec": 0,
                    "is_finished": False
                }
            )

            return Response({
                "code": 200,
                "msg": "开始播放记录成功",
                "log_id": log.pk,
                "created": created
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"watch_start接口错误：{str(e)}", exc_info=True)
            return Response({
                "code": 500,
                "msg": f"服务器内部错误：{str(e)[:50]}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def watch_progress(self, request, pk=None):
        video = self.get_object()
        user = request.user
        current_time = request.data.get('current_time', 0)
        duration = video.duration or 0

        try:
            log = VideoWatchLog.objects.get(user=user, video=video)
        except VideoWatchLog.DoesNotExist:
            return Response({"code": 400, "msg": "请先调用开始播放接口"})

        last = log.total_watch_sec
        if current_time - last > 5:
            return Response({
                "code": 403,
                "msg": "检测到快进，观看无效",
                "invalid": True
            })

        log.total_watch_sec = current_time
        log.last_progress_sec = current_time
        log.save()

        progress = 0
        if duration > 0:
            progress = round(current_time / duration * 100, 2)

        return Response({
            "code": 200,
            "current": current_time,
            "duration": duration,
            "progress": progress
        })

    @action(detail=True, methods=['post'])
    def watch_finish(self, request, pk=None):
        video = self.get_object()
        user = request.user
        logger.info(f"【watch_finish】用户{user.id}，视频{pk}，视频时长：{video.duration}")

        video_duration = video.duration or 0
        if video_duration <= 0:
            try:
                log = VideoWatchLog.objects.get(user=user, video=video)
                video_duration = log.last_progress_sec or 60
            except VideoWatchLog.DoesNotExist:
                logger.error(f"【时长异常】用户{user.id}视频{pk}无观看日志，无法获取时长")
                return Response({
                    "code": 400,
                    "msg": "未检测到有效观看记录，无法领取积分"
                })

        try:
            log = VideoWatchLog.objects.get(user=user, video=video)
        except VideoWatchLog.DoesNotExist:
            return Response({
                "code": 400,
                "msg": "请先开始播放视频，再领取积分"
            })

        watch_duration = log.total_watch_sec or 0
        if watch_duration <= 0:
            return Response({
                "code": 400,
                "msg": "有效观看时长为0，无法领取积分"
            })

        completion_rate = watch_duration / video_duration
        logger.info(
            f"【完成率】用户{user.id}视频{pk}：观看{watch_duration}秒/总{video_duration}秒，完成率{completion_rate:.2f}")

        if completion_rate < 0.9:
            return Response({
                "code": 400,
                "msg": f"观看时长不足（仅完成{completion_rate * 100:.0f}%），需观看90%以上才能领取积分"
            })

        if log.point_given:
            return Response({
                "code": 200,
                "msg": "积分已发放，无需重复领取"
            })

        ok, msg = user.add_points(
            points=100,
            points_type=3,
            related_id=f"video_{video.id}",
            related_desc=f"看完《{video.title}》奖励100积分"
        )
        if not ok:
            logger.error(f"【积分发放失败】用户{user.id}视频{pk}：{msg}")
            return Response({
                "code": 500,
                "msg": f"积分发放失败：{msg}"
            })

        log.is_finished = True
        log.point_given = True
        log.watch_end = timezone.now()
        log.save()

        user.refresh_from_db()
        return Response({
            "code": 200,
            "msg": "视频观看完成，积分+100！",
            "current_points": user.points
        })

# ===================== 登录/注册视图 =====================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['nickname'] = getattr(user, 'nickname', '')
        token['star_level'] = getattr(user, 'star_level', 0)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        return {
          "code": 200,
          "msg": "登陆成功",
          "data": {
            "access": data["access"],
            "refresh": data["refresh"],
            "user_info": {
              'nickname': user.nickname,
              'star_level': user.star_level,
              'points': user.points,
              'coupon_count': user.coupon_count,
              'member_id': user.member_id,
              'user_type': user.user_type,
            }
          }
        }

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterPreCheckView(APIView):
    """
    注册前置校验接口：
    1. 校验推荐人是否存在
    2. 立即解密微信手机号（防止 code 过期）
    """
    authentication_classes = []
    permission_classes = []

    def get_wx_access_token(self):
        """
        获取微信接口调用凭证（Production 最终版）
        包含 7000秒 缓存机制，防止触发微信 API 调用频率上限
        """
        # 1. 尝试从缓存读取，如果有且未过期，直接返回（速度最快）
        access_token = cache.get('wx_access_token')
        if access_token:
            return access_token

        # 2. 从字典中精准提取正确的配置
        appid = settings.WECHAT_PAY.get("APPID")
        secret = settings.WECHAT_PAY.get("APP_SECRET")

        # 防御性校验：防止手滑删了配置
        if not appid or not secret:
            raise Exception("后端配置丢失：无法在 WECHAT_PAY 中找到 APPID 或 APP_SECRET")

        url = (
            f"https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential&appid={appid}&secret={secret}"
        )

        try:
            # 3. 发送网络请求
            res = requests.get(url, timeout=10).json()

            # 4. 严格校验返回结果
            if 'access_token' not in res:
                raise Exception(f"微信拒绝下发Token: {res.get('errcode')} - {res.get('errmsg')}")

            new_token = res['access_token']

            # 5. 写入缓存。微信 Token 的实际有效期是 7200 秒（2小时）。
            # 我们故意设置 7000 秒，留出 200 秒的提前量去刷新，保证业务绝对不会因为 Token 突然过期而中断。
            cache.set('wx_access_token', new_token, timeout=7000)

            return new_token

        except requests.exceptions.RequestException as e:
            # 捕获类似网络超时、断网等底层异常
            raise Exception(f"请求微信服务器网络异常: {str(e)}")

    def post(self, request):
        recommender_id = request.data.get('recommender_id')
        phone_code = request.data.get('phone_code')
        nickname = request.data.get('nickname')  # 🌟 1. 接收前端传来的昵称

        # ==========================================
        # 🌟 2. 前置校验：昵称查重拦截
        # ==========================================
        if nickname:
            # 假设你的模型是 User，根据你的实际模型名调整
            if User.objects.filter(nickname=nickname).exists():
                return Response({'code': 400, 'msg': '该昵称已被使用，请换一个更特别的名字哦~'})
        # 1. 严格校验推荐人是否存在 (假设你的 User 表用 member_id 或类似字段标识推荐码)
        if recommender_id:

            if not User.objects.filter(member_id=recommender_id).exists():
                return Response({'code': 400, 'msg': '填写的推荐人ID不存在，请核对后再试'})

        if not phone_code:
            return Response({'code': 400, 'msg': '缺少微信手机号授权凭证'})

        # 2. 立即调用微信接口，把 code 换成真实手机号
        try:
            access_token = self.get_wx_access_token()
            url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"

            # print(f"【DEBUG】正在请求解密手机号，使用的 code: {phone_code}")
            res = requests.post(url, json={"code": phone_code}, timeout=10).json()
            # print(f"【DEBUG】手机号解密接口返回结果: {res}")

            if res.get('errcode') != 0:
                # 🌟 把详细报错直接通过接口返回给前端！
                return Response({'code': 400, 'msg': f"解密失败: {res.get('errcode')} - {res.get('errmsg')}"})

            real_phone = res['phone_info']['phoneNumber']

            # 3. 校验该手机号是否已经注册过（防重复交钱）
            if User.objects.filter(username=real_phone).exists():
                return Response({'code': 400, 'msg': '该微信手机号已经注册过会员，请直接登录'})

            # 一切完美，把真实的手机号返回给前端
            return Response({
                'code': 200,
                'msg': '校验通过',
                'data': {'real_phone': real_phone}
            })

        except Exception as e:
            return Response({'code': 500, 'msg': f'服务器繁忙，校验失败: {str(e)}'})

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if isinstance(request.data, dict):
            data = request.data.copy()
        else:
            data = request.data.dict() if hasattr(request.data, 'dict') else request.data.copy()

            # ==============================================================
            # 🌟 模拟支付核心修改：注释掉微信真实收费/缴费状态拦截拦截
            # ==============================================================
            # is_paid = data.get('is_paid', False)
            # if user_type > 1 and str(is_paid).lower() not in ['true', '1']:
            #     return Response({
            #         'code': 402,
            #         'msg': '尚未完成支付，无法注册付费会员！',
            #         'data': None
            #     }, status=400)

            # 强制在数据中注入支付完成标记，供后续逻辑放心使用
            data['is_paid'] = True

        try:
            user, access, refresh = create_register_user(data)

            response_data = {
                'nickname': user.nickname,
                'member_id': user.member_id,
                'user_type': user.user_type,
                'parent_member_id': user.parent_user.member_id if user.parent_user else None,
                'coupon_count': user.get_coupon_stats()['total'],
                'points': user.points,
                'wallet_balance': float(user.wallet_balance)  # 🌟 顺手把刚注入的钱包余额回传给前端
            }

            return Response({
                'code': 200,
                'msg': '注册成功',
                'access': access,
                'refresh': refresh,
                'data': response_data
            }, status=201)

        except Exception as e:
            logger.error(f"注册失败: {str(e)}")
            return Response({'code': 400, 'msg': f'注册失败：{str(e)}', 'data': None}, status=400)


class WechatLoginView(APIView):
    """
    微信一键授权快捷登录专用接口
    """
    permission_classes = [AllowAny]

    def post(self, request):
        login_code = request.data.get('login_code')
        phone_code = request.data.get('phone_code')

        if not login_code or not phone_code:
            return Response({'code': 400, 'msg': '缺少微信授权参数', 'data': None})

        try:

            app_id = settings.WECHAT_PAY['APPID']
            app_secret = settings.WECHAT_PAY['APP_SECRET']

            # 1. 换取 AccessToken（利用缓存防超频）
            access_token = cache.get('wx_access_token')
            if not access_token:
                token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
                token_res = requests.get(token_url).json()
                access_token = token_res.get('access_token')
                if access_token:
                    cache.set('wx_access_token', access_token, timeout=7000)

            if not access_token:
                return Response({'code': 500, 'msg': '无法获取微信鉴权Token'})

            # 2. 解密真实手机号
            phone_url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
            phone_res = requests.post(phone_url, json={"code": phone_code}).json()

            if phone_res.get('errcode') == 0:
                real_phone = phone_res['phone_info']['phoneNumber']
            else:
                return Response({'code': 400, 'msg': "微信手机号授权已过期，请重新点击"})

            # 3. 用手机号查数据库
            try:
                user = User.objects.get(phone=real_phone, is_active=True)

                # ========== 新增：登录成功自动补绑 openid，后续登录更稳定 ==========
                session_url = f"https://api.weixin.qq.com/sns/jscode2session?appid={app_id}&secret={app_secret}&js_code={login_code}&grant_type=authorization_code"
                session_res = requests.get(session_url).json()
                openid = session_res.get('openid')
                if openid and not user.openid:
                    user.openid = openid
                    user.save(update_fields=['openid'])

                # 查到用户，直接签发登录 Token
                refresh = RefreshToken.for_user(user)
                return Response({
                    'code': 200,
                    'msg': '登录成功',
                    'data': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                        'user_info': {
                            'phone': user.phone,
                            'nickname': user.nickname,
                            'user_type': user.user_type,
                            'star_level': getattr(user, 'star_level', 0),
                            'member_id': user.member_id,
                            'points': user.points
                        }
                    }
                })

            except User.DoesNotExist:
                # 查无此人，返回 404，前端自动跳注册页
                return Response({
                    'code': 404,
                    'msg': '用户未注册，请先注册',
                    'data': None
                })

        except Exception as e:
            logger.error(f"微信快捷登录解析异常: {str(e)}")
            return Response({'code': 500, 'msg': '服务器解析异常，请稍后重试'}, status=500)

# ===================== 会员相关视图 =====================
class DebugIsAuthenticated(IsAuthenticated):
    def has_permission(self, request, view):
        print("===== 权限校验调试日志 =====")
        print("当前请求用户是否为匿名用户：", request.user.is_anonymous)
        print("当前请求用户对象：", request.user)
        # print("当前请求 Authorization 头：", request.META.get('HTTP_AUTHORIZATION', '无'))
        print("===========================")

        permission_result = super().has_permission(request, view)
        print("权限校验结果（True=通过，False=失败）：", permission_result)
        return permission_result


class MemberInfoView(APIView):
    permission_classes = [DebugIsAuthenticated]

    def get(self, request):
        try:
            print('当前登录用户：', request.user.nickname)
            request.user.issue_birthday_coupon()
            serializer = MemberInfoSerializer(request.user)

            coupon_count = UserCoupon.objects.filter(user=request.user).count()
            points = getattr(request.user, 'points', 0)

            response_data = serializer.data
            response_data['coupon_count'] = coupon_count
            response_data['points'] = points
            response_data['birth_date'] = request.user.birth_date
            response_data['can_use_ai'] = getattr(request.user, 'can_use_ai', False)
            if request.user.avatar:
                response_data['avatar_url'] = request.build_absolute_uri(request.user.avatar.url)
            else:
                response_data['avatar_url'] = ''  # 没有头像返回空字符串，前端会自动兜底
            return Response({
                'code': 200,
                'msg': '获取会员信息成功',
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print('获取会员信息异常：', str(e))
            return Response({
                'code': 500,
                'msg': f'获取会员信息失败：{str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateBirthDateView(APIView):
    """
    修改生日接口（包含一年只能修改一次的校验）
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_birth_date = request.data.get('birth_date')
        if not new_birth_date:
            return Response({"code": 400, "msg": "请提供生日日期", "data": None})

        # 调用我们在模型中写好的核心风控方法
        success, msg = request.user.update_birth_date(new_birth_date)

        if success:
            return Response({
                "code": 200,
                "msg": msg,
                "data": {"birth_date": request.user.birth_date}
            })
        else:
            return Response({
                "code": 403,  # 拒绝修改
                "msg": msg,
                "data": None
            })


class SubUserConsumeView(APIView):
    """
    【Ta创+ 工作台】核心大老板接口：
    一键获取线下所有无限极子孙产生的 线上商品单 与 线下服务核销订单（高兼容、无漏洞版）。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_user = request.user
        sync_logistics = request.query_params.get('sync_logistics', '0')

        # 权限防线
        if getattr(current_user, 'user_type', 0) < 5:
            return Response({
                'code': 403,
                'msg': '您不是顶级Ta创+账户，无权查看履约中心',
                'data': []
            }, status=status.HTTP_403_FORBIDDEN)

        # ======================================================================
        # 🌟 核心修复：通过 Q 对象执行双轨合并
        # 满足 (新订单已经打桩的) 或者 (老订单用户归属的) 的全部订单，状态包含 1, 2, 3, 4
        # ======================================================================
        all_orders = Order.objects.filter(
            Q(fulfill_by=current_user) | Q(user__root_enterprise=current_user),
            is_delete=False,
            status__in=[1, 2, 3, 4]  # 1待发货/备货中，2待收货/待取货，3已完成，4已取消
        ).select_related('user', 'pick_up_store', 'address').order_by('-create_time')

        # ======================================================================
        # 📦 数据格式化
        # ======================================================================
        formatted_orders = []
        for order in all_orders:
            buyer = order.user

            order_info = {
                'id': order.pk,
                'order_sn': order.order_sn,
                'total_price': float(order.total_price),
                'actual_pay_money': float(order.actual_pay_money) if order.actual_pay_money else float(
                    order.total_price),
                'status': order.status,
                'status_name': getattr(order, 'status_name', order.get_status_display() if hasattr(order,
                                                                                                   'get_status_display') else '未知状态'),
                'delivery_type': order.delivery_type,
                'delivery_type_name': order.get_delivery_type_display() if hasattr(order,
                                                                                   'get_delivery_type_display') else '',

                # 🌟 修正笔误：对齐你数据库里真实的字段名 goods_names
                'goods_names': order.goods_names,
                'goods_count': order.goods_count if hasattr(order, 'goods_count') else 1,
                'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else '',
                'pick_up_store_name': order.pick_up_store.name if order.pick_up_store else None,

                'buyer_info': {
                    'id': buyer.id if buyer else None,
                    'nickname': buyer.nickname if buyer else '未知买家',
                    'phone': buyer.phone if buyer else '',
                    'member_id': buyer.member_id if buyer else ''
                }
            }

            # ===================== 物流实时状态机自动同步 =====================
            if sync_logistics == '1' and getattr(order, 'jd_waybill_code', None) and order.status not in [3, 4]:
                latest_express = ExpressLogistics.objects.filter(order_sn=order.order_sn).order_by('-id').first()

                if latest_express:
                    status_name = latest_express.logistics_status_name or ''
                    remark = latest_express.remark or ''
                    combined_text = status_name + remark

                    if any(kw in combined_text for kw in ['签收', '完成', '妥投']):
                        if order.status != 3:
                            order.status = 3
                            order.save(update_fields=['status'])
                            order_info['status'] = 3
                            order_info['status_name'] = '已完成'

                    elif any(kw in combined_text for kw in ['揽收', '运输', '派送', '发往', '发车', '在途']):
                        if order.status == 1:
                            order.status = 2
                            order.save(update_fields=['status'])
                            order_info['status'] = 2
                            order_info['status_name'] = '待收货'

            formatted_orders.append(order_info)

        return Response({
            'code': 200,
            'msg': '获取履约及发货管理订单成功',
            'data': formatted_orders
        }, status=status.HTTP_200_OK)


class BenefitViewSet(GenericViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = BenefitSerializer

    def list(self, request):
        user_type = request.query_params.get('user_type')
        if not user_type or not user_type.isdigit():
            return Response(
                {'code': 400, 'msg': '请指定有效用户类型（1-蓝朋友0星，2-蓝朋友1星，3-蓝朋友2星， 4-蓝朋友3星，5-TA创+）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user_type = int(user_type)

        # 🌟 核心修改：完全同步最新的0-3星体系及Ta创+价格
        fee_map = {1: "0元", 2: "980元", 3: "3980元", 4: "9800元", 5: "5.98万元"}

        benefit_map = {
            1: [
                "注册门槛：0元",
                "专享价格：零售价",
                "裂变权益：0%",
                "其他权益：关注小程序完成注册即可体验基础服务。"
            ],
            2: [
                "注册储值：980元",
                "专享价格：会员价",
                "裂变权益：0%",
                "其他权益：解锁会员专属星价与积分换礼资格。"
            ],
            3: [
                "注册储值：3980元",
                "专享价格：会员价",
                "裂变权益：家居品 10% 返点",
                "其他权益：畅享高额家居返点收益。"
            ],
            4: [
                "注册储值：9800元",
                "专享价格：会员价",
                "裂变权益：全产品 25% 返点",
                "商学院权益：免费享价值 3980元 的护肤私教专业认证。"
            ],
            5: [
                "开通门槛：5.98万元（需线下签约）",
                "高端圈层：Ta创+高端俱乐部会员，享奇肌疗愈营，高端沙龙活动；",
                "产品折扣：享极具竞争力的专属进货权益，产品任选；",
                "SSTA运营：运营中心模版店的打造及全面扶持；",
                "专业赋能：护肤私教全部体系课程+证书，《她力量》《明星代言人》首推官资格。"
            ]
        }

        if user_type not in fee_map:
            return Response(
                {'code': 400, 'msg': '用户类型错误（1-蓝朋友0星，2-蓝朋友1星，3-蓝朋友2星， 4-蓝朋友3星，5-TA创+）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        data = {
            'user_type': user_type,
            'user_type_name': dict(User.USER_TYPE_CHOICES)[user_type],
            'fee': fee_map[user_type],
            'benefits': benefit_map[user_type]
        }
        serializer = self.get_serializer(data)
        return Response({'code': 200, 'data': serializer.data})


class UserProfileViewSet(ReadOnlyModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    # 🌟 核心修复：仅仅是在 request 后面加上了 *args, **kwargs，其他什么都不改！
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_queryset().first()
        serializer = self.get_serializer(instance)
        return Response({'code': 200, 'data': serializer.data})

# ===================== 打卡/考试/认证视图 =====================
class StudyCheckInViewSet(ModelViewSet):
    serializer_class = StudyCheckInSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudyCheckIn.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ===================== 考核题库视图 =====================
class ExamQuestionViewSet(ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExamQuestionSerializer

    def get_queryset(self):
        # 基础查询：只返回启用的题目
        return ExamQuestion.objects.filter(is_active=True)

    @action(detail=False, methods=['get'])
    def generate_paper(self, request):
        """
        随机生成试卷接口：
        用法: GET /api/exam_questions/generate_paper/?course_type=1&limit=20
        """
        course_type = request.query_params.get('course_type')
        limit = int(request.query_params.get('limit', 20))  # 默认抽20题

        if not course_type or not course_type.isdigit():
            return Response({"code": 400, "msg": "请提供正确的课程分类参数(course_type)"},
                            status=status.HTTP_400_BAD_REQUEST)

        # 随机抽取指定分类的题目
        questions = self.get_queryset().filter(course_type=int(course_type)).order_by('?')[:limit]

        if not questions.exists():
            return Response({"code": 404, "msg": "该分类下暂无考题"}, status=status.HTTP_404_NOT_FOUND)

        # 构建返回数据（⚠️ 核心安全：绝对不要在这里把 answer 和 explanation 返回给前端！）
        data = []
        for q in questions:
            data.append({
                "id": q.id,
                "question": q.question,
                "question_type": q.question_type,
                "score": q.score,
                "options": {
                    "A": q.option_a,
                    "B": q.option_b,
                    "C": q.option_c if q.option_c else None,
                    "D": q.option_d if q.option_d else None,
                }
            })

        return Response({
            "code": 200,
            "msg": "试卷生成成功",
            "data": {
                "course_type": int(course_type),
                "total_questions": len(data),
                "questions": data
            }
        })


# ===================== 考核记录(交卷与判题)视图 =====================
class ExamRecordViewSet(ModelViewSet):
    serializer_class = ExamRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ExamRecord.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        重写交卷接口，实现后端自动批改
        预期前端传参格式:
        {
            "course_type": 1,
            "answers": {
                "10": "A",          // 单选题，题号10选A
                "12": ["A", "C"],   // 多选题，题号12选A和C
                "15": "B"           // 判断题，题号15选B
            }
        }
        """
        course_type = request.data.get('course_type')
        user_answers_input = request.data.get('answers', {})

        if not course_type or not isinstance(user_answers_input, dict):
            return Response({"code": 400, "msg": "参数错误：需提供 course_type 和 answers 字典"},
                            status=status.HTTP_400_BAD_REQUEST)

        total_score = 0
        max_score = 0
        user_answers_snapshot = {}

        # 批量获取用户作答的题目对象，减少数据库查询次数
        question_ids = list(user_answers_input.keys())
        questions = ExamQuestion.objects.filter(id__in=question_ids, is_active=True)
        question_map = {str(q.pk): q for q in questions}

        # 遍历判题
        for q_id_str, user_ans in user_answers_input.items():
            q = question_map.get(q_id_str)
            if not q:
                continue  # 如果题目不存在或已下架，跳过

            # 1. 格式化用户答案 (兼容数组 ["A", "C"] 或 字符串 "A,C")
            if isinstance(user_ans, list):
                # 转为大写并排序，拼接为 "A,C"
                user_ans_str = ",".join(sorted([str(i).strip().upper() for i in user_ans]))
            else:
                user_ans_str = str(user_ans).strip().upper()

            # 2. 格式化标准答案 (防止后台录入时不小心带有空格，同样排序处理)
            correct_ans_str = ",".join(sorted([i.strip().upper() for i in str(q.answer).split(',')]))

            # 3. 严格对比判定对错
            is_correct = (user_ans_str == correct_ans_str)

            if is_correct:
                total_score += q.score

            max_score += q.score

            # 4. 生成错题本快照
            user_answers_snapshot[q_id_str] = {
                "question": q.question,
                "question_type": q.question_type,
                "user_answer": user_ans_str,
                "correct_answer": correct_ans_str,
                "is_correct": is_correct,
                "score_earned": q.score if is_correct else 0,
                "explanation": q.explanation  # 此时才把解析吐给前端
            }

        # 计算及格线 (按该次考试的满分计算60%及格)
        pass_line = max_score * 0.6 if max_score > 0 else 0
        is_pass = total_score >= pass_line

        # 保存考试记录
        record = ExamRecord.objects.create(
            user=request.user,
            course_type=int(course_type or 1),
            score=total_score,
            is_pass=is_pass,
            user_answers=user_answers_snapshot
        )

        # 返回判卷结果给前端
        return Response({
            "code": 200,
            "msg": "交卷成功",
            "data": {
                "record_id": record.pk,
                "score": total_score,
                "max_score": max_score,
                "is_pass": is_pass,
                "user_answers": user_answers_snapshot  # 前端拿到这个可以直接渲染“考试结果/错题解析页”
            }
        })

# class CertificationViewSet(ModelViewSet):
#     serializer_class = CertificationSerializer
#     permission_classes = [permissions.IsAuthenticated]
#
#     def get_queryset(self):
#         return Certification.objects.filter(user=self.request.user)
#
#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)

# ===================== 首页固定图片视图 =====================
class Index_AnnonceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        indexan = Index_Annonce.objects.all()
        fixed_serializer = IndexSerializer(indexan, many=True)
        return Response({
            'code': 200,
            'msg': '获取固定图片成功',
            'fixed_images': fixed_serializer.data
        })

# ===================== 购物车视图 =====================

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart_list = Cart.objects.filter(user=request.user).select_related('goods')
        # 🌟 修复 1：必须把 context={'request': request} 传进去！
        # 否则你在 CartSerializer 里写的 request = self.context.get('request') 根本拿不到东西！
        serializer = CartSerializer(cart_list, many=True, context={'request': request})
        total_all = sum([item['total_price'] for item in serializer.data])
        return Response({
            'code': 200,
            'msg': '获取购物车成功',
            'data': {
                'cart_list': serializer.data,
                'total_all': round(total_all, 2)
            }
        })

    def post(self, request):
        goods_id = request.data.get('goods_id')
        num = int(request.data.get('num', 1))
        if not goods_id:
            return Response({'code': 400, 'msg': '商品ID不能为空'}, status=400)
        try:
            goods = Goods.objects.get(id=goods_id)
            if goods.stock < num:
                return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
        except Goods.DoesNotExist:
            return Response({'code': 404, 'msg': '商品不存在'}, status=404)

        with transaction.atomic():
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                goods=goods,
                defaults={'num': num}
            )
            if not created:
                cart.num += num
                if cart.num > goods.stock:
                    return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
                cart.save()
        return Response({'code': 200, 'msg': '添加购物车成功'})

    def put(self, request, cart_id=None):
        if not cart_id:
            return Response({'code': 400, 'msg': '购物车ID不能为空'}, status=400)
        num = int(request.data.get('num', 1))
        try:
            cart = Cart.objects.get(id=cart_id, user=request.user)
            new_num = cart.num + num
            if new_num < 1:
                return Response({'code': 400, 'msg': '商品数量不能小于1'}, status=400)
            if new_num > cart.goods.stock:
                return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
            cart.num = new_num
            cart.save()
            return Response({'code': 200, 'msg': '修改数量成功', 'data': {'num': new_num}})
        except Cart.DoesNotExist:
            return Response({'code': 404, 'msg': '购物车商品不存在'}, status=404)

    def delete(self, request, cart_id=None):
        if not cart_id:
            return Response({'code': 400, 'msg': '购物车ID不能为空'}, status=400)
        try:
            Cart.objects.filter(id=cart_id, user=request.user).delete()
            return Response({'code': 200, 'msg': '删除成功'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'删除失败：{str(e)}'}, status=500)

class CartAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'code': 400,
                'msg': '参数错误',
                'data': serializer.errors
            })
        goods_id = serializer.validated_data['goods_id']
        num = serializer.validated_data['num']
        user = request.user

        goods = get_object_or_404(Goods, id=goods_id)
        if goods.stock < num:
            return Response({
                'code': 400,
                'msg': '库存不足',
                'data': {}
            })

        cart, created = Cart.objects.get_or_create(
            user=user,
            goods=goods,
            defaults={'num': num}
        )
        if not created:
            cart.num += num
            if cart.num > goods.stock:
                return Response({'code': 400, 'msg': '库存不足'}, status=400)
            cart.save()

        return Response({
            'code': 200,
            'msg': '加入购物车成功',
            'data': {'cart_id': cart.pk, 'num': cart.num}
        })

class CartListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("===== 购物车列表(结算页)视图调试 =====")
        try:
            cart_items = Cart.objects.filter(user=request.user).select_related('goods')

            # 🌟 修复 2：获取当前用户的身份星级
            user_type = getattr(request.user, 'user_type', 1)

            cart_list = []
            for item in cart_items:
                # 获取该商品的两个价格，没填零售价则兜底拿会员价
                original_price = item.goods.original_price if item.goods.original_price else item.goods.member_price
                member_price = item.goods.member_price

                # 动态计算真实单价
                real_price = original_price if user_type <= 1 else member_price

                # 兼容旧字段获取积分标记
                can_exchange = getattr(item.goods, 'can_point_exchange', False)
                if hasattr(item.goods, 'is_support_point_exchange'):
                    can_exchange = item.goods.is_support_point_exchange

                cart_list.append({
                    "id": item.pk,
                    "goods_id": item.goods.id,
                    "goods_name": item.goods.name,
                    "goods_image": item.goods.image_url,
                    "num": item.num,

                    # 🌟 核心修复 3：明确把这两个字段返回给前端！！
                    "original_price": float(original_price),
                    "member_price": float(member_price),

                    "price": float(real_price),  # 后端算好的真实单价
                    "total_price": float(real_price * item.num),  # 后端算好的真实总价

                    'is_support_point_exchange': can_exchange,
                    "goods_type": item.goods.goods_type
                })

            return Response({
                "code": 200,
                "msg": "获取购物车列表成功",
                "data": cart_list
            })
        except Exception as e:
            print(f"购物车查询异常：{e}")
            return Response({
                "code": 500,
                "msg": "获取购物车失败",
                "data": []
            }, status=500)

class CartUpdateNumView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart_id = request.data.get('cart_id')
        num = request.data.get('num', 1)
        if not cart_id or not isinstance(num, int) or num < 1:
            return Response({
                'code': 400,
                'msg': '参数错误',
                'data': {}
            })

        cart = get_object_or_404(Cart, id=cart_id, user=request.user)
        if cart.goods.stock < num:
            return Response({
                'code': 400,
                'msg': '库存不足',
                'data': {}
            })

        cart.num = num
        cart.save()
        return Response({
            'code': 200,
            'msg': '修改数量成功',
            'data': {'num': cart.num}
        })

class CartDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart_id = request.data.get('cart_id')
        if not cart_id:
            return Response({
                'code': 400,
                'msg': '参数错误',
                'data': {}
            })

        cart = get_object_or_404(Cart, id=cart_id, user=request.user)
        cart.delete()
        return Response({
            'code': 200,
            'msg': '删除成功',
            'data': {}
        })


class CartClearView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id=None):
        try:
            logger.info(f"清空购物车请求：用户ID={request.user.id}，订单ID={order_id}")

            if order_id:
                try:
                    order_id = int(order_id)
                    cart_query = Cart.objects.filter(user=request.user, order_id=order_id)
                    cart_count = cart_query.count()

                    if cart_count == 0:
                        logger.warning(f"无订单{order_id}关联的购物车数据，执行全清")
                        Cart.objects.filter(user=request.user).delete()
                    else:
                        cart_query.delete()
                        logger.info(f"精准清空{cart_count}条购物车数据")
                except ValueError:
                    return Response({"code": 400, "msg": "订单ID格式错误"}, status=400)
            else:
                clear_count = Cart.objects.filter(user=request.user).delete()[0]
                logger.info(f"全清购物车：删除{clear_count}条数据")

            return Response({
                "code": 200,
                "msg": "购物车清空成功",
                "data": {"cleared": True}
            })
        except Exception as e:
            logger.error(f"清空购物车失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"清空失败：{str(e)}"}, status=500)


# ===================== 收件人/地址视图 =====================
class RecipientView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recipient_list = Recipient.objects.filter(user=request.user)
        serializer = RecipientSerializer(recipient_list, many=True)
        default_recipient = recipient_list.filter(is_default=True).first()
        default_data = RecipientSerializer(default_recipient).data if default_recipient else None
        return Response({
            'code': 200,
            'msg': '获取收件人信息成功',
            'data': {
                'list': serializer.data,
                'default': default_data
            }
        })

    def post(self, request):
        recipient_id = request.data.get('id')
        if request.data.get('is_default'):
            Recipient.objects.filter(user=request.user, is_default=True).update(is_default=False)

        if recipient_id:
            try:
                recipient = Recipient.objects.get(id=recipient_id, user=request.user)
                serializer = RecipientSerializer(recipient, data=request.data)
            except Recipient.DoesNotExist:
                return Response({'code': 404, 'msg': '收件人信息不存在'}, status=404)
        else:
            serializer = RecipientSerializer(data={**request.data, 'user': request.user.id})

        if serializer.is_valid():
            serializer.save()
            return Response({'code': 200, 'msg': '保存成功', 'data': serializer.data})
        return Response({'code': 400, 'msg': '参数错误', 'error': serializer.errors}, status=400)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        recipient_id = request.data.get('recipient_id')
        try:
            recipient = Recipient.objects.get(id=recipient_id, user=request.user)
        except Recipient.DoesNotExist:
            return Response({'code': 404, 'msg': '收件人信息不存在'}, status=404)

        cart_list = Cart.objects.filter(user=request.user).select_related('goods')
        if not cart_list:
            return Response({'code': 400, 'msg': '购物车为空'}, status=400)

        total_all = sum([cart.num * cart.goods.member_price for cart in cart_list])
        return Response({
            'code': 200,
            'msg': '结算成功',
            'data': {
                'recipient': RecipientSerializer(recipient).data,
                'goods_list': CartSerializer(cart_list, many=True).data,
                'total_all': round(total_all, 2)
            }
        })


class AddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        address_list = Address.objects.filter(user=request.user)
        return Response(
            {"code": 200, "msg": "success", "data": {"address_list": AddressSerializer(address_list, many=True).data}})


class AddressManageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            address_list = Address.objects.filter(user=request.user).order_by('-update_time')
            serializer = AddressSerializer(address_list, many=True)

            default_address = address_list.filter(is_default=True).first()
            default_address_id = default_address.pk if default_address else ""

            return Response({
                "code": 200,
                "msg": "success",
                "data": {
                    "address_list": serializer.data,
                    "default_address_id": default_address_id
                }
            })
        except Exception as e:
            print(f"获取地址列表失败：{str(e)}")
            return Response({
                "code": 500,
                "msg": f"获取地址列表失败：{str(e)}",
                "data": {
                    "address_list": [],
                    "default_address_id": ""
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            print(f"当前登录用户：{request.user} | 是否匿名：{request.user.is_anonymous}")
            if request.user.is_anonymous:
                return Response({
                    "code": 401,
                    "msg": "未登录，无法添加地址",
                    "data": {}
                }, status=status.HTTP_401_UNAUTHORIZED)

            is_default = request.data.get('is_default', False)

            with transaction.atomic():
                if is_default:
                    Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

                address_data = {
                    'user': request.user,
                    'name': request.data.get('name', '').strip(),
                    'phone': request.data.get('phone', '').strip(),
                    'address': request.data.get('address', '').strip(),
                    'detail': request.data.get('detail', '').strip(),
                    'is_default': is_default,
                    'province': request.data.get('province', '').strip(),  # 新增
                    'city': request.data.get('city', '').strip(),  # 新增
                    'district': request.data.get('district', '').strip(),  # 新增
                }

                if not address_data['name'] or not address_data['phone'] or not address_data['detail']:
                    return Response({
                        "code": 400,
                        "msg": "姓名、手机号、详细地址不能为空",
                        "data": {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                address = Address.objects.create(**address_data)

                return Response({
                    "code": 201,
                    "msg": "添加地址成功",
                    "data": AddressSerializer(address).data
                })
        except Exception as e:
            print(f"添加地址异常：{str(e)}")
            if "NOT NULL constraint failed" in str(e):
                return Response({
                    "code": 400,
                    "msg": "添加地址失败：用户未登录或用户信息缺失",
                    "data": {}
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response({
                "code": 400,
                "msg": f"添加地址失败：{str(e)}",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            address = Address.objects.get(id=pk, user=request.user)
            serializer = AddressSerializer(address)
            return Response({
                "code": 200,
                "msg": "success",
                "data": serializer.data
            })
        except Address.DoesNotExist:
            return Response({
                "code": 404,
                "msg": "地址不存在",
                "data": {}
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "code": 500,
                "msg": f"获取地址详情失败：{str(e)}",
                "data": {}
            })

    def put(self, request, pk):
        serializer = None
        try:
            address = Address.objects.get(id=pk, user=request.user)

            region = request.data.pop('region', [])
            if region and len(region) >= 3:
                request.data['address'] = " ".join(region)

            is_default = request.data.get('is_default', address.is_default)
            with transaction.atomic():
                if is_default and not address.is_default:
                    Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

            serializer = AddressSerializer(address, data=request.data, partial=True)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response({
                    "code": 200,
                    "msg": "修改地址成功",
                    "data": serializer.data
                })
        except Address.DoesNotExist:
            return Response({
                "code": 404,
                "msg": "地址不存在",
                "data": {}
            })
        except Exception as e:
            return Response({
                "code": 400,
                "msg": f"修改地址失败：{str(e)}",
                "data": serializer.errors if 'serializer' in locals() else {}
            })

    def delete(self, request, pk):
        try:
            address = Address.objects.get(id=pk, user=request.user)
            address.delete()
            return Response({
                "code": 200,
                "msg": "删除地址成功",
                "data": {}
            })
        except Address.DoesNotExist:
            return Response({
                "code": 404,
                "msg": "地址不存在",
                "data": {}
            })


class SetDefaultAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            with transaction.atomic():
                Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
                address = Address.objects.get(id=pk, user=request.user)
                address.is_default = True
                address.save()

            return Response({
                "code": 200,
                "msg": "设置默认地址成功",
                "data": {"default_address_id": pk}
            })
        except Address.DoesNotExist:
            return Response({
                "code": 404,
                "msg": "地址不存在",
                "data": {}
            })
        except Exception as e:
            return Response({
                "code": 500,
                "msg": f"设置默认地址失败：{str(e)}",
                "data": {}
            })


# ===================== 订单视图 =====================

class OrderAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = OrderAddSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            logger.error(f"下单参数错误：{ser.errors}")
            return Response({"code": 400, "msg": "参数错误", "data": ser.errors})

        try:
            with transaction.atomic():
                order_type = int(request.data.get("order_type", 1))
                delivery_type = int(request.data.get("delivery_type", 1))
                pick_up_store_id = request.data.get("pick_up_store_id")
                address_id = request.data.get("address_id")
                deduct_point = int(request.data.get("deduct_point", 0))

                address = None
                pick_up_store = None
                sender_address = None

                if delivery_type == 1:
                    if not address_id:
                        return Response({"code": 400, "msg": "快递上门需选择收货地址"})
                    address = get_object_or_404(Address, id=address_id, user=request.user)
                    sender_address = StoreSenderAddress.objects.filter(is_default=True).first()
                else:
                    if not pick_up_store_id:
                        return Response({"code": 400, "msg": "到店自取需选择取货门店"})
                    pick_up_store = get_object_or_404(Area, id=pick_up_store_id)

                goods_list = request.data.get("goods_list", [])
                if not isinstance(goods_list, list) or len(goods_list) == 0:
                    return Response({"code": 400, "msg": "请选择要购买的商品"})

                total_money = Decimal('0.00')
                total_weight = Decimal('0.00')
                total_volume = Decimal('0.0000')
                invalid_goods = []
                cart_ids = []
                goods_items = []

                # 🌟 核心修改 1：获取当前用户的真实等级 (默认1，即0星/普通用户)
                current_user_type = getattr(request.user, 'user_type', 1)

                for item in goods_list:
                    cart_id = item.get("cart_id")
                    num = int(item.get("num", 1))

                    if not cart_id or num < 1:
                        raise Exception(f"购物车参数错误：cart_id={cart_id}, num={num}")

                    cart = get_object_or_404(Cart, id=cart_id, user=request.user)
                    goods = cart.goods
                    cart_ids.append(cart_id)

                    if goods.stock < num:
                        raise Exception(f"商品库存不足：{goods.name}（库存{goods.stock}，需{num}）")

                    if deduct_point > 0 and not goods.can_point_exchange:
                        invalid_goods.append(goods.name)

                    # ==============================================
                    # ✅ 核心修改 2：后端绝对安全算价逻辑
                    # 如果是 0星(<=1)，使用零售价(original_price)，没填零售价则兜底使用会员价
                    # 如果是 星级(>1)，使用会员价(member_price)
                    # ==============================================
                    if current_user_type <= 1:
                        final_price_str = str(goods.original_price) if goods.original_price else str(goods.member_price)
                    else:
                        final_price_str = str(goods.member_price)

                    goods_price = Decimal(final_price_str)

                    total_money += goods_price * num

                    total_weight += Decimal(str(goods.weight)) * num
                    total_volume += Decimal(str(goods.volume)) * num

                    goods_items.append({
                        "cart": cart,
                        "goods": goods,
                        "num": num,
                        "price": goods_price  # 将最终算好的真实价格存入订单快照
                    })

                if invalid_goods:
                    raise Exception(f"以下商品不支持积分抵扣：{','.join(invalid_goods)}")

                actual_deduct_point = 0
                deduct_money = Decimal('0.00')
                actual_pay_money = total_money

                if deduct_point > 0:
                    user = request.user
                    max_deduct_point = int(total_money * 100)
                    actual_deduct_point = min(deduct_point, max_deduct_point, user.points or 0)

                    if actual_deduct_point < deduct_point:
                        raise Exception(
                            f"积分不足：当前{user.points}分，需{deduct_point}分（最多可抵扣{max_deduct_point}分）")

                    deduct_money = Decimal(str(actual_deduct_point * 0.01))
                    actual_pay_money = max(total_money - deduct_money, Decimal('0.00'))

                current_user = request.user
                fulfill_by_boss = getattr(current_user, 'root_enterprise', None)

                if not fulfill_by_boss and getattr(current_user, 'parent_user', None):
                    fulfill_by_boss = find_root_enterprise(current_user.parent_user)
                    if fulfill_by_boss:
                        current_user.root_enterprise = fulfill_by_boss
                        current_user.save(update_fields=['root_enterprise'])

                order_sn = f"ORD{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

                order = Order.objects.create(
                    user=request.user,
                    order_sn=order_sn,
                    address=address,
                    total_price=total_money,
                    actual_pay_money=actual_pay_money,
                    point_deduct=actual_deduct_point,
                    point_deduct_money=deduct_money,
                    status=0,
                    delivery_type=delivery_type,
                    pick_up_store=pick_up_store,
                    fulfill_by=fulfill_by_boss,
                    sender_name=sender_address.sender_name if sender_address else None,
                    sender_phone=sender_address.sender_phone if sender_address else None,
                    sender_province=sender_address.province if sender_address else None,
                    sender_city=sender_address.city if sender_address else None,
                    sender_district=sender_address.district if sender_address else None,
                    sender_detail=sender_address.detail_address if sender_address else None,
                    sender_address=sender_address.full_address if sender_address else None,
                )
                logger.info(f"创建新订单：order_id={order.pk}, 订单号={order_sn}, 实付金额={actual_pay_money}")

                goods_names = []
                total_count = 0

                for item in goods_items:
                    cart = item["cart"]
                    goods = item["goods"]
                    num = item["num"]
                    price = item["price"]

                    OrderItem.objects.create(
                        order=order,
                        goods=goods,
                        num=num,
                        price=price,
                        goods_name=goods.name,
                        goods_image=goods.image_url,
                        goods_specs=goods.specs if hasattr(goods, 'specs') else "",
                        total_price=price * num,
                        weight=goods.weight,
                        volume=goods.volume
                    )

                    cart.order = order
                    cart.save(update_fields=["order"])
                    goods.stock -= num
                    goods.save(update_fields=["stock"])

                    goods_names.append(goods.name)
                    total_count += num

                order.goods_names = "、".join(goods_names)
                order.goods_count = total_count
                order.save(update_fields=["goods_names", "goods_count"])

                # 京东物流前置校验
                if delivery_type == 1 and sender_address:
                    try:
                        jd_client = JDLClient()
                        precheck_body = [{
                            "orderId": order.order_sn,
                            "senderContact": {
                                "name": order.sender_name,
                                "mobile": order.sender_phone,
                                "fullAddress": order.sender_address
                            },
                            "receiverContact": {
                                "name": address.name,
                                "mobile": address.phone,
                                "fullAddress": f"{address.province or ''}{address.city or ''}{address.district or ''}{address.detail or ''}".strip()
                            },
                            "orderOrigin": 1,
                            "customerCode": jd_client.lop_dn if hasattr(jd_client, 'customer_code') else "27K1234912",
                            "productsReq": {
                                "productCode": "ed-m-0001"
                            },
                            "settleType": 3,
                            "cargoes": [{
                                "name": "美业商品合并发货",
                                "quantity": total_count,
                                "weight": float(total_weight),
                                "volume": float(total_volume)
                            }]
                        }]

                        logger.info(f"发起京东预下单校验，单号: {order.order_sn}")
                        res = jd_client.send_request("/ecap/v1/orders/precheck", precheck_body)

                        if res.get("success") is True or res.get("code") == 200:
                            order.jd_precheck_status = True
                            order.jd_error_msg = "前置校验通过"
                        else:
                            order.jd_precheck_status = False
                            err = res.get("msg") or res.get("error_response", {}).get("zh_desc") or "预下单校验失败"
                            order.jd_error_msg = err
                            logger.warning(f"京东预下单校验未通过: {err}")

                        order.save(update_fields=["jd_precheck_status", "jd_error_msg"])

                    except Exception as jd_err:
                        logger.error(f"调用京东预下单接口崩溃: {str(jd_err)}")
                        order.jd_precheck_status = False
                        order.jd_error_msg = "内部接口异常"
                        order.save(update_fields=["jd_precheck_status", "jd_error_msg"])

                sender_info = {}
                if sender_address:
                    sender_info = {
                        "name": sender_address.sender_name,
                        "phone": sender_address.sender_phone,
                        "province": sender_address.province,
                        "city": sender_address.city,
                        "district": sender_address.district,
                        "detail": sender_address.detail,
                        "full_address": sender_address.full_address
                    }

                print("==========【资产下发·核武器级调试】==========")
                print(f"1. 收到的 order_type 值为: {order_type}, 类型: {type(order_type)}")

                if order_type == 2:
                    for item in goods_items:
                        goods = item["goods"]
                        num = item["num"]
                        print(f"2. 正在检查商品: {goods.name}, 其 goods_type 值为: {goods.goods_type}")

                        if int(goods.goods_type) == 2:
                            asset, created = UserOfflineProject.objects.get_or_create(
                                user=request.user,
                                project=goods,
                                defaults={'total_times': 0, 'remain_times': 0, 'status': 0}
                            )
                            service_times_per_goods = getattr(goods, 'service_times', 1)
                            if service_times_per_goods <= 0:
                                service_times_per_goods = 1

                            add_times = service_times_per_goods * num
                            asset.total_times += add_times
                            asset.remain_times += add_times
                            asset.save(update_fields=['total_times', 'remain_times', 'update_time'])

                            print(f"3. ✅ 成功写入数据库！为用户下发资产: {goods.name} x {add_times}次")
                        else:
                            print(f"3. ❌ 商品 {goods.name} 被跳过，因为 goods_type 不是 2")
                else:
                    print("2. ❌ 整个订单被跳过，因为 order_type 不是 2")

                response_data = {
                    "code": 200,
                    "msg": "下单成功，请支付",
                    "data": {
                        "order_id": order.id,
                        "order_sn": order.order_sn,
                        "total_price": float(total_money),
                        "actual_pay_money": float(actual_pay_money),
                        "point_deduct": actual_deduct_point,
                        "point_deduct_money": float(deduct_money),
                        "delivery_type": delivery_type,
                        "delivery_type_name": order.get_delivery_type_display(),
                        "jd_precheck_status": getattr(order, "jd_precheck_status", None),
                        "jd_error_msg": getattr(order, "jd_error_msg", None),
                        "sender_info": sender_info
                    }
                }

                if delivery_type == 2 and pick_up_store:
                    response_data["data"]["pick_up_store"] = {
                        "id": pick_up_store.id,
                        "name": pick_up_store.name
                    }

                return Response(response_data)

        except Exception as e:
            error_msg = str(e)[:100]
            logger.error(f"下单失败：{error_msg}", exc_info=True)
            return Response({"code": 500, "msg": f"下单失败: {error_msg}"})

class OrderDeleteView(APIView):
    """
    【商城订单】用户手动删除/隐藏已取消的订单
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        order_sn = request.data.get('order_sn')

        print(f"====== 收到用户删除订单请求 ======")
        print(f"操作用户：{user.member_id}，目标订单：{order_sn}")

        if not order_sn:
            return Response({'code': 400, 'msg': '订单编号不能为空'})

        try:
            # 🌟 安全拦截 1：利用外键严格限制只能查到当前用户自己、且未被删除的订单
            order = Order.objects.get(order_sn=order_sn, user=user, is_delete=False)

            # 🌟 安全拦截 2：只有“已取消(4)”状态的订单才允许被删除
            # 防止前端恶意篡改参数，把在途或者待付款的订单给删除了
            if order.status != 4:
                print(f"拒绝删除：订单 {order_sn} 当前状态为 {order.status}，非已取消状态")
                return Response({'code': 400, 'msg': '只有已取消的订单才支持彻底删除'})

            # 执行软删除
            order.is_delete = True
            order.save(update_fields=['is_delete'])

            print(f"✅ 订单 {order_sn} 软删除成功！已对该会员隐藏")
            return Response({'code': 200, 'msg': '订单删除成功'})

        except Order.DoesNotExist:
            print(f"错误：找不到属于该用户的有效订单 {order_sn}")
            return Response({'code': 404, 'msg': '订单不存在或已被删除'})
        except Exception as e:
            print(f"删除订单发生未知异常: {str(e)}")
            return Response({'code': 500, 'msg': f'删除失败：{str(e)[:20]}'})

class OrderReactivateView(APIView):
    """
    【商城订单】重新激活已取消的订单（用于重新支付）
    核心逻辑：重新校验并扣减库存，重置倒计时
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_sn = request.data.get('order_sn')

        if not order_sn:
            return Response({'code': 400, 'msg': '订单编号不能为空'})

        try:
            with transaction.atomic():
                # 1. 悲观锁查询：只能恢复自己、未被删除、且状态为“已取消(4)”的订单
                order = Order.objects.select_for_update().get(
                    order_sn=order_sn,
                    user=request.user,
                    status=4,
                    is_delete=False
                )

                # 2. 检查当前库存是否还足够（因为取消期间可能被别人买空了）
                order_items = OrderItem.objects.filter(order=order)
                for item in order_items:
                    if item.goods.stock < item.num:
                        return Response({
                            'code': 400,
                            'msg': f'手慢了，商品「{item.goods.name}」库存不足，无法重新支付'
                        })

                # 3. 重新扣减库存
                for item in order_items:
                    item.goods.stock -= item.num
                    item.goods.save(update_fields=['stock'])

                # 4. 🌟 核心：重置订单状态和时间，让它重获新生
                order.status = 0
                order.create_time = timezone.now()  # 重置创建时间，触发新的 15 分钟倒计时
                # 清空之前的取消记录
                order.cancel_time = None
                order.cancel_reason = ""
                order.save(update_fields=['status', 'create_time', 'cancel_time', 'cancel_reason'])

                print(f"✅ 订单 {order_sn} 已被重新激活为待付款，并重新锁定库存")
                return Response({'code': 200, 'msg': '订单已恢复，准备拉起支付'})

        except Order.DoesNotExist:
            return Response({'code': 404, 'msg': '订单不存在或状态不正确'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'订单恢复失败：{str(e)[:30]}'})

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        # ================= 💥 终极修复：超时订单变更为"已取消"并释放库存 =================
        now = timezone.now()
        # 测试时先用 1 分钟，正式上线一般是 15分钟 或 30分钟
        expire_threshold = now - timedelta(minutes=15)

        # 找出超时未支付的订单
        expired_orders = Order.objects.filter(
            status=0,
            is_delete=False,
            create_time__lt=expire_threshold
        )

        if expired_orders.exists():
            print(f"🔍 触发全局清理，发现 {expired_orders.count()} 个超时订单")
            for expired_order in expired_orders:
                try:
                    with transaction.atomic():
                        # 1. 找回库存
                        order_items = OrderItem.objects.filter(order=expired_order)
                        for item in order_items:
                            goods = item.goods
                            goods.stock += item.num
                            goods.save(update_fields=['stock'])

                        # 2. 🌟 核心修复：不删除，而是变更为“已取消(4)”状态
                        expired_order.status = 4
                        expired_order.cancel_time = timezone.now()
                        expired_order.cancel_reason = "超时未支付，系统自动取消"

                        # 如果有积分抵扣，可以在这里退回积分 (可选)
                        if expired_order.point_deduct > 0 and expired_order.is_point_deducted:
                            # 调用你之前写的退回积分逻辑
                            pass

                        expired_order.save(update_fields=['status', 'cancel_time', 'cancel_reason'])

                        print(f"✅ 订单 {expired_order.order_sn} 已超时，成功变更为【已取消】并释放库存")
                except Exception as e:
                    print(f"❌ 处理超时订单 {expired_order.id} 失败：{str(e)}")
        else:
            print("✅ 扫描完毕，当前没有达到超时条件的待付款订单。")
        print("=" * 50)
        # =====================================================================

        # 拉取返回给前端的列表时，必须加 is_delete=False！
        orders = Order.objects.filter(
            user=request.user
        ).exclude(
            order_type__in=['member', 'shop', 'upgrade']
        ).order_by('-create_time')

        data_list = []
        for order in orders:
            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                # 兼容旧数据：如果没存省市区，使用 address(省市区字符串) 和 detail 进行拼接
                prov = order.address.province or ""
                cit = order.address.city or ""
                dist = order.address.district or ""
                base_addr = order.address.address or ""  # 提取数据库里的"省市区"
                detail_addr = order.address.detail or ""

                if prov and cit and dist:
                    full_str = f"{prov} {cit} {dist} {detail_addr}".strip()
                else:
                    full_str = f"{base_addr} {detail_addr}".strip()

                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": prov,
                    "city": cit,
                    "district": dist,
                    "address": base_addr,  # 🌟 核心修复：必须把这个字段暴露给前端
                    "detail": detail_addr,
                    "full_address": full_str
                }

            point_summary = {
                "point_deduct": order.point_deduct or 0,
                "point_deduct_money": round(float(order.point_deduct_money or 0.0), 2),
                "actual_pay_price": round(float(order.actual_pay_money or order.total_price), 2)
            }

            data_list.append({
                "order_id": order.id,
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                "actual_pay_price": str(order.actual_pay_money or order.total_price),
                "status": order.status_display,
                "status_code": order.status,
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                "goods_names": order.goods_names,
                "goods_count": order.goods_count,
                "delivery_info": delivery_info,
                "receiver_info": receiver_info,
                "point_summary": point_summary
            })

        return Response({
            "code": 200,
            "msg": "获取订单列表成功",
            "data": data_list
        })

logger = logging.getLogger('django')

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        order_sn = request.query_params.get("order_sn")

        if not (order_id or order_sn):
            return Response({"code": 400, "msg": "请传入订单ID或订单编号"}, status=400)

        logger.info(f"--- 进入订单详情接口 ---")
        logger.info(
            f"前端传入单号: {order_sn}, 当前登录用户: ID={request.user.id} ({request.user.nickname}, 等级={request.user.user_type})")

        try:
            base_filter = Q(is_delete=False)
            if order_id:
                base_filter &= Q(id=order_id)
            else:
                base_filter &= Q(order_sn=order_sn)

            # 加入 fulfill_by 到关联查询中，提高性能
            order = Order.objects.filter(base_filter).select_related('user', 'address', 'pick_up_store',
                                                                     'fulfill_by').first()

            if not order:
                return Response({"code": 404, "msg": "订单不存在"}, status=404)

            # ==========================================================
            # 🌟 核心修复：多维权限校验矩阵
            # ==========================================================
            has_permission = False

            # 1. 身份：我是买家本人
            if str(order.user_id) == str(request.user.id):
                has_permission = True

            # 2. 身份：我是这个订单的指定发货方 (fulfill_by) 🌟【修复点在这里】🌟
            elif str(getattr(order, 'fulfill_by_id', '')) == str(request.user.id):
                has_permission = True

            # 3. 身份：我是买家的直接上级 (兼容老逻辑)
            elif str(request.user.user_type) in ['4', '5']:
                buyer_parent_id = str(getattr(order.user, 'parent_user_id', ''))
                if buyer_parent_id == str(request.user.id):
                    has_permission = True

            if not has_permission:
                logger.warning(
                    f"❌ 内存级权限拦截：订单 {order.order_sn} 属于买家ID={order.user_id}, 发货方ID={getattr(order, 'fulfill_by_id', '')}。当前登录用户 ID={request.user.id} 无权访问。")
                return Response({"code": 403, "msg": "您无权查看该订单"}, status=403)  # 改为 403 更符合语义

            logger.info(f"✅ 权限校验通过！成功获取订单: {order.order_sn}")

            # 超时自动取消
            if order.status == 0:
                expire_threshold = timezone.now() - timedelta(minutes=15)
                if order.create_time < expire_threshold:
                    with transaction.atomic():
                        order_items = OrderItem.objects.filter(order=order)
                        for item in order_items:
                            goods = item.goods
                            if goods:
                                goods.stock += item.num
                                goods.save(update_fields=['stock'])
                        order.is_delete = True
                        order.save(update_fields=['is_delete'])
                    return Response({"code": 404, "msg": "订单已超时并自动取消"}, status=404)

            order_items = OrderItem.objects.filter(order=order).select_related('goods')
            goods_detail = [
                {
                    "goods_id": item.goods.id if item.goods else None,
                    "goods_name": item.goods_name,
                    "goods_image": f"{settings.SERVER_BASE_URL}{item.goods_image}" if not str(
                        item.goods_image).startswith('http') else item.goods_image,
                    "num": item.num,
                    "price": str(item.price),
                    "total_price": str(item.num * item.price)
                }
                for item in order_items
            ]

            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                # 兼容旧数据：如果没存省市区，使用 address(省市区字符串) 和 detail 进行拼接
                prov = order.address.province or ""
                cit = order.address.city or ""
                dist = order.address.district or ""
                base_addr = order.address.address or ""  # 提取数据库里的"省市区"
                detail_addr = order.address.detail or ""

                if prov and cit and dist:
                    full_str = f"{prov} {cit} {dist} {detail_addr}".strip()
                else:
                    full_str = f"{base_addr} {detail_addr}".strip()

                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": prov,
                    "city": cit,
                    "district": dist,
                    "address": base_addr,  # 🌟 核心修复：必须把这个字段暴露给前端
                    "detail": detail_addr,
                    "full_address": full_str
                }

            # ==============================================
            # ✅ 核心修复：直接读取订单自身的寄件人信息
            # ==============================================
            sender_info = {
                "name": order.sender_name or "",
                "phone": order.sender_phone or "",
                "province": order.sender_province or "",
                "city": order.sender_city or "",
                "district": order.sender_district or "",
                "detail": order.sender_detail or "",
                "full_address": order.sender_address or ""
            }

            order_detail = {
                "order_id": order.id,
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                "actual_pay_price": str(order.actual_pay_money or order.total_price),
                "status": order.status_display,
                "status_code": order.status,
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                "goods_count": order.goods_count,
                "delivery_info": delivery_info,
                "receiver_info": receiver_info,
                "sender_info": sender_info,  # 正确的寄件信息
                "goods_detail": goods_detail,
                "jd_precheck_status": getattr(order, "jd_precheck_status", None),
                "jd_error_msg": getattr(order, "jd_error_msg", None)
            }

            return Response({
                "code": 200,
                "msg": "获取订单详情成功",
                "data": order_detail
            })

        except Exception as e:
            logger.error(f"获取订单详情失败: {str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"系统错误：{str(e)}"}, status=500)

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

class WechatPrepayView(APIView):
    """
    【微信支付 V3】小程序统一下单接口
    【完美闭环版】精准拆分纯微信、混合支付、纯钱包支付。无主订单漏洞已修复。
    """
    # authentication_classes = []
    permission_classes = [AllowAny]

    def _get_private_key(self):
        key_path = os.path.join(settings.BASE_DIR, settings.WECHAT_PAY['PRIVATE_KEY_PATH'])
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _rsa_sign(self, message):
        private_key = self._get_private_key()
        signature = private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _build_auth_header(self, method, url_path, timestamp, nonce, body=""):
        sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._rsa_sign(sign_str)

        mchid = settings.WECHAT_PAY['MCHID']
        serial_no = settings.WECHAT_PAY['CERT_SERIAL_NO']

        header_val = (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
            f'nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{serial_no}"'
        )
        return header_val

    def post(self, request):
        try:
            order_id = request.data.get('order_id')
            scene = request.data.get('scene', 'order')
            point_deduct_raw = request.data.get('point_deduct', 0)
            point_deduct = int(point_deduct_raw) if point_deduct_raw else 0
            amount = request.data.get('amount', 0)
            openid = request.data.get('openid', '')
            register_data = request.data.get('register_data', {})
            user_coupon_id = request.data.get('coupon_id')
            use_wallet = request.data.get('use_wallet', False)

            # ========================================================
            # 🌟 顶层初始化
            # ========================================================
            goods_desc = "商品购买"
            out_trade_no = ""
            pay_price_cents = 1
            pay_openid = openid
            wallet_pay_amount = Decimal('0.00')
            wechat_pay_amount = Decimal('0.00')
            final_pay_method = 1

            current_user = request.user if request.user and request.user.is_authenticated else None

            # ========== 分支1：会员开通/开店/升级 ==========
            if scene in ['member', 'shop', 'upgrade']:
                if not openid or float(amount) < 0:
                    return Response({"code": 400, "msg": "缺少支付凭证或金额"}, status=400)

                calc_amount = Decimal(str(amount))
                coupon_money = Decimal('0.00')

                # 优惠券计算
                if user_coupon_id and user_coupon_id != -1 and current_user:
                    try:
                        user_coupon = current_user.user_coupons.select_related('coupon').get(id=user_coupon_id, is_used=False)
                        coupon_tpl = user_coupon.coupon
                        if calc_amount >= coupon_tpl.min_consume:
                            if coupon_tpl.coupon_type == 1:
                                coupon_money = coupon_tpl.money
                            elif coupon_tpl.coupon_type == 2:
                                coupon_money = calc_amount - (calc_amount * coupon_tpl.discount_rate)
                            calc_amount = max(calc_amount - coupon_money, Decimal('0.01'))

                            user_coupon.is_used = True
                            user_coupon.used_time = timezone.now()
                            user_coupon.save(update_fields=['is_used', 'used_time'])
                    except Exception:
                        pass

                # 🌟 核心引擎：智能资金拆分算账
                wechat_pay_amount = calc_amount
                if use_wallet and current_user:
                    user_wallet_bal = Decimal(str(getattr(current_user, 'wallet_balance', '0.00') or '0.00'))
                    if user_wallet_bal >= wechat_pay_amount:
                        # 纯钱包足以覆盖全款
                        wallet_pay_amount = wechat_pay_amount
                        wechat_pay_amount = Decimal('0.00')
                        final_pay_method = 2  # 2: 全额电子账户支付
                    elif user_wallet_bal > 0:
                        # 钱包不够，变成混合支付
                        wallet_pay_amount = user_wallet_bal
                        wechat_pay_amount = wechat_pay_amount - wallet_pay_amount
                        final_pay_method = 4  # 4: 混合支付

                if final_pay_method in [1, 4] and wechat_pay_amount > Decimal('0.00'):
                    wechat_pay_amount = max(wechat_pay_amount, Decimal('0.01'))

                if wechat_pay_amount == Decimal('0.00') and final_pay_method != 2:
                    final_pay_method = 5  # 🌟 5: 代表 0元免单 / 系统直通车
                pay_price_cents = int(wechat_pay_amount * 100)

                order_sn = f"VIP{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

                clean_register_data = register_data or {}
                parent_id = clean_register_data.get('recommender_id') or clean_register_data.get('parent_member_id') or request.data.get('parent_id')
                root_enterprise = None
                if parent_id:
                    try:
                        parent_user = User.objects.get(member_id=parent_id)
                        root_enterprise = find_root_enterprise(parent_user)
                    except User.DoesNotExist:
                        pass
                if not root_enterprise:
                    root_enterprise = User.objects.filter(user_type=5, is_active=True).first()

                if root_enterprise:
                    clean_register_data['root_enterprise_id'] = root_enterprise.id

                # 🌟 核心修复：补充 user=current_user，终结孤儿订单漏洞
                order = Order.objects.create(
                    order_sn=order_sn,
                    user=current_user,
                    total_price=float(amount),
                    actual_pay_money=float(calc_amount),
                    coupon_deduct=coupon_money,
                    wallet_pay=wallet_pay_amount,
                    wechat_pay=wechat_pay_amount,
                    pay_method=final_pay_method,
                    status=0,
                    order_type=scene,
                    openid=openid,
                    fulfill_by=root_enterprise,
                    register_data=clean_register_data,
                    is_delete=False
                )
                pay_openid = openid
                out_trade_no = order_sn
                goods_desc = "会员权益升级" if scene == 'upgrade' else "会籍开通"

            # ========== 分支2：普通商城订单 ==========
            else:
                if not order_id:
                    return Response({"code": 400, "msg": "缺少订单号参数"}, status=400)

                with transaction.atomic():
                    order_str = str(order_id).strip()
                    if order_str.isdigit():
                        order = Order.objects.select_for_update().filter(
                            Q(id=int(order_str)) | Q(order_sn=order_str), is_delete=False
                        ).first()
                    else:
                        order = Order.objects.select_for_update().filter(order_sn=order_str, is_delete=False).first()

                    if not order:
                        return Response({"code": 404, "msg": "未找到有效待支付订单"}, status=404)

                    user = order.user
                    pay_openid = getattr(user, 'openid', None) or openid
                    if not pay_openid:
                        return Response({"code": 400, "msg": "该订单用户缺少微信支付凭证"}, status=400)

                    base_money = Decimal(str(order.total_price))

                    # 优惠券计算
                    if user_coupon_id and user_coupon_id != -1 and user:
                        try:
                            user_coupon = user.user_coupons.select_related('coupon').get(id=user_coupon_id, is_used=False)
                            coupon_tpl = user_coupon.coupon
                            if base_money >= coupon_tpl.min_consume:
                                coupon_money = coupon_tpl.money if coupon_tpl.coupon_type == 1 else (base_money - (base_money * coupon_tpl.discount_rate))
                                base_money = max(base_money - coupon_money, Decimal('0.01'))
                                order.coupon_deduct = coupon_money

                                user_coupon.is_used = True
                                user_coupon.used_time = timezone.now()
                                user_coupon.save(update_fields=['is_used', 'used_time'])
                        except Exception:
                            pass

                    # 积分抵扣
                    if point_deduct > 0 and not getattr(order, 'is_point_deducted', False):
                        deduct_money = Decimal(str(round(point_deduct * 0.01, 2)))
                        order.point_deduct = point_deduct
                        order.point_deduct_money = deduct_money
                        base_money = max(base_money - deduct_money, Decimal('0.01'))

                    # 🌟 核心引擎：智能资金拆分算账
                    wechat_pay_amount = base_money
                    if use_wallet and user:
                        user_wallet_bal = getattr(user, 'wallet_balance', Decimal('0.00'))
                        if user_wallet_bal >= wechat_pay_amount:
                            wallet_pay_amount = wechat_pay_amount
                            wechat_pay_amount = Decimal('0.00')
                            final_pay_method = 2  # 全额电子账户
                        elif user_wallet_bal > 0:
                            wallet_pay_amount = user_wallet_bal
                            wechat_pay_amount = wechat_pay_amount - wallet_pay_amount
                            final_pay_method = 4  # 混合支付

                    if final_pay_method in [1, 4]:
                        wechat_pay_amount = max(wechat_pay_amount, Decimal('0.01'))
                    pay_price_cents = int(wechat_pay_amount * 100)

                    order.actual_pay_money = base_money
                    order.wallet_pay = wallet_pay_amount
                    order.wechat_pay = wechat_pay_amount
                    order.pay_method = final_pay_method
                    order.save(update_fields=['point_deduct', 'point_deduct_money', 'coupon_deduct', 'actual_pay_money', 'wallet_pay', 'wechat_pay', 'pay_method'])

                    out_trade_no = order.order_sn
                    goods_desc = f"购买商品-{order.goods_names_str[:30]}"

            # ==============================================================
            # 🌟 通道分离：如果是【全额电子账户支付】，彻底绕过微信网关直通车！
            # ==============================================================
            if final_pay_method == 2:
                print(f"💰 [资金分流] 订单 {out_trade_no} 将走全额钱包扣款，免呼叫微信！")
                return Response({
                    "code": 200,
                    "msg": "全额抵扣单生成成功",
                    "data": {
                        "is_mock": False,
                        "order_sn": out_trade_no
                    }
                })

            if final_pay_method == 5:
                print(f"🎉 [资金分流] 订单 {out_trade_no} 金额为0，触发免单绿色通道！")

                # 1. 改变订单状态为已完成
                order.status = 3
                order.pay_time = timezone.now()
                order.save(update_fields=['status', 'pay_time'])

                # 2. 立刻执行会员资产下发与建号引擎（替代微信回调的作用）
                if order.order_type in ['member', 'shop', 'upgrade']:
                    register_data = order.register_data or {}
                    register_data['is_paid'] = True
                    register_data['amount'] = 0.0
                    if order.openid: register_data['openid'] = order.openid

                    if order.order_type in ['member', 'shop'] and not order.user:
                        try:
                            # 清理脏头像链接
                            raw_av = register_data.get('avatarUrl', '')
                            if raw_av and (raw_av.startswith('http://tmp') or raw_av.startswith('wxfile://')):
                                register_data['avatarUrl'] = ''

                            # 调用建号引擎（内含发券逻辑）
                            new_user, _, _ = create_register_user(register_data)

                            # 补全关系网
                            p_id = register_data.get('parent_user_id') or register_data.get('recommender_id')
                            r_id = register_data.get('root_enterprise_id')
                            update_user_fields = []
                            if p_id:
                                p_inst = User.objects.filter(member_id=p_id).first()
                                if p_inst:
                                    new_user.parent_user = p_inst
                                    update_user_fields.append('parent_user')
                            if r_id:
                                new_user.root_enterprise_id = r_id
                                update_user_fields.append('root_enterprise_id')
                            if update_user_fields:
                                new_user.save(update_fields=update_user_fields)

                            order.user = new_user
                            order.save(update_fields=['user'])
                            print(f"✅ 0元免单建号成功：{new_user.phone}")
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            print(f"🚨 0元免单建号崩溃: {str(e)}")

                    elif order.order_type == 'upgrade' and order.user:
                        target_lvl = register_data.get('target_level') or register_data.get(
                            'user_type') or register_data.get('level') or 0
                        if int(target_lvl) > 0:
                            try:
                                grant_member_assets(
                                    user=order.user,
                                    target_level=int(target_lvl),
                                    amount_paid=Decimal('0.00'),
                                    remark_text="0元免单升级会籍"
                                )
                            except Exception as e:
                                print(f"🚨 0元升级报错: {str(e)}")

                return Response({
                    "code": 200,
                    "msg": "0元免单处理成功",
                    "data": {
                        "is_mock": True,  # 🌟 关键点：告诉前端这是模拟支付，让它直接调 paySuccess
                        "order_sn": out_trade_no
                    }
                })
            # ==============================================================
            # 🌟 Debug 模式拦截器
            # ==============================================================
            is_debug_pay = getattr(settings, 'DEBUG_PAY', False)

            if is_debug_pay:
                print(f"⚠️ [测试/Debug 模式] 触发虚拟支付，跳过微信真实统一下单！订单号: {out_trade_no}")
                return Response({
                    "code": 200,
                    "msg": "【模拟环境】预支付参数生成成功",
                    "data": {
                        "is_mock": True,
                        "order_sn": out_trade_no,
                        "timeStamp": str(int(time.time())),
                        "nonceStr": f"MOCK_NONCE_{uuid.uuid4().hex[:8].upper()}",
                        "package": "prepay_id=MOCK_PREPAY_ID",
                        "signType": "RSA",
                        "paySign": "MOCK_SIGNATURE"
                    }
                })

            # ==============================================================
            # 🌟 真实调用微信统一下单 API
            # ==============================================================
            url_path = "/v3/pay/transactions/jsapi"
            full_url = f"https://api.mch.weixin.qq.com{url_path}"
            timestamp = str(int(time.time()))
            nonce = uuid.uuid4().hex.upper()

            body_data = {
                "appid": settings.WECHAT_PAY['APPID'],
                "mchid": settings.WECHAT_PAY['MCHID'],
                "description": goods_desc,
                "out_trade_no": out_trade_no,
                "notify_url": settings.WECHAT_PAY['NOTIFY_URL'],
                "amount": {"total": pay_price_cents, "currency": "CNY"},
                "payer": {"openid": pay_openid}
            }
            body_json = json.dumps(body_data, separators=(',', ':'))
            auth_header = self._build_auth_header("POST", url_path, timestamp, nonce, body_json)
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": auth_header,
                "User-Agent": "Django-WechatPay-V3-Client"
            }

            response = requests.post(full_url, data=body_json, headers=headers, timeout=10)
            if response.status_code != 200:
                return Response({"code": 500, "msg": f"微信下单通讯失败: {response.text}"}, status=500)

            res_data = response.json()
            prepay_id = res_data.get('prepay_id')
            if not prepay_id:
                return Response({"code": 500, "msg": "未能获取到预支付会话标识"}, status=500)

            front_timestamp = str(int(time.time()))
            front_nonce = uuid.uuid4().hex.upper()
            package_str = f"prepay_id={prepay_id}"
            front_sign_message = f"{settings.WECHAT_PAY['APPID']}\n{front_timestamp}\n{front_nonce}\n{package_str}\n"
            front_signature = self._rsa_sign(front_sign_message)

            return Response({
                "code": 200,
                "msg": "预支付参数生成成功",
                "data": {
                    "is_mock": False,
                    "order_sn": out_trade_no,
                    "timeStamp": front_timestamp,
                    "nonceStr": front_nonce,
                    "package": package_str,
                    "signType": "RSA",
                    "paySign": front_signature
                }
            })

        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "未找到有效待支付订单"}, status=404)
        except Exception as e:
            traceback.print_exc()
            return Response({"code": 500, "msg": f"系统发起支付故障: {str(e)}"}, status=500)

def wx_get_user_openid_somehow(user):
    """ 兜底函数：如果你的 user 属性名不叫 openid，请在此行完成映射转换 """
    return getattr(user, 'username', None)  # 根据实际调整

class WechatPayCallbackView(APIView):
    """
    微信支付 V3 统一回调接口
    覆盖：新用户开通会员、会员升级、普通商品购买
    配置依赖：settings.WECHAT_PAY（支付）、settings.WX_APP_ID / WX_APP_SECRET（小程序）
    """
    authentication_classes = []
    permission_classes = []

    def decrypt_wechat_resource(self, resource):
        """ AES-256-GCM 解密微信支付回调密文 """
        api_v3_key = settings.WECHAT_PAY['API_V3_KEY'].encode('utf-8')
        nonce = resource['nonce'].encode('utf-8')
        associated_data = resource.get('associated_data', '').encode('utf-8')
        ciphertext = base64.b64decode(resource['ciphertext'])

        aesgcm = AESGCM(api_v3_key)
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(decrypted_data.decode('utf-8'))

    def _get_wx_access_token(self):
        """ 获取微信接口调用凭证（带7000秒缓存） """
        access_token = cache.get('wx_access_token')
        if access_token:
            return access_token

        appid = settings.WECHAT_PAY["APPID"]
        secret = settings.WECHAT_PAY["APP_SECRET"]
        url = (
            f"https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential&appid={appid}&secret={secret}"
        )
        res = requests.get(url, timeout=10).json()
        if 'access_token' not in res:
            raise Exception(f"获取微信access_token失败: {res.get('errmsg', '未知错误')}")

        access_token = res['access_token']
        cache.set('wx_access_token', access_token, timeout=7000)
        return access_token

    def _decrypt_phone_number(self, phone_code):
        """ 通过手机号授权码解密真实手机号 """
        access_token = self._get_wx_access_token()
        url = (
            f"https://api.weixin.qq.com/wxa/business/getuserphonenumber"
            f"?access_token={access_token}"
        )
        res = requests.post(url, json={"code": phone_code}, timeout=10).json()
        if res.get('errcode') != 0:
            raise Exception(f"手机号解密失败: {res.get('errmsg', '未知错误')}")
        return res['phone_info']['phoneNumber']

    def post(self, request):
        print("===== 收到微信支付 V3 异步回调 =====")
        try:
            # 1. 接收并解密回调报文
            event_data = request.data
            if event_data.get('event_type') != 'TRANSACTION.SUCCESS':
                return Response({'code': 'SUCCESS', 'message': '非支付成功通知，忽略'}, status=200)

            resource = event_data.get('resource', {})
            decrypted_data = self.decrypt_wechat_resource(resource)

            # 2. 提取支付核心字段
            order_sn = decrypted_data.get('out_trade_no')
            transaction_id = decrypted_data.get('transaction_id')
            total_fee = decrypted_data.get('amount', {}).get('total', 0) / 100.0

            print(f"支付成功：订单={order_sn}, 微信单号={transaction_id}, 金额={total_fee}元")

            # 3. 事务 + 行锁，保证幂等与数据一致
            with transaction.atomic():
                order = Order.objects.select_for_update().filter(order_sn=order_sn).first()
                if not order:
                    print(f"警告：找不到对应订单 {order_sn}")
                    return Response({'code': 'SUCCESS', 'message': '订单不存在'}, status=200)

                if order.status != 0:
                    print(f"订单 {order_sn} 已处理，忽略本次回调")
                    return Response({'code': 'SUCCESS', 'message': '订单已处理'}, status=200)

                # ==============================================================
                # 💳 核销钱包抵扣
                # ==============================================================
                from decimal import Decimal
                import uuid

                if order.wallet_pay and order.wallet_pay > Decimal('0.00'):
                    print(f"⏳ 微信真实支付成功，开始同步扣除电子账户抵扣金额: ¥{order.wallet_pay}...")
                    if order.user and hasattr(order.user, 'wallet'):
                        try:
                            wallet = order.user.wallet
                            locked_wallet = type(wallet).objects.select_for_update().get(id=wallet.id)

                            deduct_amount = Decimal(str(order.wallet_pay))
                            total_bal = locked_wallet.principal + locked_wallet.bonus

                            if total_bal >= deduct_amount:
                                used_bonus = Decimal('0.00')
                                used_principal = Decimal('0.00')

                                if locked_wallet.bonus >= deduct_amount:
                                    locked_wallet.bonus -= deduct_amount
                                    used_bonus = deduct_amount
                                else:
                                    used_bonus = locked_wallet.bonus
                                    remaining = deduct_amount - locked_wallet.bonus
                                    locked_wallet.bonus = Decimal('0.00')
                                    locked_wallet.principal -= remaining
                                    used_principal = remaining

                                locked_wallet.total_balance = locked_wallet.principal + locked_wallet.bonus
                                locked_wallet.save(update_fields=['principal', 'bonus', 'total_balance'])

                                from .models import WalletTransaction
                                trade_no = f"WT{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                                WalletTransaction.objects.create(
                                    wallet=locked_wallet,
                                    trade_no=trade_no,
                                    order_sn=order.order_sn,
                                    transaction_type=2,
                                    amount=-deduct_amount,
                                    principal_change=-used_principal,
                                    bonus_change=-used_bonus,
                                    after_balance=locked_wallet.total_balance,
                                    remark=f"微信混合支付完成自动核销，订单号：{order.order_sn}"
                                )
                                print(f"✅ [生产环境核销成功] 成功从电子钱包扣除: ¥{deduct_amount}！流水号: {trade_no}")
                            else:
                                print(
                                    f"🚨 [生产环境严重故障] 微信付款成功，但钱包余额不足！订单需扣 ¥{deduct_amount}，仅剩 ¥{total_bal}")
                        except Exception as e:
                            print(f"🚨 [生产环境致命异常] 扣减钱包时代码崩溃: {str(e)}")
                            traceback.print_exc()
                    else:
                        print("🚨 [生产环境异常] 订单显示需钱包抵扣，但买家用户实体没有关联 wallet 属性！")

                # ==============================================================
                # 🌟 核心防线升级：智能订单类型嗅探器与冲突检测
                # ==============================================================
                o_type = str(order.order_type).strip().lower()
                is_member_flow = o_type in ['member', 'shop', '1'] or order_sn.startswith('VIP') or o_type == 'upgrade'

                if is_member_flow:
                    print(f"🔄 处理会籍订单回调: {order_sn}")

                    # 🌟 [安全升级] 第一步：确定目标用户实体（严防并发建号）
                    target_user = order.user

                    # 双保险查找：如果订单未绑定，尝试通过 openid 查找数据库中是否已有该老用户
                    if not target_user and order.openid:
                        target_user = User.objects.filter(openid=order.openid).first()

                    # 准备资产下发数据
                    register_data = order.register_data or {}
                    register_data['is_paid'] = True
                    register_data['amount'] = float(total_fee)
                    if order.openid: register_data['openid'] = order.openid

                    if not target_user:
                        # -----------------------------------------------------
                        # 场景 1-A：真正的全新用户 -> 执行建号
                        # -----------------------------------------------------
                        print(f"📝 [真实回调] 数据库无此 openid，执行新用户建号场景...")

                        # 头像临时链接清理逻辑
                        raw_av = register_data.get('avatarUrl', '')
                        if raw_av and (raw_av.startswith('http://tmp') or raw_av.startswith('wxfile://')):
                            register_data['avatarUrl'] = ''

                        try:
                            # 🚀 调用注册引擎（内部会自动建号、派发资产 grant_member_assets）
                            target_user, _, _ = create_register_user(register_data)

                            # 🌟 补全上下级与顶级 Ta 创 + 关系网
                            p_id = register_data.get('parent_user_id') or register_data.get('recommender_id')
                            r_id = register_data.get('root_enterprise_id')

                            update_user_fields = []
                            if p_id:
                                parent_instance = User.objects.filter(member_id=p_id).first()
                                if parent_instance:
                                    target_user.parent_user = parent_instance
                                    update_user_fields.append('parent_user')
                            if r_id:
                                target_user.root_enterprise_id = r_id
                                update_user_fields.append('root_enterprise_id')

                            if update_user_fields:
                                target_user.save(update_fields=update_user_fields)

                            print(f"✅ 成功为新用户 {target_user.phone} 开卡并关联关系网")
                        except Exception as e:
                            traceback.print_exc()
                            print(f"🚨 [生产致命] 建号失败: {str(e)}")
                            # 即使失败也要让微信知道我们收到了，防止无限重试
                            return Response({'code': 'SUCCESS', 'message': f'建号异常:{str(e)}'}, status=200)
                    else:
                        # -----------------------------------------------------
                        # 场景 1-B：数据库已有此 OpenID -> 执行资产累加（老号翻新/升级）
                        # -----------------------------------------------------
                        print(
                            f"🚀 [生产兼容] 检测到 openid 已属于老用户 {target_user.phone}，跳过建号，直接执行资产累加引擎...")

                        target_level_raw = register_data.get('target_level') or register_data.get(
                            'user_type') or register_data.get('level')

                        if target_level_raw:
                            try:
                                # 🌟 调用资产累加引擎
                                grant_member_assets(
                                    user=target_user,
                                    target_level=int(target_level_raw),
                                    amount_paid=Decimal(str(total_fee)),
                                    remark_text=f"微信支付开卡/升级订单(OpenID防冲突)，订单号:{order_sn}"
                                )
                            except Exception as e:
                                print(f"🚨 资产累加失败: {str(e)}")

                    # 🌟 [关键修正] 统一更新订单状态并死死绑定确定的用户实体
                    if target_user:
                        order.status = 3
                        order.pay_method = 1
                        order.pay_no = transaction_id
                        order.pay_time = timezone.now()
                        order.actual_pay_money = total_fee
                        order.user = target_user  # 绑定查询到的老用户或者新建的新用户
                        order.save(
                            update_fields=['status', 'pay_method', 'pay_no', 'pay_time', 'actual_pay_money', 'user'])
                        print(f"✅ 会员订单{order_sn}处理完成，状态已同步。")

                    # 会员流程处理完毕，安全返回
                    return Response({'code': 'SUCCESS', 'message': '成功'}, status=200)

                else:
                    # =====================================================
                    # 场景 3：普通商品购买订单
                    # =====================================================
                    user = order.user
                    if not user:
                        print(f"警告：普通商品订单{order_sn}无关联用户，仅修改订单状态")
                        order.status = 1
                        order.pay_method = 1
                        order.pay_no = transaction_id
                        order.pay_time = timezone.now()
                        order.actual_pay_money = total_fee
                        order.save(update_fields=['status', 'pay_method', 'pay_no', 'pay_time', 'actual_pay_money'])
                        return Response({'code': 'SUCCESS', 'message': '成功'}, status=200)

                    # 1. 更新订单状态
                    order.status = 1
                    order.pay_method = 1
                    order.pay_no = transaction_id
                    order.pay_time = timezone.now()
                    order.actual_pay_money = total_fee
                    order.save(update_fields=['status', 'pay_method', 'pay_no', 'pay_time', 'actual_pay_money'])

                    # 2. 扣除积分抵扣
                    deduct_point = order.point_deduct or 0
                    if deduct_point > 0 and not PointsRecord.objects.filter(user=user, points_type=4,
                                                                            related_id=order.order_sn).exists():
                        user.add_points(points=-deduct_point, points_type=4, related_id=order.order_sn,
                                        related_desc=f"订单抵扣{deduct_point}积分")

                    # 3. 赠送消费积分
                    has_given = PointsRecord.objects.filter(
                        user=user,
                        points_type=2,
                        related_id=order.order_sn
                    ).exists()

                    if not has_given and total_fee > 0:
                        # 🌟 核心更新：消费护肤品 1 元获得 1 积分
                        base_points = round(total_fee * 1)

                        is_bd_month = user.is_birthday_month() if hasattr(user, 'is_birthday_month') else False
                        final_points = base_points * 2 if is_bd_month else base_points

                        if final_points > 0:
                            user.add_points(
                                points=final_points,
                                points_type=2,
                                related_id=order.order_sn,
                                related_desc=f"消费赠送{final_points}积分"
                            )

                    print(f"✅ 普通订单 {order_sn} 回调业务全部处理完毕！")
                    return Response({'code': 'SUCCESS', 'message': '成功'}, status=200)

        except Exception as e:
            traceback.print_exc()
            # 异常返回500，微信会在合理时间内重试
            return Response(
                {'code': 'FAIL', 'message': f'服务器内部错误: {str(e)}'},
                status=500
            )

class PayGetTokenView(APIView):
    """
    【Ta创+】核心中枢：获取支付后的登录凭证与身份刷新
    【安全规范】无任何账号特权后门。测试流转 100% 依赖 settings.DEBUG_PAY 物理开关。
    """
    permission_classes = [AllowAny]

    def post(self, request):
        order_sn = request.data.get('order_sn')

        if not order_sn:
            return Response({'code': 400, 'msg': '缺少订单号参数'})

        # 1. 检索核心订单
        order = Order.objects.filter(order_sn=order_sn).first()
        if not order:
            print(f"❌ [安全拦截] 数据库里找不到单号为 {order_sn} 的订单！")
            return Response({'code': 400, 'msg': f'订单 {order_sn} 不存在'})

        # ==============================================================
        # 🌟 核心防线：唯一定向开关！没有任何账号特权！
        # ==============================================================
        is_debug_pay = getattr(settings, 'DEBUG_PAY', False)

        if order.status == 0:
            if is_debug_pay:
                print(f"\n" + "=" * 50)
                print(f"🚀 [物理拨片激活] DEBUG_PAY=True，执行本地联调支付成功回调，订单: {order_sn}")
                print(
                    f"👉 支付方式: {order.get_pay_method_display()} | 微信需付: ¥{order.wechat_pay} | 钱包抵扣: ¥{order.wallet_pay}")

                # -----------------------------------------------------------
                # 💳 核心资产原子核销（仅在混合/全额钱包时触发）
                # -----------------------------------------------------------
                if order.wallet_pay and order.wallet_pay > Decimal('0.00'):
                    print("⏳ 正在扣除电子账户余额并记录金融流水...")
                    if order.user and hasattr(order.user, 'wallet'):
                        try:
                            from django.db import transaction
                            with transaction.atomic():
                                wallet = order.user.wallet
                                locked_wallet = type(wallet).objects.select_for_update().get(id=wallet.id)

                                deduct_amount = Decimal(str(order.wallet_pay))
                                total_bal = locked_wallet.principal + locked_wallet.bonus

                                if total_bal >= deduct_amount:
                                    used_bonus = Decimal('0.00')
                                    used_principal = Decimal('0.00')

                                    # FIFO 算法：优先扣赠送金
                                    if locked_wallet.bonus >= deduct_amount:
                                        locked_wallet.bonus -= deduct_amount
                                        used_bonus = deduct_amount
                                    else:
                                        used_bonus = locked_wallet.bonus
                                        remaining = deduct_amount - locked_wallet.bonus
                                        locked_wallet.bonus = Decimal('0.00')
                                        locked_wallet.principal -= remaining
                                        used_principal = remaining

                                    # 对齐冗余字段并落盘
                                    locked_wallet.total_balance = locked_wallet.principal + locked_wallet.bonus
                                    locked_wallet.save(update_fields=['principal', 'bonus', 'total_balance'])

                                    # 记入不可篡改的流水表快照
                                    trade_no = f"WT{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                                    WalletTransaction.objects.create(
                                        wallet=locked_wallet,
                                        trade_no=trade_no,
                                        order_sn=order.order_sn,
                                        transaction_type=2,  # 2: 消费扣款
                                        amount=-deduct_amount,
                                        principal_change=-used_principal,
                                        bonus_change=-used_bonus,
                                        after_balance=locked_wallet.total_balance,
                                        remark=f"商城购物抵扣，订单号：{order.order_sn}"
                                    )
                                    print(
                                        f"✅ [核销成功] 流水号: {trade_no} | 账户新余额: ¥{locked_wallet.total_balance}")
                                else:
                                    print(f"🚨 [安全拦截] 账户余额真实不足！防薅羊毛熔断。")
                                    return Response({'code': 400, 'msg': '支付失败：电子账户可用余额不足'})
                        except Exception as e:
                            print(f"🚨 [致命异常] 电子钱包扣款崩溃: {str(e)}")
                            traceback.print_exc()
                            return Response({'code': 500, 'msg': f'钱包核销失败: {str(e)}'})
                    else:
                        print("🚨 [资产异常] 订单存在钱包代扣，但买家用户实体没有关联 wallet 属性！")

                # 改变订单为已支付状态
                order.status = 1
                order.pay_time = timezone.now()
                order.save(update_fields=['status', 'pay_time'])

                # -----------------------------------------------------------
                # 🎁 场景 A：老用户升级会籍（资产累加派发）
                # -----------------------------------------------------------
                if order.order_type == 'upgrade':
                    print(f"🚀 [测试后门] 执行老用户升级场景...")
                    upgrade_user = order.user
                    if upgrade_user:
                        target_lvl = order.register_data.get('target_level', 2) if order.register_data else 2
                        grant_member_assets(
                            user=upgrade_user,
                            target_level=int(target_lvl),
                            amount_paid=order.actual_pay_money,
                            remark_text=f"老用户会籍升级，订单号:{order_sn}"
                        )
                    else:
                        print("❌ [测试后门错误] 升级订单未绑定操作用户！")

                # -----------------------------------------------------------
                # 🎁 场景 B：全新用户注册付费（自动建号并注入资产）
                # -----------------------------------------------------------
                elif order.order_type in ['member', 'shop']:
                    print(f"📝 [测试后门] 执行新用户建号场景...")
                    if order.register_data:
                        register_data = order.register_data
                        register_data['is_paid'] = True
                        if order.openid:
                            register_data['openid'] = order.openid
                        raw_av = register_data.get('avatarUrl', '')
                        if raw_av and (raw_av.startswith('http://tmp') or raw_av.startswith('wxfile://')):
                            register_data['avatarUrl'] = ''

                        try:
                            # 触发新用户注册闭环（内部会自动调用 grant_member_assets）
                            new_user, _, _ = create_register_user(register_data)

                            # 🌟 防线：强行确保关联电子钱包必须初始化成功，防止收银台死锁
                            UserWallet.objects.get_or_create(user=new_user)

                            # 补全上下级与顶级 Ta 创 + 关系网
                            p_id = register_data.get('parent_user_id')
                            r_id = register_data.get('root_enterprise_id')
                            if p_id or r_id:
                                if p_id: new_user.parent_user_id = p_id
                                if r_id: new_user.root_enterprise_id = r_id
                                new_user.save(update_fields=['parent_user_id', 'root_enterprise_id'])

                            # 将新建的用户死死绑定回当前主订单
                            order.user = new_user
                            order.save(update_fields=['user'])
                        except Exception as e:
                            traceback.print_exc()
                            return Response({'code': 500, 'msg': f'测试后门建号失败: {str(e)}'})
                print("=" * 50 + "\n")

            else:
                # 🛑 生产环境：绝对隔离！无视任何状态0的请求
                print(f"🛑 [生产安全拦截] 订单 {order_sn} 处于待付款状态，严禁获取 Token 与下发资产！")
                return Response({'code': 402, 'msg': '订单尚未完成支付，请在收银台付款后再试'})

        # ==============================================================
        # 🌟 真实业务逻辑：发放安全 JWT Token 凭证与返回最新用户信息缓存
        # ==============================================================
        user = order.user
        if not user:
            return Response({'code': 400, 'msg': '订单未绑定有效用户，无法签发登录凭证'})

        # 🌟 统一核心修复：只要状态还是待付款(0)，继续让前端轮询等待
        if order.status == 0:
            return Response({'code': 402, 'msg': '微信网关对账中，请稍后再试'})

        # 🌟 终极放行装甲：不管是普通商品的 1，还是会员场景的 3，统统放行！
        if order.status not in [1, 3]:
            print(f"🛑 [安全拦截] 订单 {order_sn} 处于异常状态: {order.status}，拒绝下发凭证！")
            return Response({'code': 402, 'msg': '订单校验未通过，无法开通权益'})

        try:
            # 1. 颁发具有最高法律效力的 JWT 双 Token
            refresh = RefreshToken.for_user(user)

            # 2. 聚合属性安全聚合
            coupon_count = user.get_coupon_stats()['total'] if hasattr(user, 'get_coupon_stats') else 0
            wallet_balance = float(user.wallet_balance) if hasattr(user, 'wallet_balance') else 0.00

            user_info = {
                'nickname': user.nickname,
                'member_id': user.member_id,
                'user_type': user.user_type,
                'phone': user.phone,
                'points': user.points,
                'coupon_count': coupon_count,
                'wallet_balance': wallet_balance,
            }

            return Response({
                'code': 200,
                'msg': '支付成功，权益已自动开通！',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'data': user_info
            })

        except Exception as e:
            traceback.print_exc()
            return Response({'code': 500, 'msg': f'签发身份令牌故障: {str(e)}'})

class UserWalletDetailView(APIView):
    """
    【Ta创+】核心接口：前端查询当前钱包余额
    🌟 升级：注入脏数据自愈装甲，只要接口被调用，自动清洗历史不对齐的毒瘤数据！
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # get_or_create 确保新用户点击时自动初始化 0 元钱包
        wallet, created = UserWallet.objects.get_or_create(user=request.user)

        # 🌟 核心优化：脏数据自愈。
        # 如果是以前的历史老数据，发现总余额不等于本金+赠金（如本金0赠金0，总余额182）
        # 只要用户一进钱包页面，接口立刻强制触发 save() 重新计算对齐，彻底纠正错误，防误导前端！
        if not created and wallet.total_balance != (wallet.principal + wallet.bonus):
            print(f"⚠️ [自愈引擎触发] 检测到用户 {request.user.phone} 钱包数据不对齐，正在强制修正...")
            # 如果本金和赠金全为0但总余额有钱，判定为充值脏数据，将钱全部归为可提现的“本金”
            if wallet.principal == Decimal('0.00') and wallet.bonus == Decimal('0.00') and wallet.total_balance > 0:
                wallet.principal = wallet.total_balance
            wallet.save()  # 触发我们重写的 save() 方法，重新锁死 total_balance

        return Response({
            "code": 200,
            "msg": "获取钱包详情成功",
            "data": {
                "total_balance": float(wallet.total_balance),
                "principal": float(wallet.principal),
                "bonus": float(wallet.bonus),
                "status": wallet.status
            }
        })

class WalletTransactionListView(APIView):
    """
    【Ta创+】核心接口：前端查询钱包账单明细（支持分页）
    🌟 升级：精细化对账输出，把每一笔扣款扣的是本金还是赠金如实推给前端，财务极其透明！
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = UserWallet.objects.get(user=request.user)
        except UserWallet.DoesNotExist:
            return Response({"code": 200, "msg": "获取成功", "data": [], "total": 0})

        # 获取资金流水，按时间倒序
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-create_time')

        # 分页防护
        try:
            page = int(request.query_params.get('page', 1))
            size = int(request.query_params.get('size', 20))
        except ValueError:
            page, size = 1, 20

        start = (page - 1) * size
        end = start + size

        data_list = []
        for t in transactions[start:end]:
            data_list.append({
                "trade_no": t.trade_no,
                "type_name": t.get_transaction_type_display(),
                "amount": float(t.amount),

                # 🌟 核心优化：向前端输出本金、赠金的精确变动明细
                # 这样前端可以在 UI 上渲染出：消费扣款 -¥100 (本金扣除: -¥80, 赠金扣除: -¥20)
                "principal_change": float(t.principal_change),
                "bonus_change": float(t.bonus_change),

                "after_balance": float(t.after_balance),
                "remark": t.remark,
                "create_time": t.create_time.strftime("%Y-%m-%d %H:%M:%S")
            })

        return Response({
            "code": 200,
            "msg": "获取成功",
            "data": data_list,
            "total": transactions.count()
        })

class WalletPayOrderView(APIView):
    """
    【Ta创+】核心接口：前端发起【全额】电子账户支付请求
    🌟 升级：增加边界安全锁，杜绝混合支付单错切通道，提升并发健壮性。
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_sn = request.data.get('order_sn')
        if not order_sn:
            return Response({"code": 400, "msg": "缺失订单号参数"}, status=400)

        order = Order.objects.filter(order_sn=order_sn, is_delete=False).first()
        if not order:
            return Response({"code": 404, "msg": "订单不存在"}, status=404)
        if order and order.pay_method == 4:
            return Response({
                "code": 400,
                "msg": "该订单已转为混合支付，请选择微信收银台完成微信部分的支付！"
            }, status=400)

        print(f"\n🪙 [全额账户支付] 用户 {request.user.phone} 正在请求全额扣款，订单: {order_sn}")

        # 调用你们底层的纯钱包支付核心服务引擎
        # （里面必须包含：select_for_update 锁钱包、扣全额、写流水 transaction_type=2、改订单 status=1、发资产）
        try:
            success, msg = pay_order_with_wallet(request.user, order_sn)
            if success:
                print(f"✅ [全额账户支付成功] 订单: {order_sn}\n")
                order.refresh_from_db()  # 获取底层引擎改过的最新状态

                # 识别是否为虚拟升级订单
                is_virtual_order = order.order_sn.startswith('VIP') or order.order_sn.startswith('UPG')

                if is_virtual_order:
                    register_data = order.register_data or {}
                    # 兼容各个版本的参数命名
                    target_level_raw = register_data.get('target_level') or register_data.get(
                        'user_type') or register_data.get('level')

                    if target_level_raw:
                        target_level = int(target_level_raw)
                        try:
                            # 🌟 触发核心资产分发引擎！(内部会自动改等级、延期、发代金券)
                            grant_member_assets(
                                user=request.user,
                                target_level=target_level,
                                amount_paid=order.actual_pay_money,
                                remark_text=f"全额钱包升级特权入账，单号：{order_sn}"
                            )
                        except Exception as e:
                            print(f"❌ 钱包支付升级资产下发失败: {str(e)}")

                    # 虚拟订单处理完毕后，将订单最终状态标记为 3 (已完成)
                    order.status = 3
                    order.pay_time = timezone.now()
                    order.save(update_fields=['status', 'pay_time'])
                return Response({"code": 200, "msg": msg})
            else:
                print(f"❌ [全额账户支付驳回] 原因: {msg}\n")
                return Response({"code": 400, "msg": msg}, status=400)

        except Exception as e:
            traceback.print_exc()
            return Response({"code": 500, "msg": f"全额扣款中途崩溃: {str(e)}"}, status=500)

class RechargeActivityListView(APIView):
    """获取所有上架的储值套餐列表"""

    def init_default_rules(self):
        """🌟 自动初始化全新 6 档储值与代金券规则"""
        coupon_100, _ = Coupon.objects.get_or_create(
            title="储值专享100元代金券",
            defaults={
                'coupon_type': 1, 'money': 100.00, 'discount_rate': 1.00,
                'min_consume': 0.00, 'valid_days': 365, 'is_active': True
            }
        )

        # 🌟 严格对齐新版体系的金额与代金券张数
        rules = [
            {"amount": 980, "num": 1, "name": "充980元 (蓝朋友1星)"},
            {"amount": 1980, "num": 3, "name": "充1980元 (蓝朋友2星)"},
            {"amount": 3800, "num": 10, "name": "充3800元 (蓝朋友3星)"},
            {"amount": 9800, "num": 0, "name": "充9800元 (蓝朋友4星)"},
            {"amount": 39800, "num": 0, "name": "充39800元 (蓝朋友5星)"},
        ]

        # 为了防止旧数据干扰，初始化前可以考虑清空旧规则 (仅限首次重构)
        # RechargeActivity.objects.all().delete()

        for idx, rule in enumerate(rules):
            RechargeActivity.objects.get_or_create(
                amount=rule["amount"],
                defaults={
                    "name": rule["name"],
                    "bonus_amount": 0.00,
                    "gift_coupon": coupon_100 if rule["num"] > 0 else None,
                    "gift_coupon_num": rule["num"],
                    "sort_order": idx + 1,
                    "is_active": True
                }
            )

    def get(self, request):
        if not RechargeActivity.objects.exists():
            self.init_default_rules()

        activities = RechargeActivity.objects.filter(is_active=True).order_by('sort_order')
        data = []
        for act in activities:
            coupon_num = act.gift_coupon_num or 0
            has_coupon = act.gift_coupon and coupon_num > 0

            data.append({
                "id": act.id,
                "name": act.name,
                "amount": float(act.amount),
                "gift_coupon_title": act.gift_coupon.title if has_coupon else "",
                "gift_coupon_num": coupon_num,
                "tags": f"送 {coupon_num * 100} 元券包" if has_coupon else ("享专属会员价" if act.amount >= 980 else "")
            })

        return Response({"code": 200, "msg": "获取成功", "data": data})

class SubmitRechargeOrderView(APIView):
    """
    发起充值并唤起支付 (已接入全局 DEBUG_PAY 物理隔离)
    """
    permission_classes = [IsAuthenticated]

    # -------------------------------------------------------------------
    # 微信V3 签名工具 (复用) - 实际项目中建议抽离为公共 Mixin 或 Utils
    # -------------------------------------------------------------------
    def _get_private_key(self):
        import os
        from cryptography.hazmat.primitives import serialization
        key_path = os.path.join(settings.BASE_DIR, settings.WECHAT_PAY['PRIVATE_KEY_PATH'])
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _rsa_sign(self, message):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        import base64
        private_key = self._get_private_key()
        signature = private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _build_auth_header(self, method, url_path, timestamp, nonce, body=""):
        sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._rsa_sign(sign_str)
        mchid = settings.WECHAT_PAY['MCHID']
        serial_no = settings.WECHAT_PAY['CERT_SERIAL_NO']
        header_val = (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
            f'nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{serial_no}"'
        )
        return header_val

    def post(self, request):
        activity_id = request.data.get('activity_id')

        try:
            activity = RechargeActivity.objects.get(id=activity_id, is_active=True)
        except RechargeActivity.DoesNotExist:
            return Response({"code": 400, "msg": "该储值套餐不存在或已下架"})

        # 检查微信身份
        pay_openid = getattr(request.user, 'openid', None)
        if not pay_openid:
            return Response({"code": 400, "msg": "用户尚未绑定微信身份，无法发起充值支付"})

        # 🌟 统一读取全局开关
        is_debug_pay = getattr(settings, 'DEBUG_PAY', False)

        # 生成充值订单号 (CZ开头的独立体系)
        order_sn = f"CZ{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

        # 记录充值订单 (状态0:待支付)
        recharge_order = RechargeOrder.objects.create(
            user=request.user,
            order_sn=order_sn,
            activity=activity,
            amount=activity.amount,
            pay_method=1  # 默认记录为微信支付
        )

        # =========================================================
        # 🌟 分支 A：全局测试环境拦截 (DEBUG_PAY = True)
        # =========================================================
        if is_debug_pay or pay_openid.startswith("MOCK_"):
            print(f"⚠️ [测试环境触发] 订单 {order_sn} 拦截真实支付，直接执行充值入账！")

            # 直接调用充值入账核心引擎 (你原本的底层业务)
            success, msg = handle_recharge_success(order_sn, transaction_id=f"MOCK_TRANS_{uuid.uuid4().hex[:8]}")

            if success:
                # 伪造一个能让前端假装拉起支付然后跳转成功的参数结构
                return Response({
                    "code": 200,
                    "msg": "【模拟支付环境】充值成功",
                    "data": {
                        "is_mock": True,  # 告诉前端这是假支付，直接弹 Toast 跳转即可
                        "order_sn": order_sn
                    }
                })
            else:
                return Response({"code": 500, "msg": f"模拟充值入账失败: {msg}"}, status=500)

        # =========================================================
        # 🌟 分支 B：真实生产环境微信支付 (DEBUG_PAY = False)
        # =========================================================
        try:
            url_path = "/v3/pay/transactions/jsapi"
            full_url = f"https://api.mch.weixin.qq.com{url_path}"
            timestamp = str(int(time.time()))
            nonce = uuid.uuid4().hex.upper()

            pay_price_cents = int(activity.amount * 100)

            body_data = {
                "appid": settings.WECHAT_PAY['APPID'],
                "mchid": settings.WECHAT_PAY['MCHID'],
                "description": f"储值套餐-{activity.name}",
                "out_trade_no": order_sn,
                # ⚠️ 注意：充值订单的回调地址，最好和你商品订单的回调地址分开，或者在回调里能根据前缀(CZ)做区分
                "notify_url": settings.WECHAT_PAY['NOTIFY_URL'],
                "amount": {"total": pay_price_cents, "currency": "CNY"},
                "payer": {"openid": pay_openid}
            }
            body_json = json.dumps(body_data, separators=(',', ':'))
            auth_header = self._build_auth_header("POST", url_path, timestamp, nonce, body_json)
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": auth_header,
                "User-Agent": "Django-WechatPay-V3-Client"
            }

            response = requests.post(full_url, data=body_json, headers=headers, timeout=10)
            if response.status_code != 200:
                return Response({"code": 500, "msg": f"微信统一下单失败: {response.text}"}, status=500)

            res_data = response.json()
            prepay_id = res_data.get('prepay_id')
            if not prepay_id:
                return Response({"code": 500, "msg": "未能获取到预支付会话标识"}, status=500)

            front_timestamp = str(int(time.time()))
            front_nonce = uuid.uuid4().hex.upper()
            package_str = f"prepay_id={prepay_id}"
            front_sign_message = f"{settings.WECHAT_PAY['APPID']}\n{front_timestamp}\n{front_nonce}\n{package_str}\n"
            front_signature = self._rsa_sign(front_sign_message)

            return Response({
                "code": 200,
                "msg": "获取微信支付参数成功",
                "data": {
                    "is_mock": False,
                    "order_sn": order_sn,
                    "timeStamp": front_timestamp,
                    "nonceStr": front_nonce,
                    "package": package_str,
                    "signType": "RSA",
                    "paySign": front_signature
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"code": 500, "msg": f"发起充值故障: {str(e)}"}, status=500)


from datetime import datetime, timedelta


class GrantBirthdayCouponView(APIView):
    """
    🌟 每月执行一次：自动给当月生日的正式会员发放 200 元代金券
    调用方式：可以通过服务器 Cron 定时任务发起 GET 请求 /app01/grant_birthday_coupons/
    """
    permission_classes = [AllowAny]  # 实际部署建议加上内部秘钥校验防盗刷

    def get(self, request):
        current_month = timezone.now().month

        # 1. 创建或获取 200元 面值的生日代金券模板
        birthday_coupon, _ = Coupon.objects.get_or_create(
            title="生日专属200元代金券",
            defaults={
                'coupon_type': 1,
                'money': 200.00,
                'discount_rate': 1.00,
                'min_consume': 0.00,
                'valid_days': 30,  # 生日券一般有效期 30 天
                'is_active': True
            }
        )

        # 2. 筛选出当月过生日，且星级在 1星(含) 以上的正式会员
        # 排除掉没有填写生日的用户
        birthday_users = User.objects.filter(
            birth_date__isnull=False,
            birth_date__month=current_month,
            user_type__gte=2
        )

        grant_count = 0
        already_granted_count = 0

        # 3. 开始派发
        for user in birthday_users:
            # 防重复检查：本月是否已经领过这类型的券
            has_granted = UserCoupon.objects.filter(
                user=user,
                coupon=birthday_coupon,
                start_time__month=current_month,
                start_time__year=timezone.now().year
            ).exists()

            if not has_granted:
                UserCoupon.objects.create(
                    user=user,
                    coupon=birthday_coupon,
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(days=birthday_coupon.valid_days),
                    is_used=False
                )
                grant_count += 1
            else:
                already_granted_count += 1

        msg = f"操作完成！{current_month}月生日且达标的会员共 {birthday_users.count()} 人。本次成功派发 200元代金券 {grant_count} 张，跳过已领取的 {already_granted_count} 人。"
        print(f"🎂 [生日礼遇] {msg}")

        return Response({"code": 200, "msg": msg})
# ===================== 短信验证码视图 =====================
@csrf_exempt
def send_sms_code(request):
    if request.method != "POST":
        return JsonResponse({"code": -1, "msg": "仅支持POST请求"})

    data = json.loads(request.body)
    phone = data.get("phone")
    if not phone or not phone.startswith("1") or len(phone) != 11:
        return JsonResponse({"code": -1, "msg": "手机号格式错误"})

    request = AcsRequest()
    request.set_domain("dypnsapi.aliyuncs.com")
    request.set_version("2017-05-25")
    request.set_action_name("SendSmsVerifyCode")
    request.set_method("POST")
    request.add_query_param("PhoneNumber", phone)
    request.add_query_param("SceneCode", "SMS_LOGIN")
    request.add_query_param("OutId", "your_out_id")

    try:
        response = client.do_action_with_exception(request)
        res_data = json.loads(response.decode("utf-8"))
        if res_data.get("Code") == "OK":
            return JsonResponse({
                "code": 200,
                "msg": "验证码发送成功",
                "data": {"biz_id": res_data.get("BizId")}
            })
        else:
            return JsonResponse({
                "code": -1,
                "msg": f"发送失败：{res_data.get('Message')}"
            })
    except Exception as e:
        return JsonResponse({"code": -1, "msg": f"系统异常：{str(e)}"})


@csrf_exempt
def verify_sms_code(request):
    if request.method != "POST":
        return JsonResponse({"code": -1, "msg": "仅支持POST请求"})

    data = json.loads(request.body)
    phone = data.get("phone")
    code = data.get("code")
    biz_id = data.get("biz_id")
    if not (phone and code and biz_id):
        return JsonResponse({"code": -1, "msg": "参数不完整"})

    request = AcsRequest()
    request.set_domain("dypnsapi.aliyuncs.com")
    request.set_version("2017-05-25")
    request.set_action_name("VerifySmsVerifyCode")
    request.set_method("POST")
    request.add_query_param("PhoneNumber", phone)
    request.add_query_param("VerifyCode", code)
    request.add_query_param("BizId", biz_id)

    try:
        response = client.do_action_with_exception(request)
        res_data = json.loads(response.decode("utf-8"))
        if res_data.get("Code") == "OK":
            return JsonResponse({"code": 200, "msg": "验证码验证成功"})
        else:
            return JsonResponse({
                "code": -1,
                "msg": f"验证失败：{res_data.get('Message')}"
            })
    except Exception as e:
        return JsonResponse({"code": -1, "msg": f"系统异常：{str(e)}"})

class GiveRegisterPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if request.data.get('phone') and user.phone != request.data.get('phone'):
            return Response({'code': 403, 'msg': '手机号与登录会员不一致', 'data': None})
        success, msg = user.add_points(
            points=0,
            points_type=1,
            related_desc='前端手动触发-新用户注册积分'
        )
        return Response({
            'code': 200 if success else 400,
            'msg': msg,
            'data': {'current_points': user.points}
        })

class PointsRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        points_type = request.query_params.get('type', '')
        queryset = PointsRecord.objects.filter(user=user)
        if points_type and points_type.isdigit():
            queryset = queryset.filter(points_type=int(points_type))
        serializer = PointsRecordSerializer(queryset, many=True)
        return Response({
            'code': 200,
            'msg': '获取积分明细成功',
            'data': {
                'current_points': user.points,
                'record_list': serializer.data
            }
        })

# ===================== 门店相关接口 =====================
class AreaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            area_list = Area.objects.all()
            data = [
                {
                    "id": area.id,
                    "name": area.name,
                    "desc": area.desc,
                }
                for area in area_list
            ]
            return Response({
                "code": 200,
                "msg": "获取门店列表成功",
                "data": data
            })
        except Exception as e:
            return Response({
                "code": 500,
                "msg": f"获取门店失败：{str(e)}",
                "data": []
            }, status=500)

@csrf_exempt
def video_proxy(request):
    video_url = request.GET.get('url', '')

    # 你的安全校验逻辑 (假设 BASE_URL 已在 settings 中定义)
    # from django.conf import settings
    # if not video_url or not video_url.startswith(f"{settings.BASE_URL}/media/"):
    #     return HttpResponse('无效URL', status=400)

    # 1. 【关键】获取并准备 Range 请求头
    # 手机端会发送类似 "bytes=0-" 的请求头，必须转发给原始服务器
    proxy_headers = {}
    if 'HTTP_RANGE' in request.META:
        proxy_headers['Range'] = request.META['HTTP_RANGE']

    try:
        # 2. 向原始地址发起请求
        # stream=True 必选，避免将几十MB的视频读入内存导致服务器宕机
        response = requests.get(video_url, headers=proxy_headers, stream=True, timeout=15)

        # 3. 构造流式响应
        # 建议 chunk_size 调小一点（如 8KB），1MB 太大会导致初次加载感官变慢
        streaming_response = StreamingHttpResponse(
            response.iter_content(chunk_size=8192),
            status=response.status_code  # 转发原始状态码（通常是 206）
        )

        # 4. 【核心修复】转发必要的视频协议响应头
        # 只有告诉前端 "Accept-Ranges: bytes"，手机端才能正常解析和拖动
        streaming_response['Content-Type'] = response.headers.get('Content-Type', 'video/mp4')
        streaming_response['Accept-Ranges'] = 'bytes'

        # 转发分段信息（Range 相关头）
        if 'Content-Range' in response.headers:
            streaming_response['Content-Range'] = response.headers['Content-Range']
        if 'Content-Length' in response.headers:
            streaming_response['Content-Length'] = response.headers['Content-Length']

        return streaming_response

    except Exception as e:
        return HttpResponse(f'代理失败：{str(e)}', status=500)

# 优惠券领取
def claim_coupon(request):
    coupon_id = request.POST.get('id')
    expire_at = timezone.now() + timedelta(days=90)

    UserCoupon.objects.create(
        user=request.user,
        coupon_id=coupon_id,
        end_time=expire_at
    )
    return JsonResponse({"status": True, "msg": "领取成功，有效期90天"})

# 用户统计
def get_user_stats(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    print(f"--- 原始 Authorization 头内容: {auth_header} ---")
    if not request.user.is_authenticated:
        print("警告：收到一个匿名请求，可能是 Token 已失效")
        return JsonResponse({
            "code": 401,
            "msg": "身份认证失败，请重新登录",
            "couponCount": 0
        })

    count = UserCoupon.objects.filter(user=request.user).count()
    print(f"用户 {request.user.username} 的优惠券数量: {count}")

    return JsonResponse({
        "code": 200,
        "couponCount": count
    })

def get_user_coupons(request):
    queryset = UserCoupon.objects.filter(user=request.user).order_by('-add_time')

class UserStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_count = UserCoupon.objects.filter(user=request.user).count()
        return Response({
            "code": 200,
            "couponCount": user_count
        })

class UserCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            only_valid = request.query_params.get('only_valid', 'false').lower() == 'true'
            coupon_type = request.query_params.get('type')
            coupon_type = int(coupon_type) if coupon_type and coupon_type.isdigit() else None

            coupons = request.user.get_coupons(only_valid=only_valid, coupon_type=coupon_type)
            serializer = UserCouponSerializer(coupons, many=True)

            stats = request.user.get_coupon_stats()
            stats_serializer = UserCouponStatsSerializer(stats)

            return Response({
                'code': 200,
                'msg': '获取优惠券成功',
                'data': {
                    'stats': stats_serializer.data,
                    'coupons': serializer.data
                }
            })
        except Exception as e:
            logger.error(f'获取用户优惠券失败：{str(e)}')
            return Response({
                'code': 500,
                'msg': f'获取优惠券失败：{str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserCouponUseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        coupon_id = request.data.get('coupon_id')
        order_sn = request.data.get('order_sn')

        if not coupon_id or not order_sn:
            return Response({
                'code': 400,
                'msg': '优惠券ID和订单号不能为空',
                'data': None
            })

        try:
            coupon = UserCoupon.objects.get(
                id=coupon_id,
                user=request.user,
                is_used=False,
                end_time__gt=timezone.now()
            )

            coupon.is_used = True
            coupon.used_time = timezone.now()
            coupon.order_sn = order_sn
            coupon.save()

            return Response({
                'code': 200,
                'msg': '优惠券使用成功',
                'data': {
                    'coupon_id': coupon.id,
                    'order_sn': order_sn
                }
            })
        except UserCoupon.DoesNotExist:
            return Response({
                'code': 400,
                'msg': '优惠券不可用（已使用/已过期/不存在）',
                'data': None
            })
        except Exception as e:
            logger.error(f'使用优惠券失败：{str(e)}')
            return Response({
                'code': 500,
                'msg': f'使用优惠券失败：{str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 顺丰物流配置
PARTNER_ID = "LSQJS1HHHWZW"
CHECK_WORD = "zfIRMBfdRKaZiJfOea1vm40V7utd9x2z"
URL = "https://sfapi-sbox.sf-express.com/std/service"


def query_sf_routes(logistics_no_list):
    biz_content = {
        "language": "zh-CN",
        "trackingType": "1",
        "trackingNumber": logistics_no_list,
        "methodType": "1"
    }
    msg_data = json.dumps(biz_content, separators=(',', ':'))

    request_id = str(uuid.uuid4()).replace("-", "")
    timestamp = str(int(time.time() * 1000))
    service_code = 'EXP_RECE_SEARCH_ROUTES'

    origin_str = f"{msg_data}{timestamp}{CHECK_WORD}"
    md5_hash = hashlib.md5(origin_str.encode('utf-8')).digest()
    msg_digest = base64.b64encode(md5_hash).decode('utf-8')

    payload = {
        'partnerID': PARTNER_ID,
        'requestID': request_id,
        'serviceCode': service_code,
        'timestamp': timestamp,
        'msgDigest': msg_digest,
        'msgData': msg_data,
        'format': 'json'
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    }
    try:
        response = requests.post(URL, data=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f"顺丰接口调用失败：{str(e)}")

def extract_sf_logistics_info(raw_json_str):
    try:
        outer_data = json.loads(raw_json_str)
        if outer_data.get("apiResultCode") != "A1000":
            raise Exception(f"接口返回错误：{outer_data.get('apiErrorMsg', '未知错误')}")

        inner_data = json.loads(outer_data["apiResultData"])
        if not inner_data.get("success"):
            raise Exception(f"物流查询失败：{inner_data.get('errorMsg', '未知错误')}")

        phone_pattern = re.compile(r'1[3-9]\d{9}')
        name_pattern = re.compile(r'【([^，\s]+)，(联系电话|电话)：')

        temp_result = []
        route_resps = inner_data["msgData"]["routeResps"]

        for resp in route_resps:
            mail_no = resp["mailNo"]
            for route in resp["routes"]:
                accept_time = route["acceptTime"]
                accept_address = route["acceptAddress"]
                status_name = route['firstStatusName']
                remark = route["remark"]

                try:
                    logistics_time = datetime.strptime(accept_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logistics_time = timezone.now()

                status_code = SF_STATUS_MAP.get(status_name, 601)

                phone = phone_pattern.search(remark).group() if phone_pattern.search(remark) else None
                contact = name_pattern.search(remark).group(1) if name_pattern.search(remark) else None

                temp_result.append({
                    "运单号": mail_no,
                    "时间": logistics_time,
                    "地点": accept_address,
                    "物流状态编码": status_code,
                    "物流状态名称": status_name,
                    "派件联系人": contact,
                    "联系电话": phone,
                    "备注": remark
                })

        unique_groups = defaultdict(dict)
        for item in temp_result:
            group_key = (item["运单号"], item["物流状态编码"])
            if not unique_groups[group_key] or item["时间"] > unique_groups[group_key]["时间"]:
                unique_groups[group_key] = item

        final_result = sorted(unique_groups.values(), key=lambda x: x["时间"])

        for idx, item in enumerate(final_result):
            item["排序"] = idx

        return final_result, len(temp_result)

    except Exception as e:
        raise Exception(f"数据解析/去重失败：{str(e)}")

def express_create(request):
    if request.method == "POST":
        form = ExpressCreateForm(request.POST)
        if form.is_valid():
            order = form.cleaned_data["order"]
            logistics_no_list = form.cleaned_data["logistics_no"]
            logistics_company = form.cleaned_data["logistics_company"]

            try:
                raw_data = query_sf_routes(logistics_no_list)
                logistics_info_list, raw_count = extract_sf_logistics_info(raw_data)

                if logistics_info_list:
                    current_logistics_nos = [info["运单号"] for info in logistics_info_list]
                    ExpressLogistics.objects.filter(
                        order=order,
                        logistics_no__in=current_logistics_nos
                    ).delete()

                created_count = 0
                for info in logistics_info_list:
                    ExpressLogistics.objects.create(
                        order=order,
                        order_sn=order.order_sn,
                        logistics_no=info["运单号"],
                        logistics_company=logistics_company,
                        logistics_time=info["时间"],
                        accept_address=info["地点"],
                        logistics_status=info["物流状态编码"],
                        logistics_status_name=info["物流状态名称"],
                        courier_name=info["派件联系人"],
                        courier_phone=info["联系电话"],
                        remark=info["备注"],
                        sort=info["排序"]
                    )
                    created_count += 1

                if logistics_no_list:
                    order.logistics_no = logistics_no_list[0]
                    order.logistics_company = logistics_company
                    order.save(update_fields=["logistics_no", "logistics_company"])

                messages.success(request, "运单创建成功！")
                return redirect("express_list")

            except Exception as e:
                messages.error(request, f"操作失败：{str(e)}")
    else:
        form = ExpressCreateForm()

    return render(request, "app01/express_create.html", {"form": form})

def express_list(request):
    # 如果接口被前端直接调用，需要确保能识别用户
    user = request.user
    if not user or not user.is_authenticated:
        return JsonResponse({"code": 401, "msg": "未登录，无权查询物流"})

    return_format = request.GET.get('format', '')
    order_sns_str = request.GET.get('order_sns', '')
    order_sns = order_sns_str.split(',') if order_sns_str else []

    # ==========================================================
    # 🌟 核心修复：权限漏斗过滤
    # 提前查出当前用户【有权访问】的订单单号，再去查物流
    # ==========================================================
    if user.is_superuser:
        allowed_order_sns = order_sns # 超级管理员看所有
    else:
        allowed_order_sns = Order.objects.filter(
            order_sn__in=order_sns,
            is_delete=False
        ).filter(
            Q(user=user) |
            Q(fulfill_by=user) |
            Q(user__parent_user=user)
        ).values_list('order_sn', flat=True)

    # 用过滤后合法的单号去查询物流表
    logistics_list = ExpressLogistics.objects.filter(
        order_sn__in=allowed_order_sns,
        is_delete=False
    ).order_by("-logistics_time")

    # 下面的格式化返回代码保持不变
    if return_format == 'json' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        data = []
        for item in logistics_list:
            data.append({
                "order_sn": item.order_sn,
                "logistics_no": item.logistics_no,
                "logistics_company": item.logistics_company,
                "logistics_time": item.logistics_time.strftime("%Y-%m-%d %H:%M:%S") if item.logistics_time else "",
                "accept_address": item.accept_address,
                "logistics_status_name": item.logistics_status_name,
                "courier_name": item.courier_name or "",
                "courier_phone": item.courier_phone or ""
            })
        return JsonResponse({
            "code": 200,
            "msg": "success",
            "data": data
        })

    context = {
        'logistics_list': logistics_list,
        'order_sns': order_sns_str
    }
    return render(request, 'app01/express_list.html', context)

# ===================== 积分抵扣接口 =====================
class PointExchangeCalculateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            goods_list = request.data.get("goods_list", [])
            deduct_point = int(request.data.get("deduct_point", 0))
            user = request.user

            if not goods_list:
                return Response({"code": 400, "msg": "请选择商品"}, status=400)
            if deduct_point < 0:
                return Response({"code": 400, "msg": "抵扣积分不能为负数"}, status=400)

            total_money = 0.0
            invalid_goods = []
            cart_items = []

            for item in goods_list:
                cart_id = item.get("cart_id")
                num = int(item.get("num", 1))

                if not cart_id or num < 1:
                    return Response({"code": 400, "msg": f"购物车参数错误：cart_id={cart_id}"}, status=400)

                cart = get_object_or_404(Cart, id=cart_id, user=user)
                goods = cart.goods

                if not goods.can_point_exchange:
                    invalid_goods.append(goods.name)
                    continue

                total_money += float(goods.member_price * num)
                cart_items.append({
                    "cart": cart,
                    "num": num,
                    "goods": goods
                })

            if invalid_goods:
                return Response({
                    "code": 403,
                    "msg": f"以下商品不支持积分兑换：{','.join(invalid_goods)}",
                    "data": {"invalid_goods": invalid_goods}
                }, status=403)

            max_deduct_point = int(total_money * 100)
            actual_deduct_point = min(deduct_point, max_deduct_point, user.points)
            deduct_money = actual_deduct_point * 0.01
            actual_pay_money = max(total_money - deduct_money, 0)

            return Response({
                "code": 200,
                "msg": "积分抵扣计算成功",
                "data": {
                    "total_money": round(total_money, 2),
                    "request_deduct_point": deduct_point,
                    "max_deduct_point": max_deduct_point,
                    "actual_deduct_point": actual_deduct_point,
                    "deduct_money": round(deduct_money, 2),
                    "actual_pay_money": round(actual_pay_money, 2),
                    "user_current_points": user.points,
                    "points_shortage": max(deduct_point - user.points, 0)
                }
            })

        except Exception as e:
            logger.error(f"积分抵扣计算失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"计算失败：{str(e)}"}, status=500)

class UserPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "code": 200,
            "msg": "success",
            "data": {
                "points": request.user.points or 0
            }
        })

class DeductPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get('order_id')
            deduct_point = int(request.data.get('deduct_point', 0))
            user = request.user

            if not order_id:
                return Response({"code": 400, "msg": "订单ID不能为空"})
            if deduct_point < 0:
                return Response({"code": 400, "msg": "抵扣积分不能为负数"})

            try:
                order = Order.objects.get(id=order_id, user=user, is_delete=False)
            except Order.DoesNotExist:
                return Response({"code": 404, "msg": "订单不存在"})

            if order.status not in [1, 2, 3]:
                return Response(
                    {"code": 400, "msg": f"订单状态异常（当前：{order.get_status_display()}），仅已支付订单可扣减积分"})

            order_items = order.items.all()
            goods_list = [item.goods for item in order_items if item.goods]

            success, msg = order.deduct_user_points(user, deduct_point, goods_list)

            if success:
                return Response({"code": 200, "msg": msg})
            else:
                return Response({"code": 400, "msg": msg})

        except Exception as e:
            logger.error(f"扣减积分失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"扣减积分失败：{str(e)}"})

@csrf_exempt
@require_POST
def ai_chat_api(request):
    print("=" * 50)
    print("INFO: 后端AI接口已调用")
    try:
        data = json.loads(request.body)
        member_id = data.get("user_id")
        question = data.get("question", "").strip()

        # 🔥 新增：获取前端传递的 model_type，默认使用免费小模型 'lite'
        model_type = data.get("model_type", "lite")

        if not member_id or not question:
            return JsonResponse({"code": 400, "msg": "参数错误"}, safe=False)

        # 查询用户
        try:
            user = User.objects.get(member_id=member_id)
        except User.DoesNotExist:
            return JsonResponse({"code": 404, "msg": "用户不存在"}, safe=False)

        # 🔥 拦截器：如果选择专业大模型，必须先检查积分余额
        # ⚠️ 注意：这里假设你的用户积分字段名叫 points，如果叫 integral 或其他名字，请自行替换
        user_points = getattr(user, 'points', 0)
        if model_type == "pro" and user_points <= 0:
            return JsonResponse({
                "code": 403,
                "msg": "积分不足，无法使用专业大模型，请使用快速小模型或去获取积分。"
            }, safe=False)

        session, _ = AIChatSession.objects.get_or_create(user=user)

        # 🔥 调用双擎 AI 接口 (现在返回的是字典)
        ai_result = get_ai_answer(question, model_type)

        # 异常处理：如果底层模型调用失败，直接返回报错
        if ai_result.get("status") == "error":
            return JsonResponse({"code": 500, "msg": ai_result.get("answer")}, safe=False)

        # 提取答案和 Token 消耗
        answer = ai_result.get("answer", "")
        total_tokens = ai_result.get("total_tokens", 0)
        points_deducted = 0

        # 🔥 核心：执行扣除积分逻辑
        if model_type == "pro" and total_tokens > 0:
            # 1 积分抵扣 10 个 token，向上取整 (例如 101 个 token = 11 积分)
            points_deducted = math.ceil(total_tokens / 10)

            # 扣除积分并保存
            if hasattr(user, 'points'):
                user.points -= points_deducted
                # 兜底防护：防止异常情况下积分被扣成负数
                if user.points < 0:
                    user.points = 0
                user.save()

        try:
            print(f"INFO: AI返回成功 | 模型:{model_type} | Token消耗:{total_tokens} | 扣除积分:{points_deducted}")
        except:
            pass

        # 保存对话
        AIChatMessage.objects.create(session=session, role="user", content=question)
        AIChatMessage.objects.create(
            session=session,
            role="assistant",
            content=answer,
            model_type=model_type,  # 记录是 lite 还是 pro
            tokens_used=total_tokens,  # 记录真实消耗的 token
            points_deducted=points_deducted  # 记录扣除了多少积分
        )

        # 返回给前端（顺便把扣除的积分和剩余积分带给前端，方便 UI 弹窗提示）
        return JsonResponse({
            "code": 200,
            "data": {
                "answer": answer,
                "model_type": model_type,
                "points_deducted": points_deducted,
                "remaining_points": getattr(user, 'points', 0)
            }
        }, safe=False)

    except Exception as e:
        try:
            print(f"ERROR: 接口异常 - {str(e)}")
        except:
            pass
        return JsonResponse({"code": 500, "msg": "服务异常"}, safe=False)

# 对话历史接口（完全不变）
@csrf_exempt
@require_POST
def get_chat_history_api(request):
    try:
        data = json.loads(request.body)
        member_id = data.get("user_id")
        user = User.objects.get(member_id=member_id)
        session = AIChatSession.objects.get(user=user)
        messages = session.messages.all().values("role", "content", "create_time")
        return JsonResponse({"code": 200, "data": list(messages)}, safe=False)
    except Exception:
        return JsonResponse({"code": 200, "data": []}, safe=False)

from django.shortcuts import render
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

# ==========================================
# 🌟 小程序必备：引入 JWT 和 数据库模型
# ==========================================
from rest_framework_simplejwt.authentication import JWTAuthentication

# ==========================================
# 🌟 基础辅助函数 (完全保留原版)
# ==========================================
def safe_print(msg):
    """安全打印：解决终端对 Emoji 或特殊字符的兼容性问题"""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('gbk', errors='replace').decode('gbk'), flush=True)

def load_knowledge():
    """实时加载 products.json，适配最新的中文键名结构"""
    try:
        json_path = os.path.join(settings.BASE_DIR, 'data','products.json')

        if not os.path.exists(json_path):
            safe_print(f"[ERROR] 找不到文件: {json_path}")
            return {}

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 🌟 适配：剥开 "知识库" 嵌套
            if "知识库" in data:
                return data["知识库"]
            return data
    except Exception as e:
        safe_print(f"[ERROR] 知识库读取失败: {e}")
        return {}

def get_questionnaire_api(request):
    try:
        json_path = os.path.join(settings.BASE_DIR, 'data','questionnaire.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 🌟 加上这一行打印，看看后端读取到的到底是什么
        # print(f"后端读取到的题库数据: {data}")

        # 确保返回格式统一
        return JsonResponse({"code": 200, "data": data})
    except Exception as e:
        print(f"读取异常: {e}")
        return JsonResponse({"code": 500, "msg": "问卷库加载失败"})

# ==========================================
# 🌟 核心硬逻辑：肤质评估算法 (完全保留原版)
# ==========================================
def evaluate_skin_type(answers):
    """基于问卷 Q1-Q8 的硬规则判断肤质优先级"""
    q1, q2 = answers.get('Q1', ''), answers.get('Q2', '')
    q3, q4 = answers.get('Q3', ''), answers.get('Q4', '')
    q5, q6 = answers.get('Q5', ''), answers.get('Q6', '')
    q7, q8 = answers.get('Q7', ''), answers.get('Q8', '')

    tags = []
    base_type = "中性皮肤"

    # 1. 基础肤质判定
    if q1 == 'A':
        base_type = "干性皮肤"
    elif q1 == 'B':
        base_type = "中性皮肤"
    elif q1 == 'C':
        base_type = "混合性皮肤"
    elif q1 == 'D':
        base_type = "油性皮肤"

    # 混合性判定修正
    if q1 == 'C' and q2 == 'C': base_type = "混合性皮肤"

    # 2. 核心症状判定 (按优先级)
    if q3 in ['C', 'D'] or q7 == 'D' or q8 == 'C': tags.append("敏感肌肤")
    if q4 in ['C', 'D'] or q8 == 'D': tags.append("痘痘肌肤")
    if q5 in ['B', 'C', 'D'] or q8 == 'E': tags.append("色斑肌肤")
    if q6 in ['B', 'C', 'D'] or q8 == 'F': tags.append("衰老肌肤")

    if base_type not in tags: tags.append(base_type)

    # 3. 排序 (黄金原则：屏障 > 抗炎 > 控油 > 美白 > 抗老)
    priority_map = {
        "敏感肌肤": 1, "痘痘肌肤": 2, "油性皮肤": 3, "混合性皮肤": 4,
        "干性皮肤": 5, "中性皮肤": 6, "色斑肌肤": 7, "衰老肌肤": 8
    }
    tags.sort(key=lambda x: priority_map.get(x, 99))
    return tags[:3]

import asyncio
from asgiref.sync import sync_to_async
# 引入 ollama 的异步客户端
from ollama import AsyncClient


# ==========================================
# 🌟 数据库与验证操作 (同步转异步包裹器)
# ==========================================
@sync_to_async
def async_authenticate(request):
    """异步化 JWT 验证"""
    jwt_authenticator = JWTAuthentication()
    return jwt_authenticator.authenticate(request)

@sync_to_async
def get_latest_profile(p_id):
    """强制刷新并获取数据库中最新的档案，防止被 ORM 缓存"""
    return UserSkinProfile.objects.get(id=p_id)


# ==========================================
# 🌟 数据库与验证操作 (同步转异步包裹器)
# ==========================================
@sync_to_async
def async_manage_profile(user, step_val, sub_name="未命名", data_dict=None):
    if data_dict is None:
        data_dict = {}

    # 1. 查找或创建当前被测人的档案
    profile = UserSkinProfile.objects.filter(user=user, subject_name=sub_name).order_by('-id').first()
    if not profile:
        profile = UserSkinProfile.objects.create(user=user, subject_name=sub_name)

    # 2. 根据阶段精准保存
    if step_val == 'submit_questionnaire':
        try:
            # ==========================================
            # 🌟 新增逻辑：清洗前端传来的问卷数据
            # 过滤掉用户没有填写的、空的补充回答（如 Q1_sup: ""）
            # ==========================================
            cleaned_answers = {}
            for key, val in data_dict.items():
                if isinstance(val, str):
                    val = val.strip()
                # 只有当值不为空时，才保存进字典（若没有补充，则不保存）
                if val != "":
                    cleaned_answers[key] = val

            # 将清洗后、不含空补充的字典存入数据库
            profile.answers = cleaned_answers

            # 评估算法依然只读取 Q1~Q8，完全不受 Q1_sup 等补充字段的影响！
            skin_tags = evaluate_skin_type(cleaned_answers)
            profile.skin_tags = skin_tags

            # 🌟 核心修复：清空旧的缓存报告
            profile.final_report = ""
            profile.skincare_plan = ""
            profile.image_analysis = ""

            profile.save(update_fields=['answers', 'skin_tags', 'final_report', 'skincare_plan', 'image_analysis',
                                        'update_time'])
            safe_print(f"✅ 档案 [{sub_name}] - 问卷及补充已更新，旧缓存已清空")
        except Exception as e:
            safe_print(f"❌ 问卷解析或肤质计算失败: {e}")

    elif step_val == 'save_final_report':
        if 'final_report' in data_dict:
            profile.final_report = data_dict['final_report']
            profile.save(update_fields=['final_report', 'update_time'])
            safe_print(f"✅ 档案 [{sub_name}] - 蓝博士综合定性报告已存库！")

        if 'skincare_plan' in data_dict:
            profile.skincare_plan = data_dict['skincare_plan']
            profile.save(update_fields=['skincare_plan', 'update_time'])
            safe_print(f"✅ 档案 [{sub_name}] - 私教终极居家方案已存库！")

    return profile

# ==========================================
# 🌟 流式对话接口 (包含预运算、秒出和完整提示词)
# ==========================================
from openai import AsyncOpenAI
# 🌟 引入线程池与数据库连接管理器（高并发基石）
from concurrent.futures import ThreadPoolExecutor
from django.db import connections

# 🌟 初始化全局并发线程池，最大并发数限制为10（保护服务器不被压垮）
AI_PRE_COMPUTE_POOL = ThreadPoolExecutor(max_workers=10)

@csrf_exempt
async def wx_chat_stream_api(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # 注意：你需要确保 async_authenticate 等辅助函数已经定义
        auth_result = await async_authenticate(request)
        if auth_result is None:
            return JsonResponse({"error": "未提供有效Token"}, status=401)
        current_user, token = auth_result
    except Exception as e:
        return JsonResponse({"error": f"身份验证失败: {str(e)}"}, status=401)

    user_query = request.POST.get('query', '').strip()
    step = request.POST.get('step', 'chat').strip()
    sub_name = request.POST.get('subject_name', '').strip()

    safe_print(
        f"\n[{time.strftime('%H:%M:%S')}] [请求入栈] 用户: {current_user.member_id} | 步骤: {step} | 被测人: {sub_name}")

    # ==========================================
    # 🌟 AI 引擎安全配置加载
    # ==========================================
    provider_key = getattr(settings, 'ACTIVE_AI_PROVIDER', 'ollama')
    ai_config = getattr(settings, 'AI_PROVIDERS', {}).get(provider_key, {})

    raw_api_key = ai_config.get("api_key", "")
    current_api_key = str(raw_api_key).strip()

    if not current_api_key or current_api_key in ["ARK_API_KEY", "os.getenv('ARK_API_KEY')", "sk-empty"]:
        current_api_key = os.getenv("ARK_API_KEY", "").strip()

    current_base_url = ai_config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3").strip()
    current_model = ai_config.get("model_name", "").strip()

    async def generate_response(user, step_val, query_val, subject_name):
        try:
            answers_dict = {}
            if step_val == 'submit_questionnaire':
                try:
                    payload = json.loads(query_val)
                    answers_dict = payload.get('answers', {})
                except:
                    pass

            profile = await async_manage_profile(user, step_val, subject_name, answers_dict)

            # ==================== 步骤 2：问卷提交 ====================
            if step_val == 'submit_questionnaire':
                yield f"📝 **被测人 [{profile.subject_name}] 的深度测肤问卷已完成分析！**\n\n宝贝，系统已经为您建立了基础肌肤档案。接下来，请点击下方按钮，蓝博士将为您生成深度诊断报告。".encode(
                    'utf-8')
                yield b"[SHOW_STEP_3]"
                return

            # ==================== 🌟 秘密步骤：独立线程静默预运算 ====================
            if step_val == 'pre_analyze':
                def run_pre_compute_task():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        async def safe_bg_compute():
                            bg_client = AsyncOpenAI(api_key=current_api_key, base_url=current_base_url)
                            target_skin_keys = profile.skin_tags if profile.skin_tags else ["中性皮肤"]
                            primary_skin = target_skin_keys[0]
                            fresh_db = load_knowledge()
                            skin_types_data = fresh_db.get("皮肤类型", [])

                            # 🚀 预运算 1：生成定性分析报告
                            if not profile.final_report:
                                combined_principles = "".join([
                                    f"【{skin_key} 护肤原则】：{next((item.get('护肤原则', '') for item in skin_types_data if item.get('皮肤类型') == skin_key), '')}\n"
                                    for skin_key in target_skin_keys
                                ])
                                prompt_report = f"你是专业护肤私教蓝博士。\n确诊肤质：【{', '.join(target_skin_keys)}】。\n原则参考：\n{combined_principles}\n请专业、温柔地解释为何得出此肤质结论，并阐述护理逻辑。禁止推荐具体产品。结尾：‘宝贝，核心问题分析完毕！下一步，蓝博士将为您精准匹配产品方案...’"

                                stream_report = await bg_client.chat.completions.create(
                                    model=current_model, messages=[{'role': 'user', 'content': prompt_report}],
                                    stream=True, temperature=0.2
                                )
                                full_report = ""
                                async for chunk in stream_report:
                                    if chunk.choices[0].delta.content:
                                        full_report += chunk.choices[0].delta.content
                                if full_report.strip():
                                    await async_manage_profile(user, 'save_final_report', subject_name,
                                                               {'final_report': full_report})

                            # 🚀 预运算 2：生成护肤方案 Markdown 表格
                            if not profile.skincare_plan:
                                skin_data = next(
                                    (item for item in skin_types_data if item.get("皮肤类型") == primary_skin), {})
                                treatment = json.dumps(skin_data.get("居家产品方案", {}), ensure_ascii=False)
                                tips = json.dumps(skin_data.get("注意事项", []), ensure_ascii=False)
                                prompt_plan = f"你是专业护肤私教蓝博士。\n肤质：{primary_skin}。\n【居家方案】：{treatment}\n【注意事项】：{tips}\n请务必输出一个美观的 Markdown 格式护肤方案表格。包含：【步骤】(早/晚/店)、【推荐产品及用法】、【注意事项】三列。不废话。"

                                stream_plan = await bg_client.chat.completions.create(
                                    model=current_model, messages=[{'role': 'user', 'content': prompt_plan}],
                                    stream=True, temperature=0.1
                                )
                                full_plan = ""
                                async for chunk in stream_plan:
                                    if chunk.choices[0].delta.content:
                                        full_plan += chunk.choices[0].delta.content
                                if full_plan.strip():
                                    await async_manage_profile(user, 'save_final_report', subject_name,
                                                               {'skincare_plan': full_plan})

                        loop.run_until_complete(safe_bg_compute())
                    except Exception as bg_err:
                        safe_print(f"❌ 后台预运算崩溃: {bg_err}")
                    finally:
                        loop.close()
                        # 强制释放数据库连接防挤爆
                        connections.close_all()

                AI_PRE_COMPUTE_POOL.submit(run_pre_compute_task)
                yield b""
                return

            # ==================== 步骤 3/4：打字机流式输出 ====================
            elif step_val in ['analyze', 'skip_and_analyze', 'generate_plan']:

                # 🌟 安全破冰垫片：发送 1024 个连续空格，瞬间撑爆底层网络缓冲墙，强行开启流式通道！
                padding = " " * 1024
                yield padding.encode('utf-8')
                is_plan = (step_val == 'generate_plan')

                # 轮询等待后台预运算结果（共50秒）
                for wait_time in range(25):
                    profile = await get_latest_profile(profile.id)
                    target_text = profile.skincare_plan if is_plan else profile.final_report

                    if target_text:
                        safe_print(f"INFO: 命中缓存，向前端推送流式数据...")
                        # 每次推送 10 个字符，稍微间隔，防止网络层自动合包
                        for i in range(0, len(target_text), 10):
                            yield target_text[i:i + 10].encode('utf-8')
                            await asyncio.sleep(0.05)

                        if not is_plan:
                            yield b"[SHOW_STEP_4]"
                        return
                    await asyncio.sleep(2)

                # 兜底：如果超时没算完，直接给前端个提示
                yield "\n\n稍微有些超时了，请重新点击获取哦~".encode('utf-8')
                return

        except Exception as e:
            yield f"\n\n❌ 运行异常: {str(e)}".encode('utf-8')

    response = StreamingHttpResponse(
        generate_response(current_user, step, user_query, sub_name),
        content_type='application/octet-stream'
    )
    # 彻底禁用所有代理的缓存拦截
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache, no-transform'
    return response

import urllib.request
from django.http import JsonResponse
import urllib.error  # 引入用于捕获真实报错的模块
# ===================== 公共签名函数（全局复用） =====================
def jd_sign(algorithm: str, data: bytes, secret: bytes) -> str:
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

# ===================== 1. 京东预校验接口 =====================

@csrf_exempt
@require_http_methods(["POST"])
def jd_order_precheck(request):
    try:
        req_data = json.loads(request.body)
        order_sn = req_data.get("order_sn", "ceshi123")
        sender = req_data.get("sender", {})
        receiver = req_data.get("receiver", {})
        quantity = req_data.get("quantity", 1)

        # 🌟 获取前端传来的包裹动态数据（兜底默认值为你原本设定的 0.5kg 和 0.001体积）
        cargo_name = req_data.get("cargo_name", "护肤品")
        try:
            cargo_weight = float(req_data.get("cargo_weight", 0.5))
            cargo_volume = float(req_data.get("cargo_volume", 0.001))
        except (ValueError, TypeError):
            cargo_weight = 0.5
            cargo_volume = 0.001

        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]  # 🌟 修复：改回你原本正确的 UAT 测试环境
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        customer_code = config["CUSTOMER_CODE"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        path = "/ecap/v1/orders/precheck"

        # 🌟 保持你原本完全正确的数据结构，仅替换 cargoes 里的值
        body = json.dumps([{
            "orderId": order_sn,
            "senderContact": {
                "name": sender.get('name', ''),
                "mobile": sender.get('mobile', ''),
                "fullAddress": sender.get('fullAddress', '')
            },
            "receiverContact": {
                "name": receiver.get('name', ''),
                "mobile": receiver.get('mobile', ''),
                "fullAddress": receiver.get('fullAddress', '')
            },
            "orderOrigin": 1,
            "customerCode": customer_code,
            "productsReq": {"productCode": "ed-m-0001"},
            "settleType": 3,
            "cargoes": [{
                "name": cargo_name,  # 动态提取
                "quantity": quantity,
                "weight": cargo_weight,  # 动态提取
                "volume": cargo_volume  # 动态提取
            }]
        }], ensure_ascii=False)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sign_content = "".join([
            app_secret,
            "access_token", access_token,
            "app_key", app_key,
            "method", path,
            "param_json", body,
            "timestamp", timestamp,
            "v", version,
            app_secret
        ])
        sign_result = jd_sign(algorithm, sign_content.encode("utf-8"), app_secret.encode("utf-8"))

        queries = {
            "LOP-DN": domain, "app_key": app_key, "access_token": access_token,
            "timestamp": timestamp, "v": version, "sign": sign_result, "algorithm": algorithm
        }
        url = f"{base_uri}{path}?{urlencode(queries)}"
        headers = {
            "lop-tz": str(int(-time.timezone / 3600)),
            "User-Agent": "lop-http/python3",
            "content-type": "application/json;charset=utf-8",
        }

        opener = urllib.request.build_opener()
        req = urllib.request.Request(url=url, data=body.encode("utf-8"), headers=headers)
        resp = opener.open(req, timeout=10)
        jd_res = json.loads(resp.read().decode("utf-8"))

        # 🌟 提取预估运费并返回给前端
        if jd_res.get("success") is True:
            total_freight = jd_res.get("data", {}).get("totalFreightStandard", 0)

            return JsonResponse({
                "code": 200,
                "data": {
                    "success": True,
                    "freight": total_freight,
                    "error_msg": ""
                }
            })
        else:
            return JsonResponse({
                "code": 200,
                "data": {
                    "success": False,
                    "error_msg": jd_res.get("msg", jd_res.get("error_response", {}).get("zh_desc", ""))
                }
            })

    # 依然保留 HTTPError 捕获，以防以后真遇到过期或签名错误时能看到详细原因
    except urllib.error.HTTPError as http_err:
        error_body = http_err.read().decode("utf-8")
        print("❌ 京东API报错:", error_body)
        return JsonResponse({"code": 500, "msg": f"接口鉴权失败：{error_body}", "data": None})

    except Exception as e:
        return JsonResponse({"code": 500, "msg": str(e), "data": None})

# ===================== 2. 京东创建运单接口 =====================
@csrf_exempt
@require_http_methods(["POST"])
def jd_create_waybill(request):
    try:
        req_data = json.loads(request.body)
        order_sn = req_data.get("order_sn", "")
        sender = req_data.get("sender", {})
        receiver = req_data.get("receiver", {})
        quantity = req_data.get("quantity", 1)

        # 🌟 1. 动态接收前端传递的包裹三要素（带有严谨的类型转换与安全兜底）
        cargo_name = req_data.get("cargo_name", "护肤品")
        try:
            cargo_weight = float(req_data.get("cargo_weight", 1.0))
        except (ValueError, TypeError):
            cargo_weight = 1.0

        try:
            cargo_volume = float(req_data.get("cargo_volume", 10.0))
        except (ValueError, TypeError):
            cargo_volume = 10.0

        print(f"====== 收到发起京东物流申请 ======")
        print(f"订单：{order_sn} | 物品：{cargo_name} | 重量：{cargo_weight}kg | 体积：{cargo_volume}cm³")

        if not all([order_sn, sender, receiver]):
            return JsonResponse({"code": 400, "msg": "参数不完整", "data": None})

        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        customer_code = config["CUSTOMER_CODE"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        path = "/ecap/v1/orders/create"

        pickup_start_time = req_data.get("pickupStartTime")
        pickup_end_time = req_data.get("pickupEndTime")  # 京东一般要求有开始就最好有结束时间窗

        # 🌟 2. 构建京东基础报文对象
        jd_order_payload = {
            "orderId": order_sn,
            "senderContact": {
                "name": sender.get('name', ''),
                "mobile": sender.get('mobile', ''),
                "fullAddress": sender.get('fullAddress', '')
            },
            "receiverContact": {
                "name": receiver.get('name', ''),
                "mobile": receiver.get('mobile', ''),
                "fullAddress": receiver.get('fullAddress', '')
            },
            "orderOrigin": 1,
            "customerCode": customer_code,
            "productsReq": {"productCode": "ed-m-0001"},
            "settleType": 3,
            "cargoes": [{
                "name": cargo_name,
                "quantity": quantity,
                "weight": cargo_weight,
                "volume": cargo_volume
            }]
        }

        # 👇 新增：如果前端传了预约时间，就塞进报文里（一定要转成整型 long/int 毫秒）
        if pickup_start_time:
            jd_order_payload["pickupStartTime"] = int(pickup_start_time)
        if pickup_end_time:
            jd_order_payload["pickupEndTime"] = int(pickup_end_time)

        body = json.dumps([jd_order_payload], ensure_ascii=False)

        # 签名运算（保持你原有的逻辑完全不变）
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sign_content = "".join([
            app_secret, "access_token", access_token, "app_key", app_key, "method", path, "param_json", body,
            "timestamp", timestamp, "v", version, app_secret
        ])
        sign_result = jd_sign(algorithm, sign_content.encode("utf-8"), app_secret.encode("utf-8"))

        # 发起通信请求（保持完全不变）
        queries = {
            "LOP-DN": domain, "app_key": app_key, "access_token": access_token,
            "timestamp": timestamp, "v": version, "sign": sign_result, "algorithm": algorithm
        }
        url = f"{base_uri}{path}?{urlencode(queries)}"
        headers = {
            "lop-tz": str(int(-time.timezone / 3600)), "User-Agent": "lop-http/python3",
            "content-type": "application/json;charset=utf-8"
        }

        opener = urllib.request.build_opener()
        req = urllib.request.Request(url=url, data=body.encode("utf-8"), headers=headers)
        resp = opener.open(req, timeout=15)
        jd_result = json.loads(resp.read().decode("utf-8"))

        # 保存并关联本地订单状态变更（保持不变）
        if jd_result.get("success") is True:
            waybill_code = jd_result.get("data", {}).get("waybillCode", "")
            jd_order_code = jd_result.get("data", {}).get("orderCode", "")
            freight = jd_result.get("data", {}).get("totalFreightStandard", 0)

            # 更新本地订单表状态为：已发货/待收货(2)
            # 注意：此处顺手更新为你之前统一定义的 1=待发货，2=待收货 状态机规范
            Order.objects.filter(order_sn=order_sn).update(
                logistics_no=waybill_code,
                logistics_company="京东物流",
                jd_freight=freight,
                jd_order_status="created",
                jd_create_time=datetime.now(),
                status=2,  # 🌟 确保发货动作直接推动状态变成 2(待收货)
                jd_waybill_code=waybill_code,
                jd_order_code=jd_order_code,
                jd_order_origin=1,
                jd_customer_code=customer_code,
                track_reference_type="20000",
                sender_name=sender.get('name', ''),
                sender_phone=sender.get('mobile', ''),
                sender_address=sender.get('fullAddress', '')
            )

            return JsonResponse({
                "code": 200,
                "msg": "下单成功",
                "data": {"waybill_code": waybill_code, "order_code": jd_order_code}
            })
        else:
            return JsonResponse({"code": 500, "msg": jd_result.get("msg", "下单失败"), "data": None})
    except urllib.error.HTTPError as e:
        # 读取京东真实返回的报错 JSON 报文
        error_body = e.read().decode("utf-8")
        print("================ 京东 API 致命鉴权报错 ================")
        print(f"HTTP 状态码: {e.code}")
        print(f"京东返回详情: {error_body}")
        print("=======================================================")
        return JsonResponse({"code": e.code, "msg": f"京东鉴权被拒，请查看终端日志", "data": error_body})

    except Exception as e:

        traceback.print_exc() # 保持良好的排错打印习惯
        return JsonResponse({"code": 500, "msg": f"异常：{str(e)}", "data": None})


@csrf_exempt
@require_http_methods(["POST"])
def jd_cancel_order(request):
    try:
        # 读取JSON参数
        data = json.loads(request.body)
        order_sn = data.get("order_sn", "")
        if not order_sn:
            return JsonResponse({"code": 400, "msg": "订单号不能为空", "data": None})

        # 查询订单（仅查询，不删除）
        order = Order.objects.filter(order_sn=order_sn).first()
        if not order or not order.jd_waybill_code:
            return JsonResponse({"code": 400, "msg": "无运单号", "data": None})

        waybill_code = order.jd_waybill_code

        # 京东取消API代码（完全不变，保留你原有逻辑）
        opener = urllib.request.build_opener()
        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        path = "/ecap/v1/orders/cancel"
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]

        body = f'[{{"waybillCode":"{waybill_code}","orderOrigin":"1","customerCode":"{config["CUSTOMER_CODE"]}","cancelReason":"用户主动取消","cancelReasonCode":"1"}}]'

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = "".join([
            app_secret, "access_token", access_token, "app_key", app_key, "method", path,
            "param_json", body, "timestamp", timestamp, "v", version, app_secret
        ])
        sign_ = jd_sign(algorithm, content.encode("UTF-8"), app_secret.encode("UTF-8"))

        queries = {
            "LOP-DN": domain, "app_key": app_key, "access_token": access_token,
            "timestamp": timestamp, "v": version, "sign": sign_, "algorithm": algorithm
        }
        headers = {
            "lop-tz": "8", "User-Agent": "lop-http/java", "content-type": "application/json;charset=utf-8"
        }
        url = base_uri + path + "?" + urllib.parse.urlencode(queries)
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        resp = urllib.request.urlopen(req)
        cancel_result = json.loads(resp.read().decode("utf-8"))

        # ===================== 核心修复区域 START =====================
        # 取消京东物流成功后：恢复待发货 + 清空运单号（不取消订单！）
        if cancel_result.get("success") == True:
            Order.objects.filter(order_sn=order_sn).update(
                status=1,  # 【关键修改】本地状态：待发货 (替换为你系统真实的待发货状态码)
                jd_waybill_code=None,  # 【新增】清空京东运单号（取消物流必须清空）
                jd_order_status="pending_shipment"  # 【修改】京东状态：待发货
            )
            return JsonResponse({"code": 200, "msg": "取消物流成功，订单已恢复为待发货", "data": cancel_result})
        # ===================== 核心修复区域 END =====================
        else:
            return JsonResponse({"code": 500, "msg": "取消失败：" + str(cancel_result), "data": cancel_result})

    except Exception as e:
        return JsonResponse({"code": 500, "msg": "错误：" + str(e), "data": None})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def jd_query_trace(request):
    try:
        # 1. 获取订单号
        order_sn = request.GET.get("order_sn") or request.POST.get("order_sn")
        if not order_sn:
            return JsonResponse({"code": 400, "msg": "订单号不能为空", "data": {}})

        # 2. 查询订单运单号
        order = Order.objects.filter(order_sn=order_sn).first()
        if not order or not order.jd_waybill_code:
            return JsonResponse({"code": 400, "msg": "无运单号", "data": {}})

        waybill_code = order.jd_waybill_code

        # ===================== ✅ 读取京东 API 通用配置 =====================
        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]  # 测试环境地址
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]  # 轨迹查询使用ECAP
        customer_code = config["CUSTOMER_CODE"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        method = "POST"

        headers = {
            "lop-tz": "8",
            "User-Agent": "lop-http/java",
            "content-type": "application/json;charset=utf-8"
        }

        # ===================== 🚀 第一次请求：查询物流轨迹 =====================
        path_trace = "/ecap/v1/orders/trace/query"
        body_trace = f'[{{"waybillCode":"{waybill_code}","orderOrigin":"1","customerCode":"{customer_code}"}}]'
        timestamp_trace = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 轨迹查询签名
        content_trace = "".join([
            app_secret,
            "access_token", access_token,
            "app_key", app_key,
            "method", path_trace,
            "param_json", body_trace,
            "timestamp", timestamp_trace,
            "v", version,
            app_secret
        ])
        sign_trace = jd_sign(algorithm, content_trace.encode("utf-8"), app_secret.encode("utf-8"))

        query_params_trace = {
            "LOP-DN": domain, "access_token": access_token, "app_key": app_key,
            "timestamp": timestamp_trace, "v": version, "sign": sign_trace, "algorithm": algorithm
        }
        url_trace = base_uri + path_trace + "?" + urllib.parse.urlencode(query_params_trace)

        req_trace = urllib.request.Request(url_trace, data=body_trace.encode("utf-8"), headers=headers, method=method)
        with urllib.request.urlopen(req_trace, timeout=10) as resp:
            result_trace = json.loads(resp.read().decode("utf-8"))

            # 提取最新状态
            latest_status = "未知状态"
            try:
                trace_list = result_trace.get("data", {}).get("traceDetails", [])
                if trace_list:
                    latest_status = trace_list[0].get("categoryName", "未知状态")
            except Exception as e:
                print(f"状态解析错误：{str(e)}")

            # ===================== 🌟 核心：物流状态驱动订单流转 =====================
            update_fields = ['jd_latest_status']
            order.jd_latest_status = latest_status

            # 1. 拦截妥投/签收 -> 变更为“已完成(3)”
            if any(kw in latest_status for kw in ['妥投', '签收', '完成']):
                if order.status != 3:
                    order.status = 3
                    order.receive_time = datetime.now()  # 记录实际收货时间
                    update_fields.extend(['status', 'receive_time'])
                    print(f"订单 {order_sn} 已妥投，状态自动变更为：已完成(3)")

            # 2. 拦截揽件/运输 -> 变更为“待收货(2)”
            elif any(kw in latest_status for kw in ['揽收', '运输', '派送', '发车', '在途', '转运']):
                if order.status == 1:  # 只有待发货状态才允许变为待收货
                    order.status = 2
                    order.ship_time = datetime.now()  # 记录实际发货时间
                    update_fields.extend(['status', 'ship_time'])
                    print(f"订单 {order_sn} 已揽件，状态自动变更为：待收货(2)")

            # 执行数据库更新
            order.save(update_fields=update_fields)

            # ===================== 🚀 第二次请求：查询预计送达时间 =====================

        promise_time_str = ""
        try:
            path_info = "/ecap/v1/orders/info/query"
            body_info = f'[{{"customerCode":"{customer_code}","deliveryId":"{waybill_code}","dynamicTimeFlag":1}}]'
            timestamp_info = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 时间查询签名
            content_info = "".join([
                app_secret,
                "access_token", access_token,
                "app_key", app_key,
                "method", path_info,
                "param_json", body_info,
                "timestamp", timestamp_info,
                "v", version,
                app_secret
            ])
            sign_info = jd_sign(algorithm, content_info.encode("utf-8"), app_secret.encode("utf-8"))

            query_params_info = {
                "LOP-DN": domain, "access_token": access_token, "app_key": app_key,
                "timestamp": timestamp_info, "v": version, "sign": sign_info, "algorithm": algorithm
            }
            url_info = base_uri + path_info + "?" + urllib.parse.urlencode(query_params_info)

            req_info = urllib.request.Request(url_info, data=body_info.encode("utf-8"), headers=headers, method=method)
            with urllib.request.urlopen(req_info, timeout=5) as resp_info:
                result_info = json.loads(resp_info.read().decode("utf-8"))

            # 提取时间戳并转换为直观的字符串
            promise_timestamp = result_info.get("data", {}).get("deliveryPromiseTime")
            if promise_timestamp:
                # 京东返回的是毫秒级时间戳，需除以1000转为秒
                dt_obj = datetime.fromtimestamp(promise_timestamp / 1000.0)
                promise_time_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

        except Exception as e:
            print(f"预计送达时间查询或解析失败：{str(e)}")
            # 这里不阻断主流程，获取失败则让时间保持为空字符串

        # ===================== ✅ 返回合并后的结果 =====================
        return JsonResponse({
            "code": 200,
            "msg": "查询成功",
            "latest_status": latest_status,
            "promise_time": promise_time_str,  # 新增返回字段
            "data": result_trace
        })

    except Exception as e:
        return JsonResponse({"code": 500, "msg": f"查询失败：{str(e)}", "data": {}})


@csrf_exempt
@require_http_methods(["POST"])
def jd_modify_order(request):
    try:
        # 1. 接收参数
        req_data = json.loads(request.body)
        order_sn = req_data.get("order_sn")
        modify_data = req_data.get("modify_data", {})
        new_sender = modify_data.get("senderContact")
        new_receiver = modify_data.get("receiverContact")

        # 2. 查询订单+关联地址
        order = Order.objects.filter(order_sn=order_sn).select_related('address').first()
        if not order or not order.address:
            return JsonResponse({"code": 400, "msg": "订单/收货地址不存在", "data": None})

        # 3. 京东请求逻辑（不变）
        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        path = "/ecap/v1/orders/modify"

        modify_body = {
            "orderId": order.order_sn,
            "waybillCode": order.jd_waybill_code,
            "orderOrigin": 1
        }
        if new_sender: modify_body["senderContact"] = new_sender
        if new_receiver: modify_body["receiverContact"] = new_receiver
        body = json.dumps([modify_body], ensure_ascii=False)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sign_content = "".join([
            app_secret, "access_token", access_token, "app_key", app_key,
            "method", path, "param_json", body, "timestamp", timestamp, "v", version, app_secret
        ])
        sign_result = jd_sign(algorithm, sign_content.encode("UTF-8"), app_secret.encode("UTF-8"))

        query_params = {
            "LOP-DN": domain, "app_key": app_key, "access_token": access_token,
            "timestamp": timestamp, "v": version, "sign": sign_result, "algorithm": algorithm
        }
        url = base_uri + path + "?" + urllib.parse.urlencode(query_params)
        headers = {
            "lop-tz": str(int(-time.timezone / 3600)),
            "User-Agent": "lop-http/python3",
            "content-type": "application/json;charset=utf-8"
        }
        opener = urllib.request.build_opener()
        req = urllib.request.Request(url=url, data=body.encode("UTF-8"), headers=headers, method="POST")
        response = opener.open(req)
        jd_result = json.loads(response.read().decode("UTF-8"))

        # ===================== ✅ 核心：通用去重 · 无硬编码 · 纯地址处理 =====================
        if jd_result.get("success") is True:
            try:
                # 更新寄件人信息
                if new_sender:
                    order.sender_name = new_sender.get("name")
                    order.sender_phone = new_sender.get("phone")
                    order.sender_address = new_sender.get("fullAddress")

                # 更新收件人：自动剔除省市区，仅保存纯详细地址
                if new_receiver:
                    addr = order.address
                    addr.name = new_receiver.get("name")
                    addr.phone = new_receiver.get("phone")

                    # 🔥 无硬编码核心：获取地址自身的省市区，从完整地址中剔除
                    region_text = f"{addr.province} {addr.city} {addr.district}".strip()
                    full_addr = new_receiver.get("fullAddress", "").strip()

                    # 剔除省市区前缀，得到纯详细地址
                    if full_addr.startswith(region_text):
                        clean_detail = full_addr.replace(region_text, "", 1).strip()
                    else:
                        clean_detail = full_addr

                    addr.detail = clean_detail  # 保存纯详细地址
                    addr.save()  # 写入地址表

                order.save()  # 写入订单表

            except Exception as db_err:
                print("数据库写入异常：", str(db_err))

        return JsonResponse({
            "code": 200 if jd_result.get("success") else 500,
            "msg": "修改成功" if jd_result.get("success") else jd_result.get("msg", "修改失败"),
            "data": jd_result
        })

    except Exception as e:
        return JsonResponse({"code": 500, "msg": f"异常：{str(e)}", "data": None})

# ===================== ✅ 京东物流位置/GIS轨迹查询（对照官方示例编写） =====================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def jd_query_waybill_gis_track(request):
    """
    京东物流实时位置查询接口 (waybillGisTrack)
    入参：order_sn 订单号
    返回：物流GIS位置、实时轨迹数据
    """
    try:
        # 1. 获取前端传入的订单号（和你现有接口一致）
        order_sn = request.GET.get("order_sn") or request.POST.get("order_sn")
        if not order_sn:
            return JsonResponse({"code": 400, "msg": "订单号不能为空", "data": {}})

        # 2. 查询订单，获取京东运单号（无运单号则返回错误）
        order = Order.objects.filter(order_sn=order_sn).first()
        if not order or not order.jd_waybill_code:
            return JsonResponse({"code": 400, "msg": "订单无京东运单号", "data": {}})

        waybill_code = order.jd_waybill_code

        # 3. 从配置文件读取所有参数（✅ 无任何硬编码）
        config = settings.JD_LOGISTICS
        base_uri = config["UAT_API"]
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        customer_code = config["CUSTOMER_CODE"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        # 官方示例接口地址
        path = "/ecap/v1/orders/waybillGisTrack"

        # 4. 构造请求体（1:1 对照官方示例）
        body = json.dumps([{
            "waybillCode": waybill_code,
            "customerCode": customer_code
        }], ensure_ascii=False)

        # 5. 生成签名（完全对照官方拼接规则）
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sign_content = "".join([
            app_secret,
            "access_token", access_token,
            "app_key", app_key,
            "method", path,
            "param_json", body,
            "timestamp", timestamp,
            "v", version,
            app_secret
        ])
        sign_result = jd_sign(algorithm, sign_content.encode("UTF-8"), app_secret.encode("UTF-8"))

        # 6. 构造请求参数
        queries = {
            "LOP-DN": domain,
            "app_key": app_key,
            "access_token": access_token,
            "timestamp": timestamp,
            "v": version,
            "sign": sign_result,
            "algorithm": algorithm
        }

        # 7. 请求头（1:1 对照官方示例）
        offset = str(int(-time.timezone / 3600))
        headers = {
            "lop-tz": offset,
            "User-Agent": "lop-http/python3",
            "content-type": "application/json;charset=utf-8",
        }

        # 8. 发送请求（官方原生写法）
        url = base_uri + path + "?" + urllib.parse.urlencode(queries)
        opener = urllib.request.build_opener()
        http_request = urllib.request.Request(url=url, data=body.encode("UTF-8"), headers=headers)
        http_response = opener.open(http_request)
        result = json.loads(http_response.read().decode("UTF-8"))

        # 9. 返回前端（和你现有接口返回格式统一）
        return JsonResponse({
            "code": 200,
            "msg": "物流位置查询成功",
            "data": result
        })

    except Exception as e:
        return JsonResponse({
            "code": 500,
            "msg": f"物流位置查询失败：{str(e)}",
            "data": {}
        })

from rest_framework.decorators import api_view, permission_classes
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # 🌟 DRF 的门神，自动解析 Token，没登录直接拦截返回 401
def jd_create_order_and_waybill(request):
    # 🌟 只要能进到这里，说明 Token 绝对有效，request.user 已经自动变成了你的真实用户！
    user = request.user

    try:
        req_data = json.loads(request.body)
        sender = req_data.get("sender", {})
        receiver = req_data.get("receiver", {})

        # 提取动态货品规格
        cargo_name = req_data.get("cargo_name", "护肤品/日用品")
        cargo_weight = float(req_data.get("cargo_weight", 1.0))
        cargo_volume = float(req_data.get("cargo_volume", 0.01))

        # 🌟 核心财务校验：认准前端上报的预估结算积分
        deduct_points = int(req_data.get("deduct_points", 0))
        if deduct_points <= 0:
            return JsonResponse({"code": 400, "msg": "计费积分异常，无法叫件"})

        # ====================================================
        # 🚀 开启原子事务核心层（ACID 强一致性防御）
        # ====================================================
        with transaction.atomic():

            # 1. 采用 select_for_update 执行行级悲观锁，彻底杜绝并发连击薅羊毛
            from django.contrib.auth import get_user_model
            User = get_user_model()
            locked_user = User.objects.select_for_update().get(id=user.id)

            current_points = locked_user.points or 0
            if current_points < deduct_points:
                return JsonResponse({
                    "code": 400,
                    "msg": f"积分不足：当前剩余 {current_points} 分，本次叫件需 {deduct_points} 分"
                })

            # 2. 执行扣分，并记录财务流水线
            locked_user.points -= deduct_points
            locked_user.save(update_fields=['points'])

            # 自动生成内部唯一对账大单号
            order_sn = f"WBL{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            PointsRecord.objects.create(
                user=locked_user,
                points=-deduct_points,  # 负数代表扣除
                points_type=4,  # 4 代表 抵扣消费
                related_id=order_sn,  # 关联你的物流单号
                description=f"积分换物流服务，扣除 {deduct_points} 积分",  # 前端展示的变动描述
                available_points=0  # 扣减记录，剩余可用积分为 0
                # create_time 不需要传，Django 会自动生成
            )

            # 3. 本地预生成物流订单（此时处于“叫件中”状态，挂载完整的收寄件文本快照）
            receiver_name = receiver.get("name")
            receiver_phone = receiver.get("mobile")
            receiver_addr_obj = Address.objects.filter(
                user=locked_user,
                name=receiver_name,
                phone__contains=receiver_phone  # 模糊匹配防止空格
            ).first()

            if not receiver_addr_obj:
                # 极端兜底：如果没查到，抛出异常触发回滚
                raise Exception("收件人地址在数据库中不存在，请重新选择")

            # 3. 本地预生成物流订单
            order = Order.objects.create(
                user=locked_user,
                order_sn=order_sn,
                total_price=Decimal('0.00'),
                actual_pay_money=Decimal('0.00'),
                point_deduct=deduct_points,
                point_deduct_money=Decimal(str(deduct_points * 0.01)),
                status=1,
                delivery_type=1,
                goods_count=1,
                goods_names=f"物流服务:[{cargo_name}]",

                # 寄件人信息 (保留你原本模型里的 sender_* 扁平字段)
                sender_name=sender.get("name"),
                sender_phone=sender.get("mobile"),
                sender_address=sender.get("fullAddress"),

                # 🌟 核心修复：把扁平的 receiver 字段删掉，换成你模型真正需要的 address 外键！
                address=receiver_addr_obj,

                jd_precheck_status=True,
                jd_latest_status="等待小哥揽收"
            )

            # 4. 组装网关报文，正式呼叫京东开放平台（LOP）
            config = settings.JD_LOGISTICS
            base_uri = config["UAT_API"]
            app_key = config["APP_KEY"]
            app_secret = config["APP_SECRET"]
            access_token = config["ACCESS_TOKEN"]
            domain = config["DOMAIN"]
            customer_code = config["CUSTOMER_CODE"]
            algorithm = config["ALGORITHM"]
            version = config["VERSION"]

            path_create = "/ecap/v1/orders/create"  # 京东正式下单叫件API

            # 👇 新增：提取前端传的预约时间
            pickup_start_time = req_data.get("pickupStartTime")
            pickup_end_time = req_data.get("pickupEndTime")

            path_create = "/ecap/v1/orders/create"  # 京东正式下单叫件API

            # 👇 新增：构建字典而不是直接写死 json.dumps
            jd_payload = {
                "orderId": order_sn,
                "senderContact": {
                    "name": order.sender_name,
                    "mobile": order.sender_phone,
                    "fullAddress": order.sender_address
                },
                "receiverContact": {
                    "name": receiver.get("name"),
                    "mobile": receiver.get("mobile"),
                    "fullAddress": receiver.get("fullAddress")
                },
                "orderOrigin": 1,
                "customerCode": customer_code,
                "productsReq": {"productCode": "ed-m-0001"},
                "settleType": 3,
                "cargoes": [{
                    "name": cargo_name,
                    "quantity": 1,
                    "weight": cargo_weight,
                    "volume": cargo_volume
                }]
            }

            # 👇 新增：动态挂载时间参数
            if pickup_start_time:
                jd_payload["pickupStartTime"] = int(pickup_start_time)
            if pickup_end_time:
                jd_payload["pickupEndTime"] = int(pickup_end_time)

            jd_body = json.dumps([jd_payload], ensure_ascii=False)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sign_content = "".join([
                app_secret, "access_token", access_token, "app_key", app_key,
                "method", path_create, "param_json", jd_body, "timestamp", timestamp, "v", version, app_secret
            ])

            sign_result = jd_sign(algorithm, sign_content.encode("utf-8"), app_secret.encode("utf-8"))

            queries = {
                "LOP-DN": domain, "app_key": app_key, "access_token": access_token,
                "timestamp": timestamp, "v": version, "sign": sign_result, "algorithm": algorithm
            }
            url = f"{base_uri}{path_create}?{urllib.parse.urlencode(queries)}"

            headers = {
                "lop-tz": str(int(-time.timezone / 3600)) if 'time' in globals() else "8",
                "User-Agent": "lop-http/python3",
                "content-type": "application/json;charset=utf-8",
            }

            # 下发同步阻塞请求
            req = urllib.request.Request(url=url, data=jd_body.encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as resp:
                jd_res = json.loads(resp.read().decode("utf-8"))

            # 5. 校验京东的响应判定
            if jd_res.get("success") is True or jd_res.get("code") == 200:
                # 抓取京东分配的黄金运单号
                waybill_code = jd_res.get("data", {}).get("waybillCode")
                if not waybill_code:
                    # 如果成功标记为 True 但里面没有单号，抛出异常强制回滚事务
                    raise Exception("京东接口未返回有效面单号")

                # 状态对齐：更新面单号并锁死数据
                order.jd_waybill_code = waybill_code
                order.status = 1  # 本地设为待发货/等待揽件
                order.save(update_fields=["jd_waybill_code", "status"])

                logger.info(f"🎉 订单 {order_sn} 纯积分兑换成功！分配的京东单号为: {waybill_code}")
            else:
                # 🌟 【致命防御点】：京东若说地址不支持或者参数有误，直接抛出异常
                # transaction.atomic() 捕获后，会自动把上面减掉的积分恢复，并抹去这条未诞生的订单
                err_msg = jd_res.get("msg") or jd_res.get("error_response", {}).get("zh_desc", "京东网关拒绝接单")
                raise Exception(err_msg)

        # 走出 Block 说明事务已完美安全提交（Commit）
        return JsonResponse({
            "code": 200,
            "msg": "呼叫小哥成功，请等待上门揽收",
            "data": {
                "order_sn": order_sn,
                "waybill_code": order.jd_waybill_code,
                "deduct_points": deduct_points
            }
        })

    except Exception as e:
        # 拦截所有报错，打印日志并回传给小程序
        error_msg = str(e)
        logger.error(f"❌ 积分直兑物流失败，全量回滚。原因: {error_msg}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"兑换失败: {error_msg}"})


# ================= 1. 照片纯存档接口 (高并发安全版) =================
from .models import UserSkinProfile, SkinPhotoRecord
from .serializer import UserSkinProfileSerializer
from django.db import IntegrityError

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_skin_photo(request):
    """保存被测人照片（支持多图并发，且兼容历史脏数据）"""
    subject_name = request.data.get('subject_name')
    photo_file = request.FILES.get('file')

    if not subject_name or not photo_file:
        return Response({'code': 400, 'msg': '缺少被测人姓名或照片文件'}, status=400)

    try:
        subject_name = subject_name.strip()
        created = False

        # 1. 尝试获取最新档案（兼容历史 bug，绝不报错）
        profile = UserSkinProfile.objects.filter(
            user=request.user,
            subject_name=subject_name
        ).order_by('-id').first()

        # 2. 如果不存在，执行并发安全的创建逻辑
        if not profile:
            try:
                # 开启原子事务：防止多个线程同时闯入引发数据错乱
                with transaction.atomic():
                    profile = UserSkinProfile.objects.create(
                        user=request.user,
                        subject_name=subject_name
                    )
                    created = True
            except IntegrityError:
                # 🚀 核心防御：如果走到这里，说明在极短的时间差内，
                # 前端并发的其他 9 张图的某个线程已经抢先建好档案了！
                # 此时捕获异常，并且什么都不用做，重新去查一下那个抢先建好的档案即可。
                profile = UserSkinProfile.objects.filter(
                    user=request.user,
                    subject_name=subject_name
                ).order_by('-id').first()

        # 兜底：万一并发极端情况下还是没拿到，强制拦截
        if not profile:
            return Response({'code': 500, 'msg': '并发建档异常，请重试'}, status=500)

        # 3. 追加保存照片记录 (一对多)
        SkinPhotoRecord.objects.create(
            profile=profile,
            face_image=photo_file
        )

        return Response({
            'code': 200,
            'msg': '照片存档成功',
            'data': {
                'profile_id': profile.id,
                'is_new': created
            }
        })
    except Exception as e:
        return Response({'code': 500, 'msg': f'存档失败: {str(e)}'}, status=500)

class UserSkinProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    提供给小程序的接口：获取当前登录用户建立的所有档案及其历史照片
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSkinProfileSerializer

    def get_queryset(self):
        # 🌟 优化：加上 .order_by('-id') 或 ('-updated_at')
        # 这样返回给小程序时，最新测试的顾客/档案会默认排在最前面，体验更好
        return UserSkinProfile.objects.filter(user=self.request.user).order_by('-id')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_upgrade_order(request):
    user = request.user
    target_level = int(request.data.get('target_level', 0))
    current_level = user.user_type if user.user_type else 1

    # 等级合法性校验
    if target_level <= current_level:
        return Response({"code": 400, "msg": "目标等级必须高于当前等级"})

    # 后端硬编码价格，杜绝前端篡改
    level_prices = {
        1: 0.00,
        2: 980.00,  # 1星
        3: 1980.00,  # 2星
        4: 3800.00,  # 3星
        5: 9800.00,  # 4星
        6: 39800.00,  # 5星
        7: 98000.00  # Ta创+
    }
    if target_level not in level_prices:
        return Response({"code": 400, "msg": "非法的升级等级"})

    amount = level_prices[target_level]

    # 生成订单号（和普通订单规则保持一致：UPGRADE+时间戳+短随机码）
    order_sn = f"UPGRADE{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    # 统一使用Order模型创建订单，回调自动识别处理
    order = Order.objects.create(
        order_sn=order_sn,
        user=user,
        order_type='upgrade',  # 标记为升级订单，回调走升级分支
        total_price=amount,
        actual_pay_money=amount,
        status=0,  # 0=待支付
        openid=user.openid if hasattr(user, 'openid') else None,
        register_data={
            'target_level': target_level  # 目标等级存入扩展字段，回调读取使用
        },
        is_delete=False
    )

    return Response({
        "code": 200,
        "msg": "订单创建成功",
        "data": {
            "order_id": order.order_sn,  # 和前端字段完全兼容
            "amount": float(amount)
        }
    })

# 🌟 核心：这是你【微信支付回调接口】中必须追加的逻辑！
# 当收到微信支付成功通知，且订单号 out_trade_no 以 "UPG" 开头时，执行以下代码：
def handle_upgrade_payment_success(out_trade_no):
    try:
        order = UpgradeOrder.objects.get(out_trade_no=out_trade_no, status=0)
        order.status = 1
        order.pay_time = timezone.now()
        order.save()

        user = order.user
        user.user_type = order.target_level
        # 会籍过期时间重新计算为 1 年后
        user.expire_time = timezone.now() + timedelta(days=365)
        user.save()

        return True
    except UpgradeOrder.DoesNotExist:
        return False

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_success_notify(request):
    out_trade_no = request.data.get('out_trade_no')
    if not out_trade_no:
        return Response({"code": 400, "msg": "缺少订单号"})

    try:
        order = UpgradeOrder.objects.get(out_trade_no=out_trade_no, user=request.user)

        # 只要订单是待支付状态，就处理升级逻辑
        if order.status == 0:
            # 1. 更新订单状态
            order.status = 1
            order.pay_time = timezone.now()
            order.save()

            # 🌟 2. 核心：更新用户等级和到期时间
            user = request.user
            user.user_type = order.target_level

            # 以当前时间为基准，往后推 365 天
            user.expire_time = timezone.now() + timedelta(days=365)

            # 强制更新这几个字段，防止被其他保存逻辑覆盖
            user.save(update_fields=['user_type', 'expire_time'])

        # 获取最新数据返回给前端
        user_data = MemberInfoSerializer(request.user).data

        return Response({
            "code": 200,
            "msg": "升级成功",
            "data": user_data
        })
    except UpgradeOrder.DoesNotExist:
        return Response({"code": 404, "msg": "订单不存在"})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"code": 400, "msg": "未获取到图片文件"})

    try:
        user = request.user

        # 🌟 1. 调用之前写的榨汁机函数，把又大又笨的 JPG 自动转成几 KB 的 WebP
        # webp_file = convert_jpg_to_webp(file, quality=80)

        # （如果你还没写好转WebP的函数，可以先直接用原文件存着测试：webp_file = file）
        webp_file = file

        # 🌟 2. 生成一个唯一的文件名，防止头像重名覆盖
        ext = webp_file.name.split('.')[-1]
        new_filename = f"avatar_{user.member_id}_{uuid.uuid4().hex[:8]}.{ext}"
        webp_file.name = new_filename

        # 🌟 3. 保存到用户的头像字段中 (假设你的用户模型里有个字段叫 avatar)
        user.avatar = webp_file
        user.save(update_fields=['avatar'])

        # 🌟 4. 拼接出完整的图片网络 URL 传给前端
        # 如果你配了 MEDIA_URL，通常可以直接用 user.avatar.url
        avatar_full_url = request.build_absolute_uri(user.avatar.url)

        return Response({
            "code": 200,
            "msg": "头像上传成功",
            "data": {
                "avatar_url": avatar_full_url
            }
        })
    except Exception as e:
        return Response({"code": 500, "msg": f"服务器处理图片异常: {str(e)}"})

class OrderConfirmReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_sn):
        order = get_object_or_404(Order, order_sn=order_sn, user=request.user)

        # 🌟 强转为 int 进行比对，完美消除字符串/数字的类型差异
        try:
            current_status = int(order.status)
        except (ValueError, TypeError):
            current_status = -1

        # 状态 0:未支付, 4:已取消
        if current_status in [0, 4]:
            return Response({"code": 400, "msg": "当前订单状态无法操作或已确认收货"})

        try:
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(order_sn=order_sn)

                # 🌟 同样强转为 int
                try:
                    locked_status = int(locked_order.status)
                except (ValueError, TypeError):
                    locked_status = -1

                # 🌟 调试日志：如果被拦截，在终端一眼就能看到到底卡在了什么状态上
                print(
                    f"\n[确认收货核心校验] 订单: {order_sn} | 锁定状态值: {locked_status} | 原始未转类型: {type(locked_order.status)}\n")

                # 核心防线：只有待收货/已发货(2)的订单才可以确认收货
                if locked_status != 2:
                    return Response({
                        "code": 400,
                        "msg": f"订单状态为【{locked_status}】，非待收货状态，请刷新重试"
                    })

                # 校验通过，真正执行写入
                locked_order.status = 3  # 如果数据库是字符型，Django会自动转，写成 3 或 '3' 均可
                locked_order.save(update_fields=['status'])

                # 发放佣金
                calculate_and_grant_commission(locked_order)

            return Response({"code": 200, "msg": "确认收货成功"})

        except Exception as e:
            logger.error(f"订单 {order_sn} 确认收货失败，原因: {str(e)}", exc_info=True)
            return Response({"code": 500, "msg": "系统繁忙，请稍后再试"})

class OrderConfirmReadyView(APIView):
    """
    【商家端工作台】自取订单备货完成，推进状态 1 -> 2
    """

    def post(self, request):
        order_sn = request.data.get('order_sn')
        if not order_sn:
            return Response({"code": 400, "msg": "缺少订单号"})

        try:
            with transaction.atomic():
                # 锁定订单，防止并发
                order = Order.objects.select_for_update().get(order_sn=order_sn)

                # 安全拦截 1：必须是自取订单
                if order.delivery_type != 2:
                    return Response({"code": 400, "msg": "非到店自取订单，无法执行此操作"})

                # 安全拦截 2：必须是 1 (备货中)
                try:
                    current_status = int(order.status)
                except:
                    current_status = -1

                if current_status != 1:
                    return Response({"code": 400, "msg": f"当前状态【{current_status}】无法确认备货"})

                # 🌟 核心流转：1（备货中） --> 2（待取货）
                order.status = 2
                order.save(update_fields=['status'])

                return Response({"code": 200, "msg": "备货完成，已变更为待取货"})

        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "未找到该订单"})
        except Exception as e:
            traceback.print_exc()
            return Response({"code": 500, "msg": "系统繁忙，请稍后再试"})

class MiniProgramWithdrawApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # 1. 尝试打印进入了接口
            print("========== [调试提现接口] 收到提现请求 ==========")
            user = request.user

            # 2. 核心控制：限额校验
            if not WithdrawRecord.can_withdraw_this_month(user):
                return Response({'code': 400, 'msg': '为保障资金安全，每人每月限提现一次，您本月额度已用完'})

            amount = Decimal(str(request.data.get('amount', 0)))

            if amount < Decimal('0.10'):
                return Response({'code': 400, 'msg': '单笔提现金额最低为 0.1 元'})

            if amount > user.withdrawable_balance:
                return Response({'code': 400, 'msg': '提现金额不能大于您的可用余额'})

            out_bill_no = f"WD{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            with transaction.atomic():
                locked_user = User.objects.select_for_update().get(id=user.id)
                if amount > locked_user.withdrawable_balance:
                    return Response({'code': 400, 'msg': '账户余额变动，请刷新后重试'})

                locked_user.withdrawable_balance -= amount
                locked_user.frozen_balance += amount
                locked_user.save(update_fields=['withdrawable_balance', 'frozen_balance'])

                WithdrawRecord.objects.create(
                    user=locked_user,
                    out_bill_no=out_bill_no,
                    amount=amount,
                    status=0
                )

            return Response({'code': 200, 'msg': '提现申请已提交，等待财务审核'})

        except Exception as e:
            # 🌟 核心排错：打印详细的错误堆栈到终端，并把错误信息塞进 msg 返回给前端弹窗！
            print("❌ [调试提现接口] 发生异常：")
            traceback.print_exc()
            return Response({'code': 500, 'msg': f'提现代码报错: {str(e)}'})

class WithdrawStatusView(APIView):
    def get(self, request):
        user = request.user
        # 查找该用户最新的一笔提现记录
        latest_record = WithdrawRecord.objects.filter(user=user).order_by('-create_time').first()

        if not latest_record:
            return Response({'status': -1, 'msg': '无提现记录'})

        return Response({
            'status': latest_record.status,
            'package_info': latest_record.package_info,
            'amount': latest_record.amount,
            'out_bill_no': latest_record.out_bill_no  # 内部单号
        })

class WithdrawConfirmSuccessView(APIView):
    """
    用户在微信前端确认收款成功后，由小程序前端异步通知后端修改状态
    """

    def post(self, request):
        out_bill_no = request.data.get('out_bill_no')
        if not out_bill_no:
            return Response({'code': 400, 'msg': '缺少必要参数'})

        with transaction.atomic():
            # 锁定该笔记录，防止并发冲突
            record = WithdrawRecord.objects.select_for_update().filter(
                out_bill_no=out_bill_no,
                user=request.user,
                status=1  # 只有处于待确认状态的才可以被修改
            ).first()

            if record:
                record.status = 2  # 修改为 2: 提现成功
                record.save()
                return Response({'code': 200, 'msg': '状态同步成功'})

        return Response({'code': 400, 'msg': '未找到对应待确认的提现记录'})

class MiniProgramWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user.refresh_from_db()  # 强刷数据库

        # 查出该用户的所有历史佣金记录
        records = CommissionRecord.objects.filter(user=user).select_related('order', 'buyer').order_by('-create_time')
        total_earned = records.aggregate(total=Sum('amount'))['total'] or 0.00

        detail_list = []
        for r in records:
            # 🌟 丰富每一个明细项的字段，确保前端有足够的数据可以“显式全”
            detail_list.append({
                'id': r.id,
                'order_sn': r.order.order_sn if r.order else '无',
                'order_amount': float(r.order.actual_pay_money) if r.order else 0.00,  # 原始订单实付
                'buyer_name': r.buyer.nickname if (r.buyer and r.buyer.nickname) else "微信用户",
                'buyer_phone': f"{r.buyer.phone[:3]}****{r.buyer.phone[-4:]}" if (r.buyer and r.buyer.phone) else "无",
                'amount': float(r.amount),
                'desc': r.desc,  # 比如: 来自下级会员[xxx]的消费奖励
                'date': r.create_time.strftime('%Y-%m-%d %H:%M:%S')  # 🌟 精确到秒的记账时间
            })

        return Response({
            'code': 200,
            'msg': '获取钱包资产成功',
            'data': {
                'withdrawable_balance': float(user.withdrawable_balance),
                'frozen_balance': float(user.frozen_balance),
                'total_earned': float(total_earned),
                'details': detail_list  # 丰富的流水明细
            }
        })

from django.views import View
from django.contrib.auth.mixins import UserPassesTestMixin
class FinanceSecurityMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

# =========================================================================
# 🔒 安全升级 1：避开 IP，实现特定计算机/工作站物理安全锁
# =========================================================================
class FinanceSecurityMixin(UserPassesTestMixin):
    """
    财务安全混合类：结合 员工身份校验 + 特定计算机设备指纹锁
    """

    def test_func(self):
        # 1. 基础身份校验：必须登录且是后台职员
        if not (self.request.user.is_authenticated and self.request.user.is_staff):
            return False

        # 2. 🌟 避开 IP 核心：特定计算机设备指纹校验
        # 约定：只有特定的财务计算机，其浏览器请求头（或Cookie）中才会携带独一无二的设备安全密钥
        # 运维人员只需在财务电脑的浏览器控制台执行一次：document.cookie="FINANCE_DEVICE_KEY=LansikSecurityToken2026_XYZ; max-age=31536000; path=/;"
        ALLOWED_DEVICE_KEY = settings.WECHAT_PAY["FINANCE_DEVICE_KEY"]

        # 优先从自定义 Header 拿，其次从 Cookie 中拿
        client_device_key = self.request.headers.get('X-Finance-Device-Key') or self.request.COOKIES.get(
            'FINANCE_DEVICE_KEY')

        if client_device_key != ALLOWED_DEVICE_KEY:
            logger.warning(f"🚨 警告：用户 [{self.request.user.phone}] 试图使用非授权计算机访问财务敏感接口！")
            return False

        return True

    def handle_no_permission(self):
        """ 拦截未授权设备或未登录用户的受阻响应 """
        return HttpResponse(
            "<h3>🚨 安全系统拦截：当前计算机未获得财务授信，或无权访问此页面！</h3>"
            "<p>请确保您使用的是专用的财务工作站。如有疑问，请联系系统管理员签发设备授权证书。</p>",
            status=403
        )

# =========================================================================
# 📊 看板视图：查看待审核单据
# =========================================================================
class FinanceReviewDashboardView(FinanceSecurityMixin, View):
    """
    财务 Web 审核看板：仅限授权计算机访问
    """

    def get(self, request):
        # 状态0: 待财务审核
        pending_records = WithdrawRecord.objects.filter(status=0).select_related('user').order_by('create_time')

        review_list = []
        for rec in pending_records:
            commissions = CommissionRecord.objects.filter(
                user=rec.user,
                create_time__lte=rec.create_time
            ).select_related('order', 'buyer').order_by('-create_time')

            review_list.append({
                'record': rec,
                'commissions': commissions,
                'commissions_count': commissions.count()
            })

        return render(request, 'finance_review.html', {'review_list': review_list})

# =========================================================================
# 💰 打款动作视图：严密的并发悲观锁控制
# =========================================================================
class FinanceApproveTransferView(FinanceSecurityMixin, View):
    """
    财务点击通过：防并发重复打款 + 限制特定计算机操作
    """

    def _rsa_sign(self, message):
        """ RSA 签名保持不变 """
        key_path = os.path.join(settings.BASE_DIR, settings.WECHAT_PAY['PRIVATE_KEY_PATH'])
        with open(key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        signature = private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def post(self, request):
        out_bill_no = request.POST.get('out_bill_no')
        logger.info(f"========== [提现流水线] 收到打款请求，单号={out_bill_no} ==========")

        if not out_bill_no:
            return HttpResponse("<script>alert('参数缺失'); location.href='/app01/finance/review/';</script>")

        # 🌟🌟🌟 核心加锁区：防止双击或多操作员并发重复打款 🌟🌟🌟
        # 约定临时处理中状态：9 代表“微信通讯中”，避免并发踩踏
        try:
            with transaction.atomic():
                # 1. 使用 select_for_update() 实施行级悲观锁，强制排队
                withdraw_rec = WithdrawRecord.objects.select_for_update().filter(out_bill_no=out_bill_no).first()

                if not withdraw_rec:
                    return HttpResponse(
                        "<script>alert('单据不存在！'); location.href='/app01/finance/review/';</script>")

                if withdraw_rec.status != 0:
                    # 如果状态不是0，说明另一个财务人员的请求比你快了 0.001 秒，直接弹回
                    return HttpResponse(
                        f"<script>alert('拦截：该单据正在打款中或已被处理，请勿重复操作！当前状态:{withdraw_rec.get_status_display()}'); location.href='/app01/finance/review/';</script>")

                # 2. 瞬间把状态卡死为 9 (打款中)，锁住该单据
                withdraw_rec.status = 9
                if request.user and not request.user.is_anonymous:
                    withdraw_rec.auditor = request.user
                withdraw_rec.save(update_fields=['status', 'auditor'])

            # 🌟 走出 transaction.atomic()，意味着“状态改成9”成功保存并释放了行锁，
            # 此时别的操作员进来会直接触发上面的状态拦截。现在我们可以安全、慢吞吞地去调网络极其缓慢的微信 API 了。

        except Exception as lock_err:
            logger.error(f"并发锁争夺失败: {lock_err}")
            return HttpResponse(
                "<script>alert('系统繁忙，锁单失败，请稍后重试'); location.href='/app01/finance/review/';</script>")

        # 3. 稳稳地调用微信支付底层接口
        success, wexin_res = self.call_wechat_transfer_api(withdraw_rec)

        # 4. 根据网络通讯结果，二次更新单据的最终状态
        with transaction.atomic():
            # 重新锁定单据，更新最终结果
            final_rec = WithdrawRecord.objects.select_for_update().get(out_bill_no=out_bill_no)
            final_user = User.objects.select_for_update().get(id=final_rec.user.id)

            if success:
                tx_bill_no = wexin_res.get('transfer_bill_no', '')
                state = wexin_res.get('state', '')
                package_info = wexin_res.get('package_info', '')

                # 推进到 1 (待确认)
                final_rec.status = 1
                final_rec.transfer_bill_no = tx_bill_no
                final_rec.package_info = package_info
                final_rec.audit_time = timezone.now()
                final_rec.save(update_fields=['status', 'transfer_bill_no', 'package_info', 'audit_time'])

                # 扣除冻结资产
                final_user.frozen_balance -= final_rec.amount
                final_user.save(update_fields=['frozen_balance'])

                msg = "打款指令已成功发送至微信！"
                if state == "WAIT_USER_CONFIRM":
                    msg = "打款指令已接收，等待用户在小程序端点击确认收款！"
            else:
                # 🌟 防御降级：如果微信接口明确拒绝了（比如商户号没钱了），把状态打回 0 (待审核)，允许财务排查后重新发起
                final_rec.status = 0
                final_rec.save(update_fields=['status'])
                msg = f"微信接口报错，单据已回滚退回。原因：{str(wexin_res)}"

            return HttpResponse(f"<script>alert('{msg}'); location.href='/app01/finance/review/';</script>")

    def call_wechat_transfer_api(self, withdraw_rec):
        """ 最新版微信支付 V3 【发起转账】核心封装 (保持不变) """
        url_path = "/v3/fund-app/mch-transfer/transfer-bills"
        full_url = f"https://api.mch.weixin.qq.com{url_path}"

        payload = {
            "appid": settings.WECHAT_PAY["APPID"],
            "out_bill_no": withdraw_rec.out_bill_no,
            "transfer_scene_id": "1005",
            "openid": withdraw_rec.user.openid,
            "transfer_amount": int(withdraw_rec.amount * 100),
            "transfer_remark": "分销佣金提现",
            "transfer_scene_report_infos": [
                {"info_type": "岗位类型", "info_content": "分销推广员"},
                {"info_type": "报酬说明", "info_content": "小程序推广佣金"}
            ]
        }
        body_json = json.dumps(payload, separators=(',', ':'))

        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex.upper()
        sign_str = f"POST\n{url_path}\n{timestamp}\n{nonce}\n{body_json}\n"
        signature = self._rsa_sign(sign_str)

        mchid = settings.WECHAT_PAY['MCHID']
        serial_no = settings.WECHAT_PAY['CERT_SERIAL_NO']
        auth_header = (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
            f'nonce_str="{nonce}",signature="{signature}",'
            f'timestamp="{timestamp}",serial_no="{serial_no}"'
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": auth_header,
            "User-Agent": "Django-WechatPay-V3-Client"
        }

        try:
            res = requests.post(full_url, data=body_json, headers=headers, timeout=10)
            if res.status_code in [200, 201]:
                res_data = res.json()
                state = res_data.get("state")
                if state in ["ACCEPTED", "PROCESSING", "WAIT_USER_CONFIRM", "SUCCESS"]:
                    return True, res_data
                else:
                    return False, f"业务状态异常: {state} - {res_data}"
            else:
                return False, f"HTTP {res.status_code} - {res.text}"
        except Exception as e:
            return False, f"网络或系统异常: {str(e)}"

@csrf_exempt
@require_http_methods(["POST"])
def wx_code2openid(request):
    """
    微信code换取openid接口（纯工具，无需登录，不创建用户）
    入参：code (wx.login返回的授权码)
    返回：openid, session_key
    """
    try:
        req_data = json.loads(request.body)
        code = req_data.get('code', '')

        if not code:
            return JsonResponse({"code": 400, "msg": "缺少微信授权码code", "data": None})

        # 调用微信官方接口
        appid = settings.WECHAT_PAY['APPID']
        secret = settings.WECHAT_PAY['APP_SECRET']
        url = f"https://api.weixin.qq.com/sns/jscode2session?appid={appid}&secret={secret}&js_code={code}&grant_type=authorization_code"

        response = requests.get(url, timeout=10)
        wx_result = response.json()

        if 'openid' not in wx_result:
            errmsg = wx_result.get('errmsg', '换取失败')
            return JsonResponse({"code": 500, "msg": f"微信凭证换取失败：{errmsg}", "data": None})

        return JsonResponse({
            "code": 200,
            "msg": "获取成功",
            "data": {
                "openid": wx_result['openid'],
                "session_key": wx_result.get('session_key', '')
            }
        })

    except Exception as e:
        return JsonResponse({"code": 500, "msg": f"接口异常：{str(e)}", "data": None})


class WeChatCustomerServiceConfigView(APIView):
    """
    获取企业微信客服配置接口
    允许前端动态获取客服链接，方便后台随时更换客服人员而无需小程序重新发版
    """
    # 如果允许未登录用户咨询，可以去掉 IsAuthenticated
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # 这里为了演示写成固定变量。
        # 实际业务中，你可以把这两个值存在数据库的字典表或者 settings.py 中
        corp_id = settings.WECHAT_CUS['CorpID']
        kf_url = settings.WECHAT_CUS['URL']

        # 进阶玩法：你甚至可以根据 request.user 的星级 (star_level)
        # 返回不同的 kf_url，实现 VIP 专属客服分流！

        return Response({
            "code": 200,
            "msg": "获取客服配置成功",
            "data": {
                "corp_id": corp_id,
                "kf_url": kf_url
            }
        })
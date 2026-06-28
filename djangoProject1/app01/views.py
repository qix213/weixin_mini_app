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

# ===================== 2. 第三方库 =====================
import requests
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import AcsRequest

# ===================== 3. Django 核心组件 =====================
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.core.files.storage import default_storage
# ===================== 4. Django REST Framework (DRF) 相关 =====================
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
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

# 数据模型 (Models & Constants)
from .models import (
    Address, AIChatMessage, AIChatSession, Area, Banner, Cart, Category,
    Certification, Coupon, ExamQuestion, ExamRecord, ExpressLogistics,
    Goods, Index_Annonce, Notice, Order, OrderItem, PointsRecord,
    Recipient, SF_STATUS_MAP, STATUS_NAME_MAP, StoreSenderAddress,
    StudyCheckIn, User, UserCoupon, VideoCourse, VideoWatchLog, Welcome,
UpgradeOrder,MemberPrivilege
)

# 序列化器 (Serializers)
from .serializer import (
    AddressSerializer, BannerSerializer, BenefitSerializer, CartAddSerializer,
    CartSerializer, CategorySerializer, CertificationSerializer,
    ExamQuestionSerializer, ExamRecordSerializer, GoodsSerializer,
    IndexSerializer, MemberInfoSerializer, NoticeSerializer,
    OrderAddSerializer, PointsRecordSerializer, RecipientSerializer,
    RegisterSerializer, StudyCheckInSerializer, SubConsumeRecordSerializer,
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
from .models import CourseCategory, VideoCourse
from .serializer import CourseCategorySerializer, VideoCourseSerializer
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

            # 🌟 极简拼接逻辑
            video_link = ""
            if video.video_url:
                raw_path = video.video_url.strip()  # 去除前后多余空格

                # 如果你在后台不小心填了完整的 http 链接，直接用
                if raw_path.startswith('http'):
                    video_link = raw_path
                # 正常情况：拼接上专属域名
                else:
                    if not raw_path.startswith('/'):
                        raw_path = '/' + raw_path
                    video_link = f"https://video.lansik2026.com{raw_path}"

            return Response({
                "code": 200,
                "msg": "允许观看",
                "has_permission": True,
                "video_url": video_link
            })
        except Exception as e:
            logger.error(f"check_permission接口错误：{str(e)}")
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
                "log_id": log.id,
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
        token['nickname'] = user.nickname
        token['star_level'] = user.star_level
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user_info'] = {
            'nickname': user.nickname,
            'star_level': user.star_level,
            'points': user.points,
            'coupon_count': user.coupon_count,
            'member_id': user.member_id,
            'user_type': user.user_type
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 将前端传来的数据复制一份，变成可修改的字典
        if isinstance(request.data, dict):
            data = request.data.copy()
        else:
            data = request.data.dict() if hasattr(request.data, 'dict') else request.data.copy()

        # ================= 🌟 1. 支付状态拦截防火墙 =================
        user_type = int(data.get('user_type', 1))
        is_paid = data.get('is_paid', False)

        if user_type > 1 and str(is_paid).lower() not in ['true', '1']:
            logger.warning(f"越权注册拦截：试图在未支付状态下注册付费级别(类型:{user_type})")
            return Response({
                'code': 402,
                'msg': '系统检测到尚未完成支付，为保障资金安全，无法写入数据库！',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        # ================= 🌟 2. 微信一键登录核心解析逻辑 =================
        login_code = data.get('login_code')
        phone_code = data.get('phone_code')
        openid = None

        # 如果前端传了这两个票据，我们才去微信验票
        if login_code and phone_code:
            try:
                # 强烈建议在 settings.py 中配置这两个常量
                app_id = getattr(settings, 'WX_APP_ID', '替换成你的小程序APPID')
                app_secret = getattr(settings, 'WX_APP_SECRET', '替换成你的小程序SECRET')

                # (1) 解析 OpenID
                session_url = f"https://api.weixin.qq.com/sns/jscode2session?appid={app_id}&secret={app_secret}&js_code={login_code}&grant_type=authorization_code"
                session_res = requests.get(session_url).json()
                openid = session_res.get('openid')

                # (2) 获取 AccessToken 并在本地缓存 7000 秒 (防超频风控核心)
                access_token = cache.get('wx_access_token')
                if not access_token:
                    token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
                    token_res = requests.get(token_url).json()
                    access_token = token_res.get('access_token')
                    if access_token:
                        cache.set('wx_access_token', access_token, timeout=7000)

                if not access_token:
                    raise Exception("无法获取微信 access_token")

                # (3) 解析真实手机号
                phone_url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
                phone_res = requests.post(phone_url, json={"code": phone_code}).json()

                if phone_res.get('errcode') == 0:
                    real_phone = phone_res['phone_info']['phoneNumber']
                    # 🔥 最关键的一步：用真实的手机号覆盖掉前端发来的占位符 "微信授权手机号"
                    data['phone'] = real_phone
                else:
                    return Response({'code': 400, 'msg': f"手机号授权已过期或失效，请重试"})

            except Exception as e:
                logger.error(f"微信授权解析失败: {str(e)}")
                return Response({'code': 500, 'msg': '微信授权解析异常，请稍后重试'},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # =================================================================

        # ================= 🌟 3. 正常走原来的注册入库与发券流程 =================
        serializer = RegisterSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            update_fields_list = []
            # 1. 记录微信 OpenID
            if openid and hasattr(user, 'openid'):
                user.openid = openid
                update_fields_list.append('openid')

            # 2. 赋予会籍有效期 (如果是付费等级 2,3,4,5)
            if user.user_type > 1:
                user.expire_time = timezone.now() + timedelta(days=365)
                update_fields_list.append('expire_time')

            # 统一保存上述修改
            if update_fields_list:
                user.save(update_fields=update_fields_list)
            # 🌟🌟🌟 修复结束

            # 处理生日信息
            birth_date = data.get('birth_date')
            if birth_date:
                user.birth_date = birth_date
                user.last_birth_date_modify = timezone.now()
                user.save(update_fields=['birth_date', 'last_birth_date_modify'])

            self.send_register_coupons(user)
            success, msg = user.add_points(
                points=1000,
                points_type=1,
                related_desc='新用户注册专属积分，立即到账'
            )
            logger.info(f'会员{user.member_id}注册成功，积分赠送结果：{msg}')

            has_gift = False
            try:
                reg_coupon = Coupon.objects.filter(id=1).first()
                if reg_coupon:
                    target_count = {1: 2, 2: 2, 3: 4}.get(user.user_type, 5)
                    coupon_list = [
                        UserCoupon(
                            user=user,
                            coupon=reg_coupon,
                            start_time=timezone.now(),
                            end_time=timezone.now() + timedelta(days=90),
                            is_used=False
                        ) for _ in range(target_count)
                    ]
                    UserCoupon.objects.bulk_create(coupon_list)
                    has_gift = True
            except Exception as coupon_err:
                logger.error(f"发券异常: {coupon_err}")

            refresh = RefreshToken.for_user(user)

            response_data = {
                'nickname': user.nickname,
                'member_id': user.member_id,
                'user_type': user.user_type,
                'parent_member_id': user.parent_user.member_id if user.parent_user else None,
                'coupon_count': user.get_coupon_stats()['total'],
                'points': user.points
            }

            return Response({
                'code': 200,
                'msg': '注册成功',
                'has_gift': has_gift,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'data': response_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'code': 400, 'msg': f'注册失败：{str(e)}', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

    def send_register_coupons(self, user):
        COUPON_RULES = {
            1: [1],
            2: [2, 3],
            3: [4, 5],
            4: [6],
            5: [7]
        }

        coupon_ids = COUPON_RULES.get(user.user_type, [])
        if not coupon_ids:
            logger.warning(f'用户{user.member_id}（等级{user.user_type}）无对应注册优惠券规则')
            return

        user_coupons = []
        for coupon_id in coupon_ids:
            try:
                coupon = Coupon.objects.get(id=coupon_id, is_active=True)
                user_coupons.append(UserCoupon(
                    user=user,
                    coupon=coupon,
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(days=coupon.valid_days)
                ))
            except Coupon.DoesNotExist:
                logger.error(f'优惠券模板ID={coupon_id}不存在，跳过发放')
                continue

        if user_coupons:
            UserCoupon.objects.bulk_create(user_coupons)
            logger.info(f'用户{user.member_id}注册成功，发放{len(user_coupons)}张优惠券')


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
            # 读取配置中的小程序凭证
            app_id = getattr(settings, 'WX_APP_ID', '')
            app_secret = getattr(settings, 'WX_APP_SECRET', '')

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

            # 2. 换取真实手机号
            phone_url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
            phone_res = requests.post(phone_url, json={"code": phone_code}).json()

            if phone_res.get('errcode') == 0:
                real_phone = phone_res['phone_info']['phoneNumber']
            else:
                return Response({'code': 400, 'msg': "微信手机号授权已过期，请重新点击"})

            # 3. 核心流转：用手机号查数据库
            try:
                user = User.objects.get(phone=real_phone, is_active=True)

                # 查到了老用户，直接签发登录 Token！
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
                # 🌟 查无此人！返回 404，前端 login.js 收到后会自动跳去注册页！
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
        print("当前请求 Authorization 头：", request.META.get('HTTP_AUTHORIZATION', '无'))
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_user = request.user
        current_level_str = request.query_params.get('current_level', '0')
        # 1. ✅ 强制接收同步参数（打印日志）
        sync_logistics = request.query_params.get('sync_logistics', '0')
        print(f"【物流同步】前端传入参数：sync_logistics = {sync_logistics}")

        try:
            current_level = int(current_level_str)
        except ValueError:
            current_level = 0

        if not current_user.user_type or current_user.user_type < 2:
            return Response({
                'code': 403,
                'msg': '无权限查看下级消费记录，请升级会员等级',
                'data': []
            }, status=status.HTTP_403_FORBIDDEN)

        # 获取订单数据（原有逻辑）
        sub_consume_data = current_user.get_sub_consume_records(current_level)
        serializer = SubConsumeRecordSerializer(
            sub_consume_data,
            many=True,
            context={'request': request}
        )
        data = serializer.data

        # ===================== ✅ 规范物流同步（状态机由后端接管） =====================
        if sync_logistics == '1':
            print("【物流同步】开始执行订单状态自动更新...")

            # 为了能在循环中直接修改并返回给前端最新的状态，将数据深拷贝为可变字典
            import json
            mutable_data = json.loads(json.dumps(data))

            for member_item in mutable_data:
                orders = member_item.get('orders', [])
                for order_info in orders:
                    order_sn = order_info.get('order_sn')
                    if not order_sn:
                        continue

                    order = Order.objects.filter(order_sn=order_sn).first()
                    if not order:
                        continue

                    # 如果没有运单号，或者订单已经完结/取消，直接跳过
                    if not order.jd_waybill_code or order.status in [3, 4]:
                        continue

                    print(f"【物流同步】订单{order_sn} | 运单号：{order.jd_waybill_code}")

                    # 🌟 核心逻辑：获取该订单最新的真实物流轨迹
                    # （假设你数据库里有 Express 表存储轨迹，如果是调京东API，请换成你的API查询逻辑）
                    from .models import ExpressLogistics  # 替换为你的 Express 模型路径
                    latest_express = ExpressLogistics.objects.filter(order_sn=order_sn).order_by('-id').first()

                    if latest_express:
                        status_name = latest_express.logistics_status_name or ''
                        remark = latest_express.operation_remark or ''
                        combined_text = status_name + remark

                        # 1. 拦截签收：只要签收或妥投，必定是已完成(3)
                        if any(kw in combined_text for kw in ['签收', '完成', '妥投']):
                            if order.status != 3:
                                order.status = 3
                                order.save(update_fields=['status'])
                                order_info['status'] = 3
                                order_info['status_name'] = '已完成'

                        # 2. 拦截揽件/发货：只要小哥收件了、发车了，就是待收货(2)
                        elif any(kw in combined_text for kw in ['揽收', '运输', '派送', '发往', '发车', '在途']):
                            if order.status == 1:
                                order.status = 2  # 🌟 修复：这里改成 2 (待收货)
                                order.save(update_fields=['status'])
                                order_info['status'] = 2
                                order_info['status_name'] = '待收货'  # 🌟 统一文案

                        # 3. 如果只是“等待揽收/已接单”，依然保持 status=1，不做任何 update 处理

            # 将处理后的最新数据覆盖原 data
            data = mutable_data
        # ======================================================================

        return Response({
            'code': 200,
            'msg': '获取下级消费记录成功',
            'data': data
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

    def retrieve(self, request):
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
        question_map = {str(q.id): q for q in questions}

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
            course_type=int(course_type),
            score=total_score,
            is_pass=is_pass,
            user_answers=user_answers_snapshot
        )

        # 返回判卷结果给前端
        return Response({
            "code": 200,
            "msg": "交卷成功",
            "data": {
                "record_id": record.id,
                "score": total_score,
                "max_score": max_score,
                "is_pass": is_pass,
                "user_answers": user_answers_snapshot  # 前端拿到这个可以直接渲染“考试结果/错题解析页”
            }
        })


class CertificationViewSet(ModelViewSet):
    serializer_class = CertificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Certification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


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
        serializer = CartSerializer(cart_list, many=True)
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
            'data': {'cart_id': cart.id, 'num': cart.num}
        })


class CartListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("===== 购物车视图调试 =====")
        print(f"请求用户：{request.user}")
        print(f"用户ID：{request.user.id}")
        print(f"会员ID：{request.user.member_id}")
        print(f"是否认证：{request.user.is_authenticated}")
        print(f"权限通过：{self.check_permissions(request)}")
        try:
            cart_items = Cart.objects.filter(user=request.user)

            cart_list = []
            for item in cart_items:
                cart_list.append({
                    "id": item.id,
                    "goods_name": item.goods.name,
                    "goods_image": item.goods.image_url,
                    "num": item.num,
                    "price": float(item.goods.member_price),
                    "total_price": float(item.num * item.goods.member_price),
                    'is_support_point_exchange': item.goods.is_support_point_exchange
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
            default_address_id = default_address.id if default_address else ""

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

                    # 获取默认发货仓（完整寄件人信息）
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

                    goods_price = Decimal(str(goods.member_price))
                    total_money += goods_price * num

                    total_weight += Decimal(str(goods.weight)) * num
                    total_volume += Decimal(str(goods.volume)) * num

                    goods_items.append({
                        "cart": cart,
                        "goods": goods,
                        "num": num,
                        "price": goods_price
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

                # 创建订单记录
                order_sn = f"ORD{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

                # ==============================================
                # ✅ 核心修改：保存完整寄件人信息到订单
                # ==============================================
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

                    # 完整寄件人信息（姓名+电话+省市区+详细地址+完整地址）
                    sender_name=sender_address.sender_name if sender_address else None,
                    sender_phone=sender_address.sender_phone if sender_address else None,
                    sender_province=sender_address.province if sender_address else None,
                    sender_city=sender_address.city if sender_address else None,
                    sender_district=sender_address.district if sender_address else None,
                    sender_detail=sender_address.detail if sender_address else None,
                    sender_address=sender_address.full_address if sender_address else None,
                )
                logger.info(f"创建新订单：order_id={order.id}, 订单号={order_sn}")

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

            # ==============================================
            # ✅ 下单返回：携带完整寄件人信息
            # ==============================================
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
                    "sender_info": sender_info  # 完整寄件信息返回前端
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

        print("=" * 50)
        print(f"👉 当前系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"👉 准备扫描创建时间早于 {expire_threshold.strftime('%Y-%m-%d %H:%M:%S')} 的待付款订单")

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
        orders = Order.objects.filter(user=request.user, is_delete=False).order_by('-create_time')

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

            order = Order.objects.filter(base_filter).select_related('user', 'address', 'pick_up_store').first()

            if not order:
                return Response({"code": 404, "msg": "订单不存在"}, status=404)

            # 权限校验
            has_permission = False
            if str(order.user_id) == str(request.user.id):
                has_permission = True
            elif str(request.user.user_type) in ['4', '5']:
                buyer_parent_id = str(getattr(order.user, 'parent_user_id', ''))
                if buyer_parent_id == str(request.user.id):
                    has_permission = True

            if not has_permission:
                logger.warning(
                    f"❌ 内存级权限拦截：订单 {order.order_sn} 属于用户 ID={order.user_id}。当前登录用户 ID={request.user.id} 无权访问。")
                return Response({"code": 404, "msg": "无权查看该订单"}, status=404)

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
    生成供前端 wx.requestPayment 唤起收银台必备的 5 个签名参数
    """
    permission_classes = [IsAuthenticated]

    def _get_private_key(self):
        """ 动态读取商户 RSA 私钥 """
        key_path = os.path.join(settings.BASE_DIR, settings.WECHAT_PAY['PRIVATE_KEY_PATH'])
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _rsa_sign(self, message):
        """ 使用商户私钥进行 SHA256withRSA 签名 """
        private_key = self._get_private_key()
        signature = private_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _build_auth_header(self, method, url_path, timestamp, nonce, body=""):
        """ 构建微信 API v3 必备的 Authorization 请求头 """
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
        user = request.user
        order_id = request.data.get('order_id')
        point_deduct_raw = request.data.get('point_deduct', 0)
        point_deduct = int(point_deduct_raw) if point_deduct_raw else 0

        # 🌟 核心防御：微信原生 JSAPI 必须依赖用户的 openid
        openid = getattr(user, 'openid', None) or wx_get_user_openid_somehow(user)
        if not openid:
            return Response({"code": 400, "msg": "当前登录用户缺少核心支付凭证(OpenID)"}, status=400)

        try:
            with transaction.atomic():
                # 1. 锁单查询
                order = Order.objects.select_for_update().get(id=order_id, user=user, is_delete=False)
                if order.status != 0:
                    return Response({"code": 400, "msg": "订单状态异常，无法发起支付"}, status=400)

                # 2. 前置业务计算：如果用户使用了积分抵扣，在下单时记录到数据库中
                if point_deduct > 0 and not order.is_point_deducted:
                    # 汇率 100积分 = 1元
                    deduct_money = round(point_deduct * 0.01, 2)
                    order.point_deduct = point_deduct
                    order.point_deduct_money = deduct_money
                    order.actual_pay_money = max(order.total_price - deduct_money, 0.01)
                    order.save(update_fields=['point_deduct', 'point_deduct_money', 'actual_pay_money'])
                else:
                    # 如果没有抵扣，实付金额等于总金额
                    if not order.actual_pay_money:
                        order.actual_pay_money = order.total_price
                        order.save(update_fields=['actual_pay_money'])

                # 微信支付的金额单位是【分】，必须转换为整数型
                pay_price_cents = int(float(order.actual_pay_money) * 100)
                if pay_price_cents <= 0:
                    pay_price_cents = 1  # 最低 1 分钱测试

                # 3. 组装请求微信官方 JSAPI 统一下单接口的 Payload
                url_path = "/v3/pay/transactions/jsapi"
                full_url = f"https://api.mch.weixin.qq.com{url_path}"

                timestamp = str(int(time.time()))
                nonce = uuid.uuid4().hex.upper()

                body_data = {
                    "appid": settings.WECHAT_PAY['APPID'],
                    "mchid": settings.WECHAT_PAY['MCHID'],
                    "description": f"购买商品-{order.goods_names_str[:30]}",
                    "out_trade_no": order.order_sn,
                    "notify_url": settings.WECHAT_PAY['NOTIFY_URL'],
                    "amount": {
                        "total": pay_price_cents,
                        "currency": "CNY"
                    },
                    "payer": {
                        "openid": openid
                    }
                }
                body_json = json.dumps(body_data, separators=(',', ':'))

                # 4. 生成签名请求头并向微信发起下单请求
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

                # =========================================================
                # 5. 🌟 核心：为前端 wx.requestPayment 生成二次签名参数
                # =========================================================
                front_timestamp = str(int(time.time()))
                front_nonce = uuid.uuid4().hex.upper()
                package_str = f"prepay_id={prepay_id}"
                appid = settings.WECHAT_PAY['APPID']

                # 二次签名拼接规则 (严格按换行符区分)
                front_sign_message = f"{appid}\n{front_timestamp}\n{front_nonce}\n{package_str}\n"
                front_signature = self._rsa_sign(front_sign_message)

                # 构造符合小程序前端拉起键盘所需格式的完整数据包
                pay_params = {
                    "timeStamp": front_timestamp,
                    "nonceStr": front_nonce,
                    "package": package_str,
                    "signType": "RSA",
                    "paySign": front_signature
                }

                return Response({
                    "code": 200,
                    "msg": "预支付参数生成成功",
                    "data": pay_params
                })

        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "未找到有效待支付订单"}, status=404)
        except Exception as e:
            return Response({"code": 500, "msg": f"系统发起支付故障: {str(e)}"}, status=500)


def wx_get_user_openid_somehow(user):
    """ 兜底函数：如果你的 user 属性名不叫 openid，请在此行完成映射转换 """
    return getattr(user, 'username', None)  # 根据实际调整

class WechatPayCallbackView(APIView):
    """
    【微信支付 V3 官方异步回调接口】
    注意：此接口由微信服务器调用，没有任何用户登录态！
    """
    authentication_classes = []  # 核心：必须免登录
    permission_classes = []  # 核心：允许任何来源（依靠验签保证安全）

    def decrypt_wechat_resource(self, resource):
        """ AES-256-GCM 解密微信 V3 报文 """
        api_v3_key = settings.WECHAT_PAY['API_V3_KEY'].encode('utf-8')
        nonce = resource['nonce'].encode('utf-8')
        associated_data = resource.get('associated_data', '').encode('utf-8')
        ciphertext = base64.b64decode(resource['ciphertext'])

        aesgcm = AESGCM(api_v3_key)
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(decrypted_data.decode('utf-8'))

    def post(self, request):
        print("===== 收到微信支付 V3 异步回调 =====")
        try:
            # 1. 获取并解密微信发来的密文
            event_data = request.data
            if event_data.get('event_type') != 'TRANSACTION.SUCCESS':
                return Response({'code': 'SUCCESS', 'message': '非支付成功通知，忽略'})

            resource = event_data.get('resource', {})
            decrypted_data = self.decrypt_wechat_resource(resource)

            # 2. 提取支付核心数据
            order_sn = decrypted_data.get('out_trade_no')  # 商户订单号
            transaction_id = decrypted_data.get('transaction_id')  # 微信支付系统订单号
            total_fee = decrypted_data.get('amount', {}).get('total', 0) / 100.0  # 真实支付金额(元)

            print(f"微信通知支付成功：订单号={order_sn}, 微信单号={transaction_id}, 支付金额={total_fee}元")

            # 3. 开启事务，执行核心业务逻辑
            with transaction.atomic():
                # 锁定订单，防止并发回调导致多次发货
                order = Order.objects.select_for_update().filter(order_sn=order_sn).first()
                if not order:
                    print(f"警告：找不到对应的订单 {order_sn}")
                    return Response({'code': 'SUCCESS', 'message': '订单不存在'}, status=200)

                if order.status != 0:
                    print(f"订单 {order_sn} 已处理过，忽略本次回调")
                    return Response({'code': 'SUCCESS', 'message': '成功'}, status=200)

                # ✅ 核心转变：这里不能用 request.user，必须用 order.user！
                user = order.user

                # ================= 业务 1: 更新订单状态 =================
                order.status = 1  # 变更为待发货/待取货
                order.pay_method = 1  # 1 为微信支付
                order.pay_no = transaction_id
                order.pay_time = timezone.now()
                # 保险起见，覆盖实际支付金额为微信真正扣款的金额
                order.actual_pay_money = total_fee
                order.save(update_fields=['status', 'pay_method', 'pay_no', 'pay_time', 'actual_pay_money'])

                # ================= 业务 2: 扣除使用的抵扣积分 =================
                deduct_point = order.point_deduct or 0
                if deduct_point > 0 and not PointsRecord.objects.filter(
                        user=user, points_type=4, related_id=order.order_sn).exists():
                    success, msg = user.add_points(
                        points=-deduct_point,
                        points_type=4,
                        related_id=order.order_sn,
                        related_desc=f"订单{order.order_sn}支付成功，抵扣{deduct_point}积分"
                    )
                    if not success:
                        raise Exception(f"积分抵扣扣减失败：{msg}")

                # ================= 业务 3: 赠送消费积分 =================
                has_given = PointsRecord.objects.filter(
                    user=user, points_type=2, related_id=order.order_sn).exists()

                if not has_given and total_fee > 0:
                    base_points = round(total_fee * 10)
                    is_birthday_month = user.is_birthday_month() if hasattr(user, 'is_birthday_month') else False
                    final_points = base_points * 2 if is_birthday_month else base_points

                    if final_points > 0:
                        success, msg = user.add_points(
                            points=final_points,
                            points_type=2,
                            related_id=order.order_sn,
                            related_desc=f"订单消费{total_fee}元，赠送{final_points}积分"
                        )
                        if success:
                            print(f"消费积分发放成功：{final_points}积分")

            print(f"===== 订单 {order_sn} 回调处理圆满完成 =====")
            # 必须严格返回 200 和特定的 JSON 格式，否则微信服务器会一直重复通知你
            return Response({'code': 'SUCCESS', 'message': '成功'})

        except Exception as e:
            traceback.print_exc()
            # 如果出错，返回 500，微信会在稍后重试通知
            return Response({'code': 'FAIL', 'message': f'服务器内部错误: {str(e)}'}, status=500)


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
    return_format = request.GET.get('format', '')
    order_sns_str = request.GET.get('order_sns', '')
    order_sns = order_sns_str.split(',') if order_sns_str else []

    logistics_list = ExpressLogistics.objects.filter(
        order_sn__in=order_sns,
        is_delete=False
    ).order_by("-logistics_time")

    if return_format == 'json':
        data = []
        for item in logistics_list:
            data.append({
                "order_sn": item.order_sn,
                "logistics_no": item.logistics_no,
                "logistics_company": item.logistics_company,
                "logistics_time": item.logistics_time.strftime("%Y-%m-%d %H:%M:%S"),
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

    accept_header = request.META.get('HTTP_ACCEPT', '')
    if 'application/json' in accept_header:
        data = []
        for item in logistics_list:
            data.append({
                "order_sn": item.order_sn,
                "logistics_no": item.logistics_no,
                "logistics_company": item.logistics_company,
                "logistics_time": item.logistics_time.strftime("%Y-%m-%d %H:%M:%S"),
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
import ollama

# ==========================================
# 🌟 小程序必备：引入 JWT 和 数据库模型
# ==========================================
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import UserSkinProfile


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
        print(f"后端读取到的题库数据: {data}")

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

from django.core.files.base import ContentFile
import base64
import uuid, io
from PIL import Image


@csrf_exempt
def wx_chat_stream_api(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # 1. JWT 身份认证
    try:
        jwt_authenticator = JWTAuthentication()
        auth_result = jwt_authenticator.authenticate(request)
        if auth_result is None:
            return JsonResponse({"error": "未提供有效Token"}, status=401)
        current_user, token = auth_result
    except Exception as e:
        return JsonResponse({"error": f"身份验证失败: {str(e)}"}, status=401)

    # 2. 提取参数
    user_query = request.POST.get('query', '').strip()
    step = request.POST.get('step', 'chat').strip()

    safe_print(f"\n[{time.strftime('%H:%M:%S')}] [请求入栈] 用户: {current_user.member_id} | 步骤: {step}")

    # 3. 闭包生成响应数据
    def generate_response(user, step_val, query_val):
        try:
            profile = None

            # 🌟 1. 核心数据锁定逻辑：精准定位当前进行中的被测人档案
            if step_val == 'submit_questionnaire':
                try:
                    payload = json.loads(query_val)
                    sub_name = payload.get('subject_name', '').strip()
                    answers_dict = payload.get('answers', {})

                    # 优先寻找第一步拍照存档时创建的那个专属档案
                    if sub_name:
                        profile = UserSkinProfile.objects.filter(user=user, subject_name=sub_name).order_by(
                            '-id').first()

                    # 💡 核心修复：如果找不到档案（说明用户在第一步点击了“跳过照片”），则在此处为该被测人当场创建专属全新档案！
                    if not profile:
                        profile = UserSkinProfile.objects.create(user=user, subject_name=sub_name or "未命名")

                    # 解析并运行原有的测肤算法，将标签锁定在该档案中
                    skin_tags = evaluate_skin_type(answers_dict)
                    profile.skin_tags = skin_tags
                    profile.save()
                except Exception as e:
                    safe_print(f"问卷解析或肤质计算失败: {e}")
                    if not profile:
                        profile = UserSkinProfile.objects.create(user=user, subject_name="未命名")
                    profile.skin_tags = ["中性皮肤"]
                    profile.save()
            else:
                # 随后的 analyze 和 generate_plan 步骤直接锁定该用户最后操作过的（即最新创建/更新）的那一笔档案
                profile = UserSkinProfile.objects.filter(user=user).order_by('-id').first()

            # 极端防御性容错
            if not profile:
                profile = UserSkinProfile.objects.create(user=user, subject_name="未命名")

            # ==================== --- 步骤 2：问卷提交响应 --- ====================
            if step_val == 'submit_questionnaire':
                yield f"📝 **被测人 [{profile.subject_name}] 的深度测肤问卷已完成分析！**\n\n宝贝，系统已经为您建立了基础肌肤档案。接下来，请点击下方按钮，蓝博士将为您生成深度诊断报告。".encode(
                    'utf-8')
                yield b"[SHOW_STEP_3]"
                return

            # ==================== --- 步骤 3：综合定性分析 --- ====================
            elif step_val in ['analyze', 'skip_and_analyze']:
                target_skin_keys = profile.skin_tags if profile.skin_tags else ["中性皮肤"]
                fresh_db = load_knowledge()
                skin_types_data = fresh_db.get("皮肤类型s", [])

                combined_principles = ""
                for skin_key in target_skin_keys:
                    skin_data = next((item for item in skin_types_data if item["皮肤类型"] == skin_key), None)
                    if skin_data:
                        combined_principles += f"【{skin_key} 护肤原则】：{skin_data.get('护肤原则', '')}\n"

                # 🌟 100% 还原你最初的提示词结构，绝不动一个字，保证小模型输出结论精准稳定
                prompt = f"你是专业护肤私教蓝博士。用户肤质：{', '.join(target_skin_keys)}。\n原则：{combined_principles}\n请专业、温柔地解释为何得出此肤质结论，并阐述护理逻辑。禁止推荐具体产品。最后以‘宝贝，核心问题分析完毕！下一步，蓝博士将为您精准匹配产品方案...’结尾。"

                stream = ollama.chat(model='qwen2.5:3b', messages=[{'role': 'user', 'content': prompt}], stream=True,
                                     options={"temperature": 0.2})
                for chunk in stream:
                    yield chunk['message']['content'].encode('utf-8')
                yield b"[SHOW_STEP_4]"
                return

            # ==================== --- 步骤 4：生成终极方案 --- ====================
            elif step_val == 'generate_plan':
                target_skin_keys = profile.skin_tags if profile.skin_tags else ["中性皮肤"]
                primary_skin = target_skin_keys[0]

                fresh_db = load_knowledge()
                skin_types_data = fresh_db.get("皮肤类型s", [])
                skin_data = next((item for item in skin_types_data if item["皮肤类型"] == primary_skin), {})

                treatment = skin_data.get("居家产品方案", {})
                tips = skin_data.get("注意事项", [])

                # 🌟 100% 还原你最初的方案生成提示词，绝不动一个字
                prompt = f"""
你是专属顾问蓝博士。请为【{primary_skin}】用户生成专属护肤方案。

### [数据参考]：
1. 护肤流程数据：{json.dumps(treatment, ensure_ascii=False)}
2. 注意事项数据：{json.dumps(tips, ensure_ascii=False)}

### [输出指令]：
1. **直接输出方案**：禁止输出任何“产品清单”列表。
2. **构建精美表格**：将“护肤流程数据”转换为 Markdown 表格，表头为 | 护理时段/阶段 | 详细操作步骤与产品推荐 |。
3. **内容完整性**：必须原样呈现数据中的详细步骤，不可精简。
4. **注意事项列表**：将“注意事项数据”以无序列表形式附在下方，每条前加一个 Emoji。
5. **语气要求**：亲切专业，禁止输出无关废话。

开头：宝贝，根据您的肤质诊断，这是蓝博士为您量身定制的专属使用方案，请查收：
结尾：方案生成完毕！您可以随时向蓝博士提问，或者返回第一步重新测试哦～
"""
                stream = ollama.chat(model='qwen2.5:3b', messages=[{'role': 'user', 'content': prompt}], stream=True,
                                     options={"temperature": 0.1})
                for chunk in stream:
                    yield chunk['message']['content'].encode('utf-8')
                return

        except Exception as e:
            yield f"\n\n❌ 运行异常: {str(e)}".encode('utf-8')

    # 4. 响应输出
    response = StreamingHttpResponse(generate_response(current_user, step, user_query),
                                     content_type='application/octet-stream')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response

import json
import base64
import hashlib
import hmac
import time
import urllib.request
from datetime import datetime
from urllib.parse import urlencode
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Order
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
            print("=" * 50)
            print(f"📦 订单 {order_sn} 京东预校验成功！预估运费：{total_freight} 元")
            print("=" * 50)

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
        base_uri = config["PROD_API"]
        app_key = config["APP_KEY"]
        app_secret = config["APP_SECRET"]
        access_token = config["ACCESS_TOKEN"]
        domain = config["DOMAIN"]
        customer_code = config["CUSTOMER_CODE"]
        algorithm = config["ALGORITHM"]
        version = config["VERSION"]
        path = "/ecap/v1/orders/create"

        # 🌟 2. 将动态提取的参数，完美组装进京东官方 cargoes 报文中
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
                "name": cargo_name,       # 🌟 动态物品名称
                "quantity": quantity,
                "weight": cargo_weight,   # 🌟 动态重量
                "volume": cargo_volume    # 🌟 动态体积
            }]
        }], ensure_ascii=False)

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

    except Exception as e:
        import traceback
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

from .models import UserSkinProfile, SkinPhotoRecord
from rest_framework.decorators import api_view, permission_classes
from .serializer import UserSkinProfileSerializer
# ================= 1. 照片纯存档接口 =================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_skin_photo(request):
    """保存被测人照片（仅存档不分析）"""
    subject_name = request.data.get('subject_name')
    photo_file = request.FILES.get('file')

    if not subject_name or not photo_file:
        return Response({'code': 400, 'msg': '缺少被测人姓名或照片文件'}, status=400)

    try:
        subject_name = subject_name.strip()

        # 🌟 核心修复：用 filter + first 替代 get_or_create。
        # 哪怕数据库里因为历史bug存了10个叫"张三"的档案，这里也只会安静地取出最新的一个，绝不报错！
        profile = UserSkinProfile.objects.filter(
            user=request.user,
            subject_name=subject_name
        ).order_by('-id').first()

        created = False
        if not profile:
            # 如果没找到，再干净利落地新建一个
            profile = UserSkinProfile.objects.create(
                user=request.user,
                subject_name=subject_name
            )
            created = True

        # 追加保存照片记录 (一对多关系：一个profile可以有多张照片)
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

    if target_level <= current_level:
        return Response({"code": 400, "msg": "目标等级必须高于当前等级"})

    # 硬编码价格字典，防止前端篡改金额
    level_prices = {
        2: 980.00,
        3: 3980.00,
        4: 9800.00,
        5: 39800.00
    }

    if target_level not in level_prices:
        return Response({"code": 400, "msg": "非法的升级等级"})

    amount = level_prices[target_level]

    # 创建订单
    order = UpgradeOrder.objects.create(
        user=user,
        target_level=target_level,
        amount=amount,
        status=0
    )

    return Response({
        "code": 200,
        "msg": "订单创建成功",
        "data": {
            "order_id": order.out_trade_no,
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

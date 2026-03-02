
# 视图文件 - 修复logger未定义 + 冗余代码 + 语法错误

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
import time
import datetime
import random
import json
import logging
from django.utils import timezone

# 第三方库导入
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action  # 新增：导入action装饰器
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from rest_framework import permissions, status, filters
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import AcsRequest

# 本地导入
from .models import (
    Welcome, Banner, Notice, Index_Annonce, Category, Goods, User,
    VideoCourse, StudyCheckIn, ExamQuestion, ExamRecord, Certification,
    Cart, Recipient, Address, Order, OrderItem, Area, VideoWatchLog,
    Coupon, UserCoupon
)
from .serializer import (
    BannerSerializer, NoticeSerializer, IndexSerializer,
    CategorySerializer, GoodsSerializer, VideoCourseSerializer,
    BenefitSerializer, UserProfileSerializer, StudyCheckInSerializer, ExamQuestionSerializer,
    ExamRecordSerializer, CertificationSerializer, RegisterSerializer, MemberInfoSerializer,
    SubConsumeRecordSerializer, CartSerializer, CartAddSerializer, RecipientSerializer,
    AddressSerializer, OrderAddSerializer, UserCouponSerializer,UserCouponStatsSerializer
)

# 全局日志配置（修复CartClearView中logger未定义问题）
logger = logging.getLogger(__name__)

# 阿里云短信配置（需替换为真实密钥）
ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
REGION_ID = "cn-hangzhou"  # 修正：号码认证服务正确地域为cn-hangzhou
client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION_ID)

# ===================== 基础视图 =====================
def index(request):
    time.sleep(1)
    return JsonResponse({'name':'嘉俊','sex':'男','age':'18'})

def welcome(request):
    res = Welcome.objects.all().order_by('-order').first()
    img = 'http://localhost:8000/media/' + str(res.img)
    return JsonResponse({'code':100, 'msg':'成功', 'result':img})

# ===================== Banner/公告视图 =====================
class BannerView(ListModelMixin, GenericViewSet):
    queryset = Banner.objects.filter(is_delete=False).order_by('order')[:4]
    permission_classes = [AllowAny]
    serializer_class = BannerSerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        notice = Notice.objects.all().order_by('create_time').first()
        serializer_notice = NoticeSerializer(instance=notice)
        return Response({'code':100, 'msg':'成功','banner':res.data, 'notice':serializer_notice.data})

# ===================== 商品分类/商品视图 =====================
class CategoryView(ListModelMixin, GenericViewSet):
    permission_classes = [AllowAny]
    queryset = Category.objects.all().order_by('id')
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
    # 关联查询images，避免N+1查询，提升性能
    queryset = Goods.objects.all().order_by('id').prefetch_related('images')
    serializer_class = GoodsSerializer

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
        return Response({
            'code': 200,
            'msg': 'success',
            'data': res.data
        })

    def retrieve(self, request, *args, **kwargs):
        try:
            res = super().retrieve(request, *args, **kwargs)
            return Response({
                'code': 200,
                'msg': 'success',
                'data': res.data
            })
        except Exception as e:
            return Response({
                'code': 404,
                'msg': '商品不存在',
                'data': {}
            })
class VideoCourseViewSet(ModelViewSet):
    queryset = VideoCourse.objects.filter(is_publish=True)
    serializer_class = VideoCourseSerializer
    permission_classes = [IsAuthenticated]  # 必须登录才能访问

    def get_queryset(self):
        """
        重构过滤逻辑：
        1. 前端不传required_level（全部视频）：返回所有已发布视频，不做等级过滤
        2. 前端传required_level（其他分类）：按传的等级+用户等级过滤
        """
        # 基础查询：只取已发布的视频
        queryset = VideoCourse.objects.filter(is_publish=True)

        # 1. 处理搜索功能（保留）
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(title__icontains=search)

        # 2. 获取前端传递的required_level参数
        required_level = self.request.query_params.get('required_level', '')
        user = self.request.user
        user_level = user.user_type or 1  # 默认蓝朋友（等级1）

        # 核心逻辑：仅当前端传了有效的required_level时，才做等级过滤
        if required_level and required_level.isdigit():
            required_level_int = int(required_level)
            # 过滤逻辑：视频所需等级 = 前端传的等级 且 ≤ 用户等级（保持原有分类逻辑）
            queryset = queryset.filter(
                required_level=required_level_int,
                required_level__lte=user_level
            )
        # 前端不传required_level（全部视频）：不添加任何等级过滤条件，返回所有已发布视频

        return queryset

    # 以下方法（check_permission、add_play_count）保持不变
    @action(detail=True, methods=['get'])
    def check_permission(self, request, pk=None):
        try:
            video = self.get_object()
            # 简单权限判断：用户等级 >= 视频所需等级
            user_level = request.user.user_type if hasattr(request.user, 'user_type') else 1
            has_permission = user_level >= video.required_level

            # 等级名称映射
            level_name_map = {
                1: "蓝朋友",
                2: "蓝明星",
                3: "护肤私教",
                4: "MINI-studio 主理人",
                5: "Ta创+"
            }

            return Response({
                "code": 200,
                "msg": "有权限观看" if has_permission else "权限不足",
                "has_permission": has_permission,
                "video_url": request.build_absolute_uri(video.video_url.url) if video.video_url else "",
                "required_level_name": level_name_map.get(video.required_level, "未知等级")
            })
        except Exception as e:
            logger.error(f"check_permission接口错误：{str(e)}")
            return Response({
                "code": 500,
                "msg": "权限校验失败"
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

            # 1. 已获取VideoCourse实例（关键：video是实例，不是ID）
            video = self.get_object()

            # 2. get_or_create中直接传实例给video字段
            log, created = VideoWatchLog.objects.get_or_create(
                user=request.user,
                video=video,  # ✅ 正确：传VideoCourse实例
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
        duration = video.duration_seconds or 0

        try:
            log = VideoWatchLog.objects.get(user=user, video=video)
        except VideoWatchLog.DoesNotExist:
            return Response({"code": 400, "msg": "请先调用开始播放接口"})

        # 只允许正常播放，不允许跳秒
        last = log.total_watch_sec
        if current_time - last > 5:
            return Response({
                "code": 403,
                "msg": "检测到快进，观看无效",
                "invalid": True
            })

        # ========== 修复：同时更新total_watch_sec和last_progress_sec ==========
        log.total_watch_sec = current_time
        log.last_progress_sec = current_time  # 新增：更新最后上报进度
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
        """视频播放完成，发放积分"""
        video = self.get_object()
        user = request.user
        logger.info(f"【watch_finish】用户{user.id}，视频{pk}，视频时长：{video.duration_seconds}")

        # ========== 修复1：兼容时长异常的边界情况 ==========
        # 1. 优先用视频实际时长（如果后端存储的时长异常，用前端上报的最后进度兜底）
        video_duration = video.duration_seconds or 0
        if video_duration <= 0:
            # 尝试从观看日志中获取最后上报的进度，作为视频时长兜底
            try:
                log = VideoWatchLog.objects.get(user=user, video=video)
                video_duration = log.last_progress_sec or 60  # 至少设为60秒，避免除以0
            except VideoWatchLog.DoesNotExist:
                logger.error(f"【时长异常】用户{user.id}视频{pk}无观看日志，无法获取时长")
                return Response({
                    "code": 400,
                    "msg": "未检测到有效观看记录，无法领取积分"
                })

        # 2. 获取观看日志并校验观看时长
        try:
            log = VideoWatchLog.objects.get(user=user, video=video)
        except VideoWatchLog.DoesNotExist:
            return Response({
                "code": 400,
                "msg": "请先开始播放视频，再领取积分"
            })

        # ========== 修复2：宽松的时长校验逻辑 ==========
        # 观看时长≥视频时长的90% 即视为完成（避免因秒数差导致校验失败）
        watch_duration = log.total_watch_sec or 0
        if watch_duration <= 0:
            return Response({
                "code": 400,
                "msg": "有效观看时长为0，无法领取积分"
            })

        # 计算完成率（允许10%的误差）
        completion_rate = watch_duration / video_duration
        logger.info(
            f"【完成率】用户{user.id}视频{pk}：观看{watch_duration}秒/总{video_duration}秒，完成率{completion_rate:.2f}")

        if completion_rate < 0.9:
            return Response({
                "code": 400,
                "msg": f"观看时长不足（仅完成{completion_rate * 100:.0f}%），需观看90%以上才能领取积分"
            })

        # ========== 修复3：防止重复发放积分 ==========
        if log.point_given:
            return Response({
                "code": 200,
                "msg": "积分已发放，无需重复领取"
            })

        # ========== 发放积分逻辑 ==========
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

        # 更新观看日志
        log.is_finished = True
        log.point_given = True
        log.watch_end = timezone.now()
        log.save()

        # 刷新用户积分并返回结果
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

from datetime import timedelta
from .models import Coupon, UserCoupon  # 确保导入了这两个模型

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()  # 创建用户
            self.send_register_coupons(user)

            # ============= 新增：注册成功自动送1000积分 =============
            success, msg = user.add_points(
                points=1000,
                points_type=1,  # 1=注册赠送
                related_desc='新用户注册专属积分，立即到账'
            )
            logger.info(f'会员{user.member_id}注册成功，积分赠送结果：{msg}')
            # --- 发券逻辑（确保数据库同步创建） ---
            actual_issue_count = 0
            has_gift = False
            try:
                reg_coupon = Coupon.objects.filter(id=1).first()
                if reg_coupon:
                    # 确定发放数量
                    if user.user_type in [1, 2]:
                        target_count = 2
                    elif user.user_type == 3:
                        target_count = 4
                    else:
                        target_count = 5

                    # 批量创建
                    coupon_list = [
                        UserCoupon(
                            user=user,
                            coupon=reg_coupon,
                            end_time=timezone.now() + timedelta(days=90),
                            is_used=False
                        ) for _ in range(target_count)
                    ]
                    UserCoupon.objects.bulk_create(coupon_list)
                    actual_issue_count = target_count
                    has_gift = True
            except Exception as coupon_err:
                print(f"发券异常: {coupon_err}")
            # 你现有代码：生成token、返回数据
            refresh = RefreshToken.for_user(user)

            # 1. 基础数据来自序列化器
            # 注意：这里如果 serializer 没有包含所有字段，可以手动构建字典
            response_data = {
                'nickname': user.nickname,
                'member_id': user.member_id,
                'user_type': user.user_type,
                'parent_member_id': user.parent_user.member_id if user.parent_user else None,
                'coupon_count': user.get_coupon_stats()['total'],  # 新增：返回优惠券总数
                'points': user.points  # 动态字段
            }

            return Response({
                'code': 200,
                'msg': '注册成功',
                'has_gift': has_gift,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'data': response_data  # 👈 统一使用 data 节点
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'code': 400,
                'msg': f'注册失败：{str(e)}',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
    def send_register_coupons(self, user):
        """根据用户等级发放注册优惠券"""
        # 定义各等级发放规则（key=user_type，value=优惠券模板ID列表）
        COUPON_RULES = {
            1: [1],  # 蓝朋友：发放ID=1的优惠券（如200元代金券）
            2: [2,3],  # 蓝明星：发放ID=2（100元代金券）+ ID=3（9折券）
            3: [4,5],  # 护肤私教：发放ID=4（500元代金券）+ ID=5（8折券）
            4: [6],  # MINI-studio主理人：发放ID=6（7折券）
            5: [7]   # Ta创+：发放ID=7（5折券）
        }

        # 获取当前用户应发放的优惠券模板ID
        coupon_ids = COUPON_RULES.get(user.user_type, [])
        if not coupon_ids:
            logger.warning(f'用户{user.member_id}（等级{user.user_type}）无对应注册优惠券规则')
            return

        # 批量创建用户优惠券
        user_coupons = []
        for coupon_id in coupon_ids:
            try:
                coupon = Coupon.objects.get(id=coupon_id, is_active=True)
                user_coupons.append(UserCoupon(
                    user=user,
                    coupon=coupon,
                    start_time=timezone.now(),
                    end_time=timezone.now() + datetime.timedelta(days=coupon.valid_days)
                ))
            except Coupon.DoesNotExist:
                logger.error(f'优惠券模板ID={coupon_id}不存在，跳过发放')
                continue

        # 批量保存（提升性能）
        if user_coupons:
            UserCoupon.objects.bulk_create(user_coupons)
            logger.info(f'用户{user.member_id}注册成功，发放{len(user_coupons)}张优惠券')
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

            # 1. 序列化基础用户信息
            serializer = MemberInfoSerializer(request.user)

            # 2. 动态计算额外字段
            coupon_count = UserCoupon.objects.filter(user=request.user).count()
            points = getattr(request.user, 'points', 0)

            # 3. 构造统一的返回结构
            # 我们把动态字段合并到 serializer.data 中，方便前端直接读取
            response_data = serializer.data
            response_data['coupon_count'] = coupon_count
            response_data['points'] = points

            # 按照你要求的 return Response 格式
            return Response({
                'code': 200,
                'msg': '获取会员信息成功',
                'data': response_data  # 👈 所有的用户信息都在这里
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print('获取会员信息异常：', str(e))
            return Response({
                'code': 500,
                'msg': f'获取会员信息失败：{str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# app01/views.py 中的 SubUserConsumeView
class SubUserConsumeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_user = request.user
        current_level_str = request.query_params.get('current_level', '0')
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

        sub_consume_data = current_user.get_sub_consume_records(current_level)
        # 关键：传入context，让序列化器能获取当前用户（判断权限）
        serializer = SubConsumeRecordSerializer(
            sub_consume_data,
            many=True,
            context={'request': request}  # 必须传入！
        )

        return Response({
            'code': 200,
            'msg': '获取下级消费记录成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

class BenefitViewSet(GenericViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = BenefitSerializer

    def list(self, request):
        user_type = request.query_params.get('user_type')
        if not user_type or not user_type.isdigit():
            return Response(
                {'code': 400, 'msg': '请指定有效用户类型（1-蓝朋友，2-蓝明星，3-TA创粉）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user_type = int(user_type)
        fee_map = {1: "0元/年", 2: "980元/年", 3: "3980元/年", 4: "9800元", 5: "9.8万元" }
        benefit_map = {
            1: [
                "SSTA新人券：2张200元代金券套，只能用来购买368元mini旅行套；",
                "SSTA价格：零售价格购买产品，不享受会员价；",
                "SSTA卡券：节日活动或生日优享券，优享活动参与资格；",
                "公益课程：护肤知识课程。"
            ],
            2: [
                "蓝粉VIP大礼包（2选1）:（1）3套SSTA旅行套盒，2张100元兑换单品券（每单限用一张），限期一个月；（2）一套小油净化（6次），4张100元兑换单品券，每单限用一张），限期一个月；",
                "会员星价：SSTA家居产品，一年蓝粉星价",
                "会员积分：SSTA家居产品，1元积10分，可兑换",
                "SSTA卡券：节日活动或生日优享券，优享活动参与资格",
                "公益课程：家居护肤课程。"
            ],
            3: [
                "SSTA大礼包（2选1）:（1）3980元SSTA家居产品任选，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；（2）一年24次SSTA小油净化，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；",
                "SSTA积分：SSTA家居产品积分兑换，1元积10分；",
                "SSTA奇肌币：裂变客户购买产品15%返点，可提现；",
                "SSTA卡券：节日或活动优享券；",
                "专业课程：护肤专业课程。"
            ],
            4: [
                "产品折扣：享产品零售价5折权益，产品任选；",
                "培训赋能：护肤私教初级班+初级证书；",
                "工具系统：系统化配套标准化+工具设备；",
                "专业课程：蓝色奇肌商学院小程序专业皮肤课程。"
            ],
            5: [
                "Ta创+高端俱乐部会员，享奇肌疗愈营，高端沙龙活动；",
                "产品折扣：享产品零售价2.5折权益，产品任选；",
                "SSTA运营：运营中心模版店的打造及扶持；",
                "培训赋能：护肤私教全部体系课程+证书；",
                "专业课程：蓝色奇肌商学院小程序专业皮肤课程；",
                "《她力量》，《明星代言人》首推官资格。",
            ]
        }
        if user_type not in fee_map:
            return Response(
                {'code': 400, 'msg': '用户类型错误（1-蓝朋友，2-蓝明星，3-护肤私教， 4-MINI-studio 主理人，5-TA创+）'},
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

class ExamQuestionViewSet(ReadOnlyModelViewSet):
    queryset = ExamQuestion.objects.all()
    serializer_class = ExamQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

class ExamRecordViewSet(ModelViewSet):
    serializer_class = ExamRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ExamRecord.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        score = serializer.validated_data.get('score', 0)
        serializer.save(user=self.request.user, is_pass=score >= 60)

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
                return Response({'code':400, 'msg':'库存不足'}, status=400)
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
                    "total_price": float(item.num * item.goods.member_price)
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
    # 确保权限验证生效（必须登录才能访问）
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 仅查询当前登录用户的地址（核心：request.user是登录用户）
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
            # 调试：打印当前登录用户（确认不是匿名用户）
            print(f"当前登录用户：{request.user} | 是否匿名：{request.user.is_anonymous}")
            # 强制校验：必须是登录用户
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

                # 核心修复：直接构造数据库可识别的字段，明确赋值user（用对象而非ID）
                address_data = {
                    # 关键：直接传user对象，Django会自动处理user_id赋值
                    'user': request.user,
                    'name': request.data.get('name', '').strip(),
                    'phone': request.data.get('phone', '').strip(),
                    'address': request.data.get('address', '').strip(),
                    'detail': request.data.get('detail', '').strip(),
                    'is_default': is_default
                }

                # 校验必填字段（避免空值）
                if not address_data['name'] or not address_data['phone'] or not address_data['detail']:
                    return Response({
                        "code": 400,
                        "msg": "姓名、手机号、详细地址不能为空",
                        "data": {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                # 跳过序列化器，直接入库（避免序列化器字段映射问题）
                address = Address.objects.create(**address_data)

                return Response({
                    "code": 200,
                    "msg": "添加地址成功",
                    "data": AddressSerializer(address).data
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"添加地址异常：{str(e)}")
            # 明确返回数据库约束错误
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
        except Exception as e:
            return Response({
                "code": 500,
                "msg": f"删除地址失败：{str(e)}",
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
# ===================== 订单视图（修复重复代码版） =====================
class OrderAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = OrderAddSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            logger.error(f"下单参数错误：{ser.errors}")
            return Response({"code": 400, "msg": "参数错误", "data": ser.errors})

        try:
            with transaction.atomic():
                # ========== 配送相关参数处理 ==========
                delivery_type = request.data.get("delivery_type", 1)  # 1=快递上门，2=到店自取
                pick_up_store_id = request.data.get("pick_up_store_id")
                address_id = request.data.get("address_id")

                # 校验配送逻辑
                address = None
                pick_up_store = None
                if delivery_type == 1:  # 快递上门：必须传地址ID
                    if not address_id:
                        return Response({"code": 400, "msg": "快递上门需选择收货地址"})
                    try:
                        address = Address.objects.get(id=address_id, user=request.user)
                    except Address.DoesNotExist:
                        return Response({"code": 404, "msg": "收货地址不存在"}, status=404)
                else:  # 到店自取：必须传门店ID
                    if not pick_up_store_id:
                        return Response({"code": 400, "msg": "到店自取需选择取货门店"})
                    try:
                        pick_up_store = Area.objects.get(id=pick_up_store_id)
                    except Area.DoesNotExist:
                        return Response({"code": 404, "msg": "取货门店不存在"}, status=404)

                # 商品列表校验
                goods_list = request.data.get("goods_list", [])
                if not isinstance(goods_list, list) or len(goods_list) == 0:
                    return Response({"code": 400, "msg": "请选择要购买的商品"})

                # 总价校验
                total_price = request.data.get("total_price", 0)
                try:
                    total_price = float(total_price)
                    if total_price <= 0:
                        return Response({"code": 400, "msg": "订单总价必须大于0"})
                except (ValueError, TypeError):
                    return Response({"code": 400, "msg": "订单总价格式错误"})

                # 创建主订单
                order_sn = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                order = Order.objects.create(
                    user=request.user,
                    order_sn=order_sn,
                    address=address,
                    total_price=total_price,
                    status=0,  # 0=待支付
                    delivery_type=delivery_type,
                    pick_up_store=pick_up_store
                )
                logger.info(f"创建新订单：order_id={order.id}, order_sn={order_sn}, 配送方式={order.get_delivery_type_display()}")

                # 创建订单明细 + 关联购物车
                goods_names = []
                total_count = 0
                for item in goods_list:
                    cart_id = item.get("cart_id")
                    num = item.get("num", 1)

                    if not cart_id or not isinstance(num, int) or num < 1:
                        raise Exception(f"购物车参数错误：cart_id={cart_id}, num={num}")

                    try:
                        cart = Cart.objects.get(id=cart_id, user=request.user)
                    except Cart.DoesNotExist:
                        raise Exception(f"购物车商品不存在：cart_id={cart_id}")

                    goods = cart.goods
                    if goods.stock < num:
                        raise Exception(f"商品库存不足：{goods.name}（库存{goods.stock}，需{num}）")

                    # 创建订单明细
                    OrderItem.objects.create(
                        order=order,
                        goods=goods,
                        num=num,
                        price=cart.goods.member_price,
                        goods_name=goods.name,
                        goods_image=goods.image_url,
                        goods_specs=goods.specs,
                        total_price=num * cart.goods.member_price
                    )
                    # 关联购物车到订单（方便后续清空）
                    cart.order = order
                    cart.save()
                    goods_names.append(goods.name)
                    total_count += num

                # 更新订单商品信息
                order.goods_names = "、".join(goods_names)
                order.goods_count = total_count
                order.save()

            # 返回订单信息（供前端跳转支付页）
            return Response({
                "code": 200,
                "msg": "下单成功，请支付",
                "data": {
                    "order_id": order.id,
                    "order_sn": order.order_sn,
                    "total_price": total_price,
                    "delivery_type": delivery_type,
                    "delivery_type_name": order.get_delivery_type_display(),
                    "pick_up_store": {
                        "id": pick_up_store.id if pick_up_store else "",
                        "name": pick_up_store.name if pick_up_store else ""
                    } if delivery_type == 2 else {}
                }
            })

        except Exception as e:
            logger.error(f"下单失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"下单失败: {str(e)}"})


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-create_time')
        data_list = []
        for order in orders:
            # 构造配送信息
            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            # ========== 新增：快递配送时返回收货人信息 ==========
            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": order.address.province or "",
                    "city": order.address.city or "",
                    "district": order.address.district or "",
                    "address": order.address.address or "",
                    "detail": order.address.detail or ""
                }

            data_list.append({
                "order_id": order.id,
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                "status": order.status_display,
                "status_code": order.status,
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M'),
                "goods_names": order.goods_names,
                "goods_count": order.goods_count,
                "delivery_info": delivery_info,
                # ========== 新增：收货人信息字段 ==========
                "receiver_info": receiver_info
            })
        return Response({
            "code": 200,
            "msg": "获取订单列表成功",
            "data": data_list
        })

# app01/views.py 中的 OrderDetailView（示例）
class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        order_sn = request.query_params.get("order_sn")

        if not (order_id or order_sn):
            return Response({"code": 400, "msg": "请传入订单ID或订单编号"}, status=400)

        try:
            # 查询订单
            query_kwargs = {'user': request.user}
            if order_id:
                query_kwargs['id'] = order_id
            else:
                query_kwargs['order_sn'] = order_sn
            order = Order.objects.get(**query_kwargs)

            # 订单商品明细（保持不变）
            order_items = OrderItem.objects.filter(order=order).select_related('goods')
            goods_detail = [
                {
                    "goods_id": item.goods.id,
                    "goods_name": item.goods.name,
                    "goods_image": f"http://localhost:8000/media/{item.goods.image_url}" if item.goods.image_url else "",
                    "num": item.num,
                    "price": str(item.price),
                    "total_price": str(item.num * item.price)
                }
                for item in order_items
            ]

            # 配送/地址信息（重点：补全收货人所有字段）
            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            # 完整的收货人信息（确保字段和序列化器一致）
            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": order.address.province or "",
                    "city": order.address.city or "",
                    "district": order.address.district or "",
                    "address": order.address.detail or "",  # 详细地址
                    "full_address": f"{order.address.province or ''} {order.address.city or ''} {order.address.district or ''} {order.address.detail or ''}".strip()
                }

            # 组装返回数据
            order_detail = {
                "order_id": order.id,
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                "status": order.status_display,
                "status_code": order.status,
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                "delivery_info": delivery_info,
                "receiver_info": receiver_info,  # 完整的收货人信息
                "goods_detail": goods_detail,
                "goods_count": order.goods_count
            }

            return Response({
                "code": 200,
                "msg": "获取订单详情成功",
                "data": order_detail
            })

        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "订单不存在"}, status=404)
        except Exception as e:
            return Response({"code": 500, "msg": f"获取订单详情失败：{str(e)}"})

class OrderPaySuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print("===== 支付回调接口开始执行 =====")
        print(f"请求用户ID：{request.user.id}，会员ID：{request.user.member_id}")
        print(f"用户初始积分：{request.user.points}")

        order_id = request.data.get('order_id')
        order_sn = request.data.get('order_sn')
        pay_method = request.data.get('pay_method', 1)
        pay_no = request.data.get('pay_no', '')
        print(f"前端传参：order_id={order_id}，order_sn={order_sn}，pay_method={pay_method}")

        if not (order_id or order_sn):
            print("错误：未传order_id或order_sn")
            return Response({'code': 400, 'msg': '请传入订单ID或订单编号', 'data': None})

        if order_id:
            try:
                order_id = int(order_id)
            except ValueError:
                print(f"错误：order_id格式错误，值为{order_id}")
                return Response({'code': 400, 'msg': '订单ID必须是数字', 'data': None})

        try:
            query_kwargs = {'user': request.user, 'is_delete': False}
            if order_id:
                query_kwargs['id'] = order_id
            else:
                query_kwargs['order_sn'] = order_sn

            order = Order.objects.get(**query_kwargs)
            print(f"查询到订单：ID={order.id}，金额={order.total_price}，当前状态={order.status}")

            # ===== 核心修改：已支付订单也检查并补送积分 =====
            give_points = 0
            msg = ""
            pay_amount = float(order.total_price)
            give_points_calc = int(pay_amount * 10)  # 应赠送的积分

            # 检查该订单是否已赠送过积分
            has_given = PointsRecord.objects.filter(
                user=request.user,
                points_type=2,  # 2=消费赠送
                related_id=order.order_sn
            ).exists()

            if order.status in [1, 2, 3]:
                print(f"订单已支付，检查积分是否已赠送：{has_given}")
                # 已支付但未赠送积分 → 补送
                if give_points_calc > 0 and not has_given:
                    print(f"补送积分：{give_points_calc}分")
                    success, msg = request.user.add_points(
                        points=give_points_calc,
                        points_type=2,
                        related_id=order.order_sn,
                        related_desc=f'补送-消费{pay_amount:.2f}元，按1元10分赠送{give_points_calc}积分'
                    )
                    request.user.refresh_from_db()
                    give_points = give_points_calc if success else 0
                    if not success:
                        print(f"补送积分失败：{msg}")
                else:
                    if has_given:
                        msg = "积分已赠送过，无需重复赠送"
                    else:
                        msg = f"消费{pay_amount:.2f}元不足1元，暂不赠送积分"
                print(f"订单已支付处理完成，用户当前积分：{request.user.points}")
                return Response({
                    'code': 200,
                    'msg': '订单已支付' + ('，积分补送成功' if give_points > 0 else f'，{msg}'),
                    'data': {'order_sn': order.order_sn, 'current_points': request.user.points,
                             'give_points': give_points}
                })

            # 未支付订单：正常更新状态+赠送积分
            with transaction.atomic():
                order.status = 1
                order.pay_method = pay_method
                order.pay_no = pay_no
                order.pay_time = datetime.datetime.now()
                order.save(update_fields=['status', 'pay_method', 'pay_no', 'pay_time'])
                print(f"订单状态已更新为待发货（1）")

                if give_points_calc > 0 and not has_given:
                    print(f"调用add_points前，用户积分：{request.user.points}")
                    success, msg = request.user.add_points(
                        points=give_points_calc,
                        points_type=2,
                        related_id=order.order_sn,
                        related_desc=f'消费{pay_amount:.2f}元，按1元10分赠送{give_points_calc}积分'
                    )
                    request.user.refresh_from_db()
                    give_points = give_points_calc if success else 0
                    print(f"add_points返回：success={success}，msg={msg}")
                    print(f"调用add_points后，用户积分：{request.user.points}")
                    if not success:
                        raise Exception(f'积分赠送失败：{msg}')
                else:
                    msg = f'消费{pay_amount:.2f}元不足1元，暂不赠送积分' if give_points_calc == 0 else "积分已赠送过"
                    print(msg)

            print(f"支付回调完成，用户最终积分：{request.user.points}")
            return Response({
                'code': 200,
                'msg': '订单支付成功' + ('，积分赠送成功' if give_points > 0 else f'，{msg}'),
                'data': {
                    'order_sn': order.order_sn,
                    'pay_amount': pay_amount,
                    'give_points': give_points,
                    'current_points': request.user.points,
                    'msg': msg
                }
            })

        except Order.DoesNotExist:
            print(f"错误：订单不存在（order_id={order_id}，order_sn={order_sn}）")
            return Response({'code': 404, 'msg': '订单不存在', 'data': None}, status=404)
        except Exception as e:
            print(f"支付回调异常：{str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'code': 500, 'msg': f'支付成功，积分处理失败：{str(e)[:30]}', 'data': None}, status=500)
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
    """注册送积分手动接口（供前端异步调用，防止自动触发漏送）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # 校验手机号（可选，防止恶意调用）
        if request.data.get('phone') and user.phone != request.data.get('phone'):
            return Response({'code':403, 'msg':'手机号与登录会员不一致', 'data':None})
        # 调用通用加积分方法
        success, msg = user.add_points(
            points=0,
            points_type=1,
            related_desc='前端手动触发-新用户注册积分'
        )
        return Response({
            'code':200 if success else 400,
            'msg':msg,
            'data':{'current_points': user.points}
        })

from .models import PointsRecord
from .serializer import PointsRecordSerializer

class PointsRecordView(APIView):
    """积分明细查询接口：返回当前用户的所有积分变动记录+当前余额"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # 可选：前端按积分类型过滤（如只看消费送的积分，传type=2）
        points_type = request.query_params.get('type', '')
        # 基础查询：当前用户的所有积分记录
        queryset = PointsRecord.objects.filter(user=user)
        # 类型过滤
        if points_type and points_type.isdigit():
            queryset = queryset.filter(points_type=int(points_type))
        # 序列化
        serializer = PointsRecordSerializer(queryset, many=True)
        # 返回结果（包含当前余额+记录列表）
        return Response({
            'code':200,
            'msg':'获取积分明细成功',
            'data':{
                'current_points': user.points,  # 积分余额
                'record_list': serializer.data  # 积分变动记录
            }
        })

# ===================== 门店相关接口 =====================
class AreaListView(APIView):
    """获取所有门店列表（供到店自取选择）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 查询所有有效门店（可根据业务添加过滤条件，如is_delete）
            area_list = Area.objects.all()
            # 构造前端需要的格式
            data = [
                {
                    "id": area.id,
                    "name": area.name,  # 门店全名
                    "desc": area.desc,  # 门店简称
                    # 可补充地址/电话等字段（如果Area模型有）
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


import requests
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt


# 极简视频代理：绕开锚点篡改（无需查数据库）
@csrf_exempt
def video_proxy(request):
    # 获取前端传的原始视频URL
    video_url = request.GET.get('url', '')
    if not video_url or not video_url.startswith('http://localhost:8000/media/'):
        return StreamingHttpResponse('无效URL', status=400)

    try:
        # 转发请求到原始视频URL，流式返回（避免文件读取）
        response = requests.get(video_url, stream=True)
        # 构建流式响应，返回视频内容
        streaming_response = StreamingHttpResponse(
            response.iter_content(chunk_size=1024 * 1024),
            status=response.status_code
        )
        streaming_response['Content-Type'] = 'video/mp4'
        return streaming_response
    except Exception as e:
        return StreamingHttpResponse(f'代理失败：{str(e)}', status=500)

# 1. 领取优惠券接口
def claim_coupon(request):
    coupon_id = request.POST.get('id')
    # 计算3个月后的过期时间
    expire_at = timezone.now() + timedelta(days=90)

    UserCoupon.objects.create(
        user=request.user,
        coupon_id=coupon_id,
        end_time=expire_at
    )
    return JsonResponse({"status": True, "msg": "领取成功，有效期90天"})


# 2. 个人中心数据接口 (供 mine.js 调用)
# 对应 path('user/stats/')
def get_user_stats(request):
    # 打印原始请求头
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    print(f"--- 原始 Authorization 头内容: {auth_header} ---")
    # 1. 检查用户是否真实登录
    if not request.user.is_authenticated:
        print("警告：收到一个匿名请求，可能是 Token 已失效")
        return JsonResponse({
            "code": 401,
            "msg": "身份认证失败，请重新登录",
            "couponCount": 0
        })

    # 2. 只有是真实用户，才执行数据库查询
    count = UserCoupon.objects.filter(user=request.user).count()
    print(f"用户 {request.user.username} 的优惠券数量: {count}")

    return JsonResponse({
        "code": 200,
        "couponCount": count
    })


# 对应 path('user/coupons/')
def get_user_coupons(request):
    # 获取用户所有的券（按时间倒序排，最新的在前面）
    queryset = UserCoupon.objects.filter(user=request.user).order_by('-add_time')
    # 序列化并返回...


class UserStatsView(APIView):
    # 这一行是关键！它会阻止 AnonymousUser 进入 get 方法
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 只要代码能走到这里，request.user 就一定是个真实用户对象
        user_count = UserCoupon.objects.filter(user=request.user).count()
        return Response({
            "code": 200,
            "couponCount": user_count
        })

class UserCouponView(APIView):
    """用户优惠券列表/统计接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取用户优惠券列表
        参数：
        - only_valid: 是否仅返回可用优惠券（true/false）
        - type: 筛选类型（1=代金券，2=折扣券）
        """
        try:
            # 获取筛选参数
            only_valid = request.query_params.get('only_valid', 'false').lower() == 'true'
            coupon_type = request.query_params.get('type')
            coupon_type = int(coupon_type) if coupon_type and coupon_type.isdigit() else None

            # 查询优惠券
            coupons = request.user.get_coupons(only_valid=only_valid, coupon_type=coupon_type)
            serializer = UserCouponSerializer(coupons, many=True)

            # 获取统计数据
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
    """使用优惠券接口（下单时调用）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        使用优惠券
        参数：
        - coupon_id: 优惠券ID
        - order_sn: 关联订单号
        """
        coupon_id = request.data.get('coupon_id')
        order_sn = request.data.get('order_sn')

        if not coupon_id or not order_sn:
            return Response({
                'code': 400,
                'msg': '优惠券ID和订单号不能为空',
                'data': None
            })

        try:
            # 查询用户可用的优惠券
            coupon = UserCoupon.objects.get(
                id=coupon_id,
                user=request.user,
                is_used=False,
                end_time__gt=timezone.now()
            )

            # 标记为已使用
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
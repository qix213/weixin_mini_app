
# 视图文件 - 修复logger未定义 + 冗余代码 + 语法错误

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
import datetime
import random
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
                    end_time=timezone.now() + timedelta(days=coupon.valid_days)
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


# ===================== 订单视图（新增积分支付逻辑） =====================
# 补充必要的导入（务必确保导入完整）
import random
from decimal import Decimal  # 金额精度处理
from .serializer import OrderAddSerializer

class OrderAddView(APIView):
    """创建订单视图（含积分抵扣）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. 序列化器参数校验
        ser = OrderAddSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            logger.error(f"下单参数错误：{ser.errors}")
            return Response({"code": 400, "msg": "参数错误", "data": ser.errors})

        try:
            # 开启数据库事务：要么全部成功，要么全部回滚
            with transaction.atomic():
                # ========== 2. 基础参数提取（配送+积分） ==========
                # 配送类型（默认1=快递上门）
                delivery_type = int(request.data.get("delivery_type", 1))
                # 自提门店ID/快递地址ID
                pick_up_store_id = request.data.get("pick_up_store_id")
                address_id = request.data.get("address_id")
                # 积分抵扣参数（默认0=不抵扣）
                deduct_point = int(request.data.get("deduct_point", 0))

                # ========== 3. 配送逻辑校验 ==========
                address = None
                pick_up_store = None
                if delivery_type == 1:  # 快递上门
                    if not address_id:
                        return Response({"code": 400, "msg": "快递上门需选择收货地址"})
                    # 校验地址归属当前用户
                    address = get_object_or_404(Address, id=address_id, user=request.user)
                else:  # 到店自取
                    if not pick_up_store_id:
                        return Response({"code": 400, "msg": "到店自取需选择取货门店"})
                    pick_up_store = get_object_or_404(Area, id=pick_up_store_id)

                # ========== 4. 商品列表校验（核心） ==========
                goods_list = request.data.get("goods_list", [])
                # 校验商品列表格式
                if not isinstance(goods_list, list) or len(goods_list) == 0:
                    return Response({"code": 400, "msg": "请选择要购买的商品"})

                # 初始化变量
                total_money = Decimal('0.00')  # 订单总价（改用Decimal保证精度）
                invalid_goods = []  # 不支持积分抵扣的商品
                cart_ids = []       # 购物车ID列表
                goods_items = []    # 商品信息列表（用于后续创建订单项）

                for item in goods_list:
                    cart_id = item.get("cart_id")
                    num = int(item.get("num", 1))  # 确保数量是整数

                    # 基础参数校验
                    if not cart_id or num < 1:
                        raise Exception(f"购物车参数错误：cart_id={cart_id}, num={num}")

                    # 校验购物车归属当前用户
                    cart = get_object_or_404(Cart, id=cart_id, user=request.user)
                    goods = cart.goods
                    cart_ids.append(cart_id)

                    # 库存校验（核心：防止超卖）
                    if goods.stock < num:
                        raise Exception(f"商品库存不足：{goods.name}（库存{goods.stock}，需{num}）")

                    # 积分抵扣时，校验商品是否支持积分兑换
                    if deduct_point > 0 and not goods.can_point_exchange:
                        invalid_goods.append(goods.name)

                    # 累加订单总价（Decimal乘法，避免浮点精度问题）
                    goods_price = Decimal(str(goods.member_price))  # 转为Decimal
                    total_money += goods_price * num

                    # 暂存商品信息（避免重复查询）
                    goods_items.append({
                        "cart": cart,
                        "goods": goods,
                        "num": num,
                        "price": goods_price
                    })

                # 有不支持积分抵扣的商品 → 终止下单
                if invalid_goods:
                    raise Exception(f"以下商品不支持积分抵扣：{','.join(invalid_goods)}")

                # ========== 5. 积分抵扣计算与校验 ==========
                actual_deduct_point = 0  # 实际抵扣积分
                deduct_money = Decimal('0.00')  # 积分抵扣金额（Decimal）
                actual_pay_money = total_money  # 实际支付金额

                if deduct_point > 0:
                    user = request.user
                    # 最大可抵扣积分 = 订单总价(元) * 100（1分=0.01元）
                    max_deduct_point = int(total_money * 100)
                    # 实际抵扣积分 = 取最小值（用户要抵扣的、用户拥有的、最大可抵扣的）
                    actual_deduct_point = min(deduct_point, max_deduct_point, user.points or 0)

                    # 积分不足校验
                    if actual_deduct_point < deduct_point:
                        raise Exception(f"积分不足：当前{user.points}分，需{deduct_point}分（最多可抵扣{max_deduct_point}分）")

                    # 计算抵扣金额（1分=0.01元）
                    deduct_money = Decimal(str(actual_deduct_point * 0.01))
                    # 实际支付金额（确保≥0）
                    actual_pay_money = max(total_money - deduct_money, Decimal('0.00'))

                # ========== 6. 创建订单主表（对齐Order模型字段） ==========
                # 生成唯一订单编号（时间戳+随机数）
                order_sn = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                # 创建订单（字段名对齐Order模型：actual_pay_money而非actual_pay_price）
                order = Order.objects.create(
                    user=request.user,
                    order_sn=order_sn,
                    address=address,
                    total_price=total_money,
                    actual_pay_money=actual_pay_money,  # 对齐模型字段
                    point_deduct=actual_deduct_point,
                    point_deduct_money=deduct_money,    # 对齐模型字段
                    status=0,  # 0=待付款
                    delivery_type=delivery_type,
                    pick_up_store=pick_up_store
                )
                logger.info(f"创建新订单：order_id={order.id}, 订单号={order_sn}, 积分抵扣{actual_deduct_point}分（{deduct_money}元）")

                # ========== 7. 创建订单项 + 关联购物车 + 扣减库存 ==========
                goods_names = []  # 订单商品名称拼接
                total_count = 0   # 订单商品总数

                for item in goods_items:
                    cart = item["cart"]
                    goods = item["goods"]
                    num = item["num"]
                    price = item["price"]

                    # 创建订单项
                    OrderItem.objects.create(
                        order=order,
                        goods=goods,
                        num=num,
                        price=price,
                        goods_name=goods.name,
                        goods_image=goods.image_url,
                        goods_specs=goods.specs if hasattr(goods, 'specs') else "",  # 兼容无specs字段
                        total_price=price * num
                    )

                    # 购物车关联订单（标记为已下单）
                    cart.order = order
                    cart.save(update_fields=["order"])

                    # 扣减商品库存（核心：防止重复下单超卖）
                    goods.stock -= num
                    goods.save(update_fields=["stock"])

                    # 累加商品名称和数量
                    goods_names.append(goods.name)
                    total_count += num

                # 更新订单的商品名称和总数
                order.goods_names = "、".join(goods_names)
                order.goods_count = total_count
                order.save(update_fields=["goods_names", "goods_count"])
                # ========== 8. 扣减用户积分（仅当有抵扣时） ==========
                # if actual_deduct_point > 0:
                #     # 调用用户模型的add_points方法（现在支持负数扣减）
                #     success, msg = request.user.add_points(
                #         points=-actual_deduct_point,  # 负数=扣减，现在方法已支持
                #         points_type=4,  # 4=订单积分抵扣
                #         related_id=order.order_sn,
                #         related_desc=f"订单{order_sn}抵扣{actual_deduct_point}积分（抵扣{deduct_money}元）"
                #     )
                #     if not success:
                #         # 抛出异常，事务回滚，确保订单不会创建成功
                #         raise Exception(f"积分扣减失败：{msg}")
                #     logger.info(f"订单{order_sn}扣减积分{actual_deduct_point}分成功，用户剩余积分：{request.user.points}")

            # ========== 9. 返回订单信息（字段名对齐） ==========
            response_data = {
                "code": 200,
                "msg": "下单成功，请支付",
                "data": {
                    "order_id": order.id,
                    "order_sn": order.order_sn,
                    "total_price": float(total_money),  # 转float供前端处理
                    "actual_pay_money": float(actual_pay_money),  # 对齐模型字段
                    "point_deduct": actual_deduct_point,
                    "point_deduct_money": float(deduct_money),
                    "delivery_type": delivery_type,
                    "delivery_type_name": order.get_delivery_type_display(),
                }
            }

            # 自提订单补充门店信息
            if delivery_type == 2 and pick_up_store:
                response_data["data"]["pick_up_store"] = {
                    "id": pick_up_store.id,
                    "name": pick_up_store.name
                }

            return Response(response_data)

        # ========== 10. 异常处理 ==========
        except Exception as e:
            error_msg = str(e)[:100]  # 截断过长的错误信息
            logger.error(f"下单失败：{error_msg}", exc_info=True)
            return Response({"code": 500, "msg": f"下单失败: {error_msg}"})

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-create_time')
        data_list = []
        for order in orders:
            # 配送信息（保留）
            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            # 收货人信息（保留）
            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": order.address.province or "",
                    "city": order.address.city or "",
                    "district": order.address.district or "",
                    "address": order.address.detail or "",
                    "full_address": f"{order.address.province or ''} {order.address.city or ''} {order.address.district or ''} {order.address.detail or ''}".strip()
                }

            # ========== 修复：字段名从actual_pay_price改为actual_pay_money ==========
            point_summary = {
                "point_deduct": order.point_deduct or 0,
                "point_deduct_money": round(float(order.point_deduct_money or 0.0), 2),
                # 修复核心错误：使用正确的字段名actual_pay_money
                "actual_pay_price": round(float(order.actual_pay_money or order.total_price), 2)
            }

            data_list.append({
                "order_id": order.id,
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                # 同步修复这里的字段名
                "actual_pay_price": str(order.actual_pay_money or order.total_price),
                "status": order.status_display,
                "status_code": order.status,
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M'),
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

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        order_sn = request.query_params.get("order_sn")

        if not (order_id or order_sn):
            return Response({"code": 400, "msg": "请传入订单ID或订单编号"}, status=400)

        try:
            # 查询订单（保留）
            query_kwargs = {'user': request.user}
            if order_id:
                query_kwargs['id'] = order_id
            else:
                query_kwargs['order_sn'] = order_sn
            order = Order.objects.get(**query_kwargs)

            # 订单商品明细（保留）
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

            # 配送/地址信息（保留）
            delivery_info = {
                "delivery_type": order.delivery_type,
                "delivery_type_name": order.get_delivery_type_display(),
                "pick_up_store": {
                    "id": order.pick_up_store.id if order.pick_up_store else "",
                    "name": order.pick_up_store.name if order.pick_up_store else ""
                } if order.delivery_type == 2 else {}
            }

            # 收货人信息（保留）
            receiver_info = {}
            if order.delivery_type == 1 and order.address:
                receiver_info = {
                    "name": order.address.name,
                    "phone": order.address.phone,
                    "province": order.address.province or "",
                    "city": order.address.city or "",
                    "district": order.address.district or "",
                    "address": order.address.detail or "",
                    "full_address": f"{order.address.province or ''} {order.address.city or ''} {order.address.district or ''} {order.address.detail or ''}".strip()
                }

            # ========== 修复：字段名从actual_pay_price改为actual_pay_money ==========
            point_info = {
                "point_deduct": order.point_deduct or 0,
                "point_deduct_money": float(order.point_deduct_money or 0.0),
                "total_price": float(order.total_price),
                # 修复核心错误：使用正确的字段名actual_pay_money
                "actual_pay_price": float(order.actual_pay_money or order.total_price)
            }

            # 组装返回数据（同步修复actual_pay_price字段）
            order_detail = {
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
                "point_info": point_info,
                "goods_detail": goods_detail
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
            print(
                f"查询到订单：ID={order.id}，金额={order.total_price}，实付={order.actual_pay_money}，积分抵扣={order.point_deduct}，当前状态={order.status}")

            # ===== 新增：支付成功后扣减积分抵扣的积分 =====
            deduct_point = order.point_deduct or 0  # 获取订单记录的抵扣积分数量
            if deduct_point > 0 and not PointsRecord.objects.filter(
                    user=request.user,
                    points_type=4,  # 4=订单积分抵扣
                    related_id=order.order_sn
            ).exists():
                # 扣减积分
                success, msg = request.user.add_points(
                    points=-deduct_point,
                    points_type=4,
                    related_id=order.order_sn,
                    related_desc=f"订单{order.order_sn}支付成功，抵扣{deduct_point}积分"
                )
                if success:
                    print(f"订单{order.order_sn}扣减抵扣积分{deduct_point}分成功")
                    request.user.refresh_from_db()
                else:
                    print(f"订单{order.order_sn}扣减抵扣积分失败：{msg}")
                    raise Exception(f"积分抵扣扣减失败：{msg}")

            # ===== 修复核心：消费赠送积分逻辑（区分积分兑换商品） =====
            give_points = 0
            msg = ""

            # 1. 关键修改：计算基数改为【实付金额】而非订单总额
            pay_amount = float(order.actual_pay_money or 0)

            # 2. 新增：判断是否为积分兑换商品订单（两种判断方式，选其一即可）
            # 方式1：通过订单是否有积分抵扣判断
            is_point_exchange_order = order.point_deduct > 0
            # 方式2：通过订单商品是否支持积分兑换判断（更精准）
            # order_items = OrderItem.objects.filter(order=order)
            # is_point_exchange_order = any(item.goods.can_point_exchange for item in order_items if item.goods)

            print(f"积分兑换订单判断：{is_point_exchange_order}，实付金额：{pay_amount}")

            # 3. 仅当非积分兑换订单 或 实付金额>0 时，才计算赠送积分
            if is_point_exchange_order:
                if pay_amount <= 0:
                    # 全额积分兑换，不赠送积分
                    msg = "全额积分兑换商品，不赠送消费积分"
                    print(msg)
                else:
                    # 部分积分抵扣，按实付金额计算赠送积分
                    give_points_calc = int(pay_amount * 10)
                    msg = f"积分抵扣订单，按实付金额{pay_amount:.2f}元计算赠送积分"
            else:
                # 普通订单，按实付金额计算（原逻辑兼容）
                give_points_calc = int(pay_amount * 10)
                msg = f"普通订单，按实付金额{pay_amount:.2f}元计算赠送积分"

            # 检查该订单是否已赠送过积分
            has_given = PointsRecord.objects.filter(
                user=request.user,
                points_type=2,  # 2=消费赠送
                related_id=order.order_sn
            ).exists()

            if order.status in [1, 2, 3]:
                print(f"订单已支付，检查积分是否已赠送：{has_given}")
                # 已支付但未赠送积分 → 补送（仅当有可赠送积分时）
                if give_points_calc > 0 and not has_given:
                    print(f"补送积分：{give_points_calc}分")
                    success, msg = request.user.add_points(
                        points=give_points_calc,
                        points_type=2,
                        related_id=order.order_sn,
                        related_desc=f'补送-{msg}，赠送{give_points_calc}积分'
                    )
                    request.user.refresh_from_db()
                    give_points = give_points_calc if success else 0
                    if not success:
                        print(f"补送积分失败：{msg}")
                else:
                    if has_given:
                        msg = "积分已赠送过，无需重复赠送"
                    elif give_points_calc <= 0:
                        msg = f"{msg}（可赠送积分数为0）"
                    print(msg)
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
                order.pay_time = timezone.now()
                order.save(update_fields=['status', 'pay_method', 'pay_no', 'pay_time'])
                print(f"订单状态已更新为待发货（1）")

                # 仅当有可赠送积分且未赠送过时，才赠送
                if give_points_calc > 0 and not has_given:
                    print(f"调用add_points前，用户积分：{request.user.points}")
                    success, msg = request.user.add_points(
                        points=give_points_calc,
                        points_type=2,
                        related_id=order.order_sn,
                        related_desc=f'{msg}，赠送{give_points_calc}积分'
                    )
                    request.user.refresh_from_db()
                    give_points = give_points_calc if success else 0
                    print(f"add_points返回：success={success}，msg={msg}")
                    print(f"调用add_points后，用户积分：{request.user.points}")
                    if not success:
                        raise Exception(f'积分赠送失败：{msg}')
                else:
                    if has_given:
                        msg = "积分已赠送过，无需重复赠送"
                    elif give_points_calc <= 0:
                        msg = f"{msg}（可赠送积分数为0）"
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


from django.http import StreamingHttpResponse

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


import hashlib
import base64
import uuid
import time
import json
import requests
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import datetime
from django.utils import timezone
from collections import defaultdict
from .forms import ExpressCreateForm
from .models import Order, ExpressLogistics, SF_STATUS_MAP, STATUS_NAME_MAP

# --- 顺丰接口配置 ---
PARTNER_ID = "LSQJS1HHHWZW"
CHECK_WORD = "zfIRMBfdRKaZiJfOea1vm40V7utd9x2z"
URL = "https://sfapi-sbox.sf-express.com/std/service"


def query_sf_routes(logistics_no_list):
    """调用顺丰接口查询物流轨迹"""
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

    # 生成签名
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
    """解析顺丰接口数据 + 去重"""
    try:
        outer_data = json.loads(raw_json_str)
        if outer_data.get("apiResultCode") != "A1000":
            raise Exception(f"接口返回错误：{outer_data.get('apiErrorMsg', '未知错误')}")

        inner_data = json.loads(outer_data["apiResultData"])
        if not inner_data.get("success"):
            raise Exception(f"物流查询失败：{inner_data.get('errorMsg', '未知错误')}")

        phone_pattern = re.compile(r'1[3-9]\d{9}')
        name_pattern = re.compile(r'【([^，\s]+)，(联系电话|电话)：')

        temp_result = []  # 原始轨迹列表
        route_resps = inner_data["msgData"]["routeResps"]

        for resp in route_resps:
            mail_no = resp["mailNo"]
            for route in resp["routes"]:
                accept_time = route["acceptTime"]
                accept_address = route["acceptAddress"]
                status_name = route['firstStatusName']
                remark = route["remark"]

                # 转换时间格式
                try:
                    logistics_time = datetime.strptime(accept_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logistics_time = timezone.now()

                # 状态编码映射
                status_code = SF_STATUS_MAP.get(status_name, 601)

                # 提取派件人/电话
                phone = phone_pattern.search(remark).group() if phone_pattern.search(remark) else None
                contact = name_pattern.search(remark).group(1) if name_pattern.search(remark) else None

                # 暂存所有原始轨迹
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

        # 去重逻辑：按运单号+状态编码分组，保留最新时间条目
        unique_groups = defaultdict(dict)
        for item in temp_result:
            group_key = (item["运单号"], item["物流状态编码"])
            if not unique_groups[group_key] or item["时间"] > unique_groups[group_key]["时间"]:
                unique_groups[group_key] = item

        # 去重后按时间正序排序
        final_result = sorted(unique_groups.values(), key=lambda x: x["时间"])

        # 给去重后的轨迹添加排序值
        for idx, item in enumerate(final_result):
            item["排序"] = idx

        # 返回去重后的轨迹列表 + 原始轨迹数量（仅内部使用，不展示）
        return final_result, len(temp_result)

    except Exception as e:
        raise Exception(f"数据解析/去重失败：{str(e)}")


def express_create(request):
    """新建运单（移除轨迹数量提示）"""
    if request.method == "POST":
        form = ExpressCreateForm(request.POST)
        if form.is_valid():
            order = form.cleaned_data["order"]
            logistics_no_list = form.cleaned_data["logistics_no"]
            logistics_company = form.cleaned_data["logistics_company"]

            try:
                # 1. 调用顺丰接口
                raw_data = query_sf_routes(logistics_no_list)
                # 2. 解析+去重物流轨迹
                logistics_info_list, raw_count = extract_sf_logistics_info(raw_data)

                # 批量删除旧轨迹
                if logistics_info_list:
                    current_logistics_nos = [info["运单号"] for info in logistics_info_list]
                    ExpressLogistics.objects.filter(
                        order=order,
                        logistics_no__in=current_logistics_nos
                    ).delete()

                # 3. 保存去重后的轨迹
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

                # 4. 更新订单物流信息
                if logistics_no_list:
                    order.logistics_no = logistics_no_list[0]
                    order.logistics_company = logistics_company
                    order.save(update_fields=["logistics_no", "logistics_company"])

                # ========== 核心修改：仅保留简洁的成功提示 ==========
                messages.success(request, "运单创建成功！")
                return redirect("express_list")

            except Exception as e:
                messages.error(request, f"操作失败：{str(e)}")
    else:
        form = ExpressCreateForm()

    return render(request, "app01/express_create.html", {"form": form})


from .models import ExpressLogistics

def express_list(request):
    """
    物流列表接口：
    - 网页端访问 → 返回 HTML 页面
    - 小程序请求（带format=json）→ 返回 JSON 数据
    """
    # 1. 接收参数（支持通过URL参数强制指定返回格式）
    return_format = request.GET.get('format', '')  # json/html，为空则自动判断
    order_sns_str = request.GET.get('order_sns', '')

    # 2. 查询物流数据（共用查询逻辑）
    # 核心修改：先查询所有未删除的数据
    logistics_list = ExpressLogistics.objects.filter(
        is_delete=False
    ).select_related('order').order_by("-order__create_time", "-logistics_time")

    # 核心修改：如果前端传了 order_sns 参数，才进行 __in 筛选，否则展示全部
    if order_sns_str:
        order_sns = order_sns_str.split(',')
        logistics_list = logistics_list.filter(order_sn__in=order_sns)

    # 3. 判断返回格式（优先级：URL参数 > 请求头）
    # 3.1 强制指定JSON格式（小程序用）
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

    # 3.2 自动判断（浏览器请求→HTML，JSON请求头→JSON）
    accept_header = request.META.get('HTTP_ACCEPT', '')
    if 'application/json' in accept_header:
        # 适配小程序默认的JSON请求头
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

    # 3.3 默认返回HTML页面
    context = {
        'logistics_list': logistics_list,
        'order_sns': order_sns_str
    }
    return render(request, 'app01/express_list.html', context)

# ===================== 积分抵扣计算接口 =====================
class PointExchangeCalculateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        积分抵扣计算接口（下单前调用）
        请求参数：
        {
            "goods_list": [
                {"cart_id": 1, "num": 2},  # 购物车ID + 购买数量
                {"cart_id": 3, "num": 1}
            ],
            "deduct_point": 2000  # 前端期望抵扣的积分数量
        }
        """
        try:
            # 1. 解析参数
            goods_list = request.data.get("goods_list", [])
            deduct_point = int(request.data.get("deduct_point", 0))
            user = request.user

            # 2. 校验参数
            if not goods_list:
                return Response({"code": 400, "msg": "请选择商品"}, status=400)
            if deduct_point < 0:
                return Response({"code": 400, "msg": "抵扣积分不能为负数"}, status=400)

            # 3. 校验商品是否支持积分兑换 + 计算订单总价
            total_money = 0.0  # 订单总金额（会员价）
            invalid_goods = []  # 不支持积分兑换的商品
            cart_items = []  # 合法的购物车商品

            for item in goods_list:
                cart_id = item.get("cart_id")
                num = int(item.get("num", 1))

                if not cart_id or num < 1:
                    return Response({"code": 400, "msg": f"购物车参数错误：cart_id={cart_id}"}, status=400)

                # 获取购物车商品
                cart = get_object_or_404(Cart, id=cart_id, user=user)
                goods = cart.goods

                # 核心校验：商品是否属于积分兑换分类
                if not goods.can_point_exchange:
                    invalid_goods.append(goods.name)
                    continue

                # 累加订单总价
                total_money += float(goods.member_price * num)
                cart_items.append({
                    "cart": cart,
                    "num": num,
                    "goods": goods
                })

            # 4. 校验是否有不支持积分兑换的商品
            if invalid_goods:
                return Response({
                    "code": 403,
                    "msg": f"以下商品不支持积分兑换：{','.join(invalid_goods)}",
                    "data": {"invalid_goods": invalid_goods}
                }, status=403)

            # 5. 积分抵扣计算（1积分=0.01元）
            max_deduct_point = int(total_money * 100)  # 最多可抵扣积分（订单总价×100）
            actual_deduct_point = min(deduct_point, max_deduct_point, user.points)
            deduct_money = actual_deduct_point * 0.01  # 抵扣的金额
            actual_pay_money = max(total_money - deduct_money, 0)  # 实际需支付金额

            # 6. 返回计算结果
            return Response({
                "code": 200,
                "msg": "积分抵扣计算成功",
                "data": {
                    "total_money": round(total_money, 2),  # 订单总价
                    "request_deduct_point": deduct_point,  # 前端请求抵扣积分
                    "max_deduct_point": max_deduct_point,  # 最大可抵扣积分
                    "actual_deduct_point": actual_deduct_point,  # 实际抵扣积分
                    "deduct_money": round(deduct_money, 2),  # 抵扣金额
                    "actual_pay_money": round(actual_pay_money, 2),  # 实际支付金额
                    "user_current_points": user.points,  # 用户当前积分
                    "points_shortage": max(deduct_point - user.points, 0)  # 积分缺口
                }
            })

        except Exception as e:
            logger.error(f"积分抵扣计算失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"计算失败：{str(e)}"}, status=500)

class UserPointsView(APIView):
    """用户积分查询接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "code": 200,
            "msg": "success",
            "data": {
                "points": request.user.points or 0  # 返回当前用户积分
            }
        })

# app01/views.py
class DeductPointsView(APIView):
    """积分扣减接口（支付成功后调用）"""
    def post(self, request):
        try:
            # 1. 获取参数
            order_id = request.data.get('order_id')
            deduct_point = int(request.data.get('deduct_point', 0))
            user = request.user

            # 2. 校验参数
            if not order_id:
                return Response({"code": 400, "msg": "订单ID不能为空"})
            if deduct_point < 0:
                return Response({"code": 400, "msg": "抵扣积分不能为负数"})

            # 3. 获取订单并校验
            try:
                order = Order.objects.get(id=order_id, user=user, is_delete=False)
            except Order.DoesNotExist:
                return Response({"code": 404, "msg": "订单不存在"})

            # 4. 校验订单状态（必须是已支付：待发货/待收货/已完成）
            if order.status not in [1, 2, 3]:
                return Response({"code": 400, "msg": f"订单状态异常（当前：{order.get_status_display()}），仅已支付订单可扣减积分"})

            # 5. 获取订单商品列表（用于校验积分商品）
            order_items = order.items.all()
            goods_list = [item.goods for item in order_items if item.goods]

            # 6. 执行积分扣减
            success, msg = order.deduct_user_points(user, deduct_point, goods_list)

            if success:
                return Response({"code": 200, "msg": msg})
            else:
                return Response({"code": 400, "msg": msg})

        except Exception as e:
            logger.error(f"扣减积分失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"扣减积分失败：{str(e)}"})


# 支付页后端视图（如 PayView）的 get 方法
class PayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        total_all = float(request.query_params.get("totalAll", 0))  # 订单总额
        actual_amount = float(request.query_params.get("actualAmount", 0))  # 实付金额
        deduct_point = int(request.query_params.get("deduct_point", 0))  # 积分抵扣数

        # 校验订单信息
        order = get_object_or_404(Order, id=order_id, user=request.user)
        # 同步订单的抵扣积分（防止前端传递异常）
        if deduct_point > 0 and order.point_deduct == 0:
            order.point_deduct = deduct_point
            order.point_deduct_money = deduct_point * 0.01
            order.actual_pay_money = total_all - order.point_deduct_money
            order.save()

        return Response({
            "code": 200,
            "msg": "success",
            "data": {
                "order_id": order.id,
                "total_all": total_all,  # 订单总额（显示用）
                "actual_amount": actual_amount,  # 实付金额（支付用）
                "deduct_point": deduct_point,  # 积分抵扣数
                "deduct_money": deduct_point * 0.01  # 积分抵扣金额
            }
        })


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import AIChatSession, AIChatMessage, User
from .utils.ai_utils import get_ai_answer


@csrf_exempt
@require_POST
def ai_chat_api(request):
    # 纯文本、无特殊字符、GBK兼容
    print("=" * 50)
    print("INFO: 后端AI接口已调用")
    try:
        data = json.loads(request.body)
        member_id = data.get("user_id")
        question = data.get("question", "").strip()

        if not member_id or not question:
            return JsonResponse({"code": 400, "msg": "参数错误"}, safe=False)

        # 查询用户
        user = User.objects.get(member_id=member_id)
        session, _ = AIChatSession.objects.get_or_create(user=user)

        # 获取AI答案
        answer = get_ai_answer(question)

        # 🔥 核心修复：打印前过滤特殊字符，避免GBK报错
        try:
            print("INFO: AI返回答案成功")
        except:
            pass

        # 保存对话
        AIChatMessage.objects.create(session=session, role="user", content=question)
        AIChatMessage.objects.create(session=session, role="assistant", content=answer)

        return JsonResponse({
            "code": 200,
            "data": {"answer": answer}
        }, safe=False)

    except Exception as e:
        # 打印错误也做兼容处理
        try:
            print(f"ERROR: 接口异常")
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
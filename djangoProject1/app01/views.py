
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

# 第三方库导入
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
    Collection, VideoCourse, StudyCheckIn, ExamQuestion, ExamRecord, Certification,
    Cart, Recipient, Address, Order, OrderItem
)
from .serializer import (
    BannerSerializer, NoticeSerializer, IndexSerializer, CollectionSerializer,
    CategorySerializer, GoodsSerializer, VideoCourseSerializer,
    BenefitSerializer, UserProfileSerializer, StudyCheckInSerializer, ExamQuestionSerializer,
    ExamRecordSerializer, CertificationSerializer, RegisterSerializer, MemberInfoSerializer,
    SubConsumeRecordSerializer, CartSerializer, CartAddSerializer, RecipientSerializer,
    AddressSerializer, OrderAddSerializer
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

class CollevtionView(ListModelMixin, GenericViewSet):
    queryset = Collection.objects.all().filter(create_time__gte=datetime.datetime.now().date())
    serializer_class = CollectionSerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        today_count = len(self.get_queryset())
        return Response({'code':100, 'msg':'成功','result':res.data, 'today_count':today_count})

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
        """校验当前用户是否有权限观看该视频"""
        video = self.get_object()
        user_level = request.user.user_type or 1

        if user_level >= video.required_level:
            return Response({
                "code": 200,
                "msg": "有权限观看",
                "has_permission": True,
                "video_url": self.get_serializer(video).data['video_url']
            })
        else:
            return Response({
                "code": 403,
                "msg": f"很抱歉，观看该视频需要升级到{video.get_required_level_display()}以上会员等级",
                "has_permission": False,
                "required_level_name": video.get_required_level_display()
            })

    @action(detail=True, methods=['post'])
    def add_play_count(self, request, pk=None):
        course = self.get_object()
        course.play_count += 1
        course.save()
        return Response({
            "code": 200,
            "msg": "播放次数更新成功",
            "play_count": course.play_count
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
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                'code': 200,
                'msg': '注册成功',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_info': {
                    'nickname': user.nickname,
                    'member_id': user.member_id,
                    'user_type': user.user_type,
                    'parent_member_id': user.parent_user.member_id if user.parent_user else None
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'code': 400,
                'msg': f'注册失败：{str(e)}',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

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
            serializer = MemberInfoSerializer(request.user)
            return Response({
                'code': 200,
                'msg': '获取会员信息成功',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print('获取会员信息异常：', str(e))
            return Response({
                'code': 500,
                'msg': f'获取会员信息失败：{str(e)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        serializer = SubConsumeRecordSerializer(sub_consume_data, many=True)

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
                "会员积分：SSTA家居产品，10元积1分，可兑换",
                "SSTA卡券：节日活动或生日优享券，优享活动参与资格",
                "公益课程：家居护肤课程。"
            ],
            3: [
                "SSTA大礼包（2选1）:（1）3980元SSTA家居产品任选，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；（2）一年24次SSTA小油净化，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；",
                "SSTA积分：SSTA家居产品积分兑换，10元积1分；",
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
class OrderAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = OrderAddSerializer(data=request.data)
        if not ser.is_valid():
            logger.error(f"下单参数错误：{ser.errors}")
            return Response({"code": 400, "msg": "参数错误", "data": ser.errors})

        try:
            with transaction.atomic():
                address_id = request.data.get("address_id")
                if not address_id:
                    return Response({"code": 400, "msg": "收货地址ID不能为空"})
                try:
                    address = Address.objects.get(id=address_id, user=request.user)
                except Address.DoesNotExist:
                    return Response({"code": 404, "msg": "收货地址不存在"}, status=404)

                goods_list = request.data.get("goods_list", [])
                if not isinstance(goods_list, list) or len(goods_list) == 0:
                    return Response({"code": 400, "msg": "请选择要购买的商品"})

                total_price = request.data.get("total_price", 0)
                try:
                    total_price = float(total_price)
                    if total_price <= 0:
                        return Response({"code": 400, "msg": "订单总价必须大于0"})
                except (ValueError, TypeError):
                    return Response({"code": 400, "msg": "订单总价格式错误"})

                order_sn = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                order = Order.objects.create(
                    user=request.user,
                    order_sn=order_sn,
                    address=address,
                    total_price=total_price,
                    status=1
                )
                logger.info(f"创建新订单：order_id={order.id}, order_sn={order_sn}")
                msg = "下单成功"

                if not order.pk:
                    raise Exception("订单创建失败，未生成主键ID")

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
                    cart.order = order
                    cart.save()
                    goods_names.append(goods.name)
                    total_count += num

                order.goods_names = "、".join(goods_names)
                order.goods_count = total_count
                order.save()

            return Response({
                "code": 200,
                "msg": msg,
                "data": {
                    "order_sn": order.order_sn,
                    "order_id": order.id,
                    "goods_names": goods_names,
                    "goods_names_str": order.goods_names,
                    "goods_count": order.goods_count
                }
            })

        except Exception as e:
            logger.error(f"下单失败：{str(e)}", exc_info=True)
            return Response({"code": 500, "msg": f"操作失败: {str(e)}"})

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-create_time')
        data_list = []
        for order in orders:
            data_list.append({
                "order_sn": order.order_sn,
                "total_price": str(order.total_price),
                "status": order.get_status_display(),
                "create_time": order.create_time.strftime('%Y-%m-%d %H:%M'),
                "goods_names": order.goods_names,
                "goods_names_str": order.goods_names,
                "goods_count": order.goods_count
            })
        return Response({"code": 200, "data": data_list})

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        order_sn = request.query_params.get("order_sn")

        if not (order_id or order_sn):
            return Response({"code": 400, "msg": "请传入订单ID或订单编号"}, status=400)

        try:
            if order_id:
                order = Order.objects.get(id=order_id, user=request.user)
            else:
                order = Order.objects.get(order_sn=order_sn, user=request.user)
        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "订单不存在"}, status=404)

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

        order_detail = {
            "order_id": order.id,
            "order_sn": order.order_sn,
            "total_price": str(order.total_price),
            "status": order.get_status_display(),
            "status_code": order.status,
            "create_time": order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            "address": {
                "name": order.address.name,
                "phone": order.address.phone,
                "province": order.address.province,
                "city": order.address.city,
                "district": order.address.district,
                "detail": order.address.detail
            } if hasattr(order, 'address') else {},
            "goods_detail": goods_detail,
            "goods_names": [item["goods_name"] for item in goods_detail],
            "item_count": len(goods_detail)
        }

        return Response({
            "code": 200,
            "msg": "获取订单详情成功",
            "data": order_detail
        })

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
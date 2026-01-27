from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse
import time

def index(request):
    time.sleep(1)
    return JsonResponse({'name':'嘉俊','sex':'男','age':'18'})

from .models import Welcome
from django.http import JsonResponse
def welcome(request):
    res = Welcome.objects.all().order_by('-order').first()
    # img = 'http://127.0.0.1:8000/media/' +str(res.img)
    img = 'http://localhost:8000/media/' + str(res.img)
    return JsonResponse({'code':100, 'msg':'成功', 'result':img})

from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from .models import Banner, Notice, Index_Annonce, Category, Goods, User
from .serializer import BannerSerializer, NoticeSerializer, IndexSerializer, CollectionSerializer,CategorySerializer, GoodsSerializer


class BannerView(ListModelMixin, GenericViewSet):
    queryset = Banner.objects.filter(is_delete=False).order_by('order')[:4]
    serializer_class = BannerSerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        notice = Notice.objects.all().order_by('create_time').first()
        serializer_notice = NoticeSerializer(instance=notice)
        return Response({'code':100, 'msg':'成功','banner':res.data, 'notice':serializer_notice.data})

from .models import Collection
from datetime import datetime
class CollevtionView(ListModelMixin, GenericViewSet):
    queryset = Collection.objects.all().filter(create_time__gte=datetime.now().date())
    serializer_class = CollectionSerializer

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        today_count = len(self.get_queryset())
        return Response({'code':100, 'msg':'成功','result':res.data, 'today_count':today_count})


# 商品分类视图（仅列表查询）
class CategoryView(ListModelMixin, GenericViewSet):
    """商品分类接口 - 仅支持列表查询"""
    # 定义查询集（数据源）
    queryset = Category.objects.all().order_by('id')
    # 注意：DRF 正确属性名是 serializer_class（不是 serializer）
    serializer_class = CategorySerializer

    # 重写list方法，统一响应格式
    def list(self, request, *args, **kwargs):
        # 调用父类ListModelMixin的list方法，获取序列化后的数据
        res = super().list(request, *args, **kwargs)
        # 返回自定义格式响应
        return Response({
            'code': 200,
            'msg': 'success',
            'data': res.data
        })

# 商品视图（支持列表查询 + 详情查询）
class GoodsViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """商品接口 - 支持列表查询、详情查询，含搜索/分类过滤"""
    # 基础查询集（所有商品）
    queryset = Goods.objects.all().order_by('id')
    serializer_class = GoodsSerializer

    # 重写list方法：添加搜索/分类过滤 + 自定义响应格式
    def list(self, request, *args, **kwargs):
        # 1. 获取前端传参（搜索关键词、分类ID）
        keyword = request.query_params.get('keyword', '')
        category_id = request.query_params.get('category_id', '')

        # 2. 基于基础queryset做过滤
        queryset = self.get_queryset()  # 获取基础查询集
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)  # 模糊搜索商品名
        if category_id and category_id.isdigit():  # 校验分类ID是数字
            queryset = queryset.filter(category_id=int(category_id))

        # 3. 重新赋值过滤后的queryset（传给序列化器）
        self.queryset = queryset
        # 4. 调用父类list方法获取序列化数据
        res = super().list(request, *args, **kwargs)
        # 5. 返回自定义格式响应
        return Response({
            'code': 200,
            'msg': 'success',
            'data': res.data
        })

    # 重写retrieve方法：商品详情 + 自定义响应格式
    def retrieve(self, request, *args, **kwargs):
        try:
            # 调用父类RetrieveModelMixin的retrieve方法
            res = super().retrieve(request, *args, **kwargs)
            return Response({
                'code': 200,
                'msg': 'success',
                'data': res.data
            })
        except Exception as e:
            # 商品不存在时返回错误格式
            return Response({
                'code': 404,
                'msg': '商品不存在',
                'data': {}
            })


from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import CourseCategory, VideoCourse
from .serializer import CourseCategorySerializer, VideoCourseSerializer
# 课程分类视图
class CourseCategoryViewSet(viewsets.ModelViewSet):
    queryset = CourseCategory.objects.all()
    serializer_class = CourseCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


# 视频课程视图
class VideoCourseViewSet(viewsets.ModelViewSet):
    queryset = VideoCourse.objects.filter(is_publish=True)  # 仅显示已发布课程
    serializer_class = VideoCourseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']  # 确保筛选字段是category（与前端参数名一致）
    search_fields = ['title', 'desc']
    # 可选：重写list方法，打印筛选参数，便于调试
    def list(self, request, *args, **kwargs):
        print('后端接收筛选参数：', request.query_params)  # 打印前端传递的参数
        return super().list(request, *args, **kwargs)
    # 播放次数增加
    @action(detail=True, methods=['post'])
    def add_play_count(self, request, pk=None):
        course = self.get_object()
        course.play_count += 1
        course.save()
        # 核心修改：返回更新后的播放次数，供前端使用
        return Response({
            "code": 200,
            "msg": "播放次数更新成功",
            "play_count": course.play_count  # 返回最新次数
        })

from rest_framework import permissions
from rest_framework.response import Response

from .models import StudyCheckIn, ExamQuestion, ExamRecord, Certification
from .serializer import (
    BenefitSerializer, UserProfileSerializer,
    StudyCheckInSerializer, ExamQuestionSerializer, ExamRecordSerializer, CertificationSerializer
)


# ====================== 注册登录：视图 ======================
# app01/views.py
from rest_framework.views import APIView  # 导入 APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny

from .serializer import RegisterSerializer
# 放弃 ViewSet，改用 APIView 定义注册接口（更简单、更易生效）

class Index_AnnonceView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        indexan = Index_Annonce.objects.all()  # 获取所有固定图片
        fixed_serializer = IndexSerializer(indexan, many=True)
        return Response({
            'code': 200,
            'msg': '获取固定图片成功',
            'fixed_images': fixed_serializer.data  # 返回固定图片数组
        })

from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializer import RegisterSerializer

# 注册接口（原有逻辑重构）
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            # 生成JWT Token
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


class SubUserConsumeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # 权限校验：仅等级2/3/4/5可查看下级消费（按需调整）
        if user.user_type not in [2,3,4,5]:
            return Response({
                'code': 403,
                'msg': '无权限查看下级消费记录'
            }, status=status.HTTP_403_FORBIDDEN)

        consume_records = user.get_sub_consume_records()
        return Response({
            'code': 200,
            'msg': '获取下级消费记录成功',
            'data': consume_records
        })

# 保留你的 MemberInfoView（无需修改，认证通过后会执行）
class MemberInfoView(APIView):
    # 无需手动配置 permission_classes，默认使用 JWT 认证
    def get(self, request):
        print("===== 进入会员信息接口 =====")
        # 获取当前登录用户（JWT 认证通过后，request.user 即为当前用户）
        user = request.user
        if not user.is_authenticated:
            return Response({
                'code': 401,
                'msg': '未授权访问',
                'data': None
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 组装会员信息
        member_info = {
            'nickname': user.nickname,
            'member_id': user.member_id,
            'user_type': user.user_type,
            'star_level': user.star_level,
            'points': user.points
        }
        print(f"===== 会员信息返回成功：{user.nickname} =====")
        return Response({
            'code': 200,
            'msg': '获取会员信息成功',
            'data': member_info
        }, status=status.HTTP_200_OK)

# 3. 会员权益预览视图
class BenefitViewSet(viewsets.GenericViewSet):
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

# 4. 我的页面用户信息视图
class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    def retrieve(self, request):
        instance = self.get_queryset().first()
        serializer = self.get_serializer(instance)
        return Response({'code': 200, 'data': serializer.data})

# ====================== 打卡学习：视图 ======================
class StudyCheckInViewSet(viewsets.ModelViewSet):
    serializer_class = StudyCheckInSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudyCheckIn.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ExamQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExamQuestion.objects.all()
    serializer_class = ExamQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

class ExamRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ExamRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ExamRecord.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # 自动判断是否通过（默认60分及格）
        score = serializer.validated_data.get('score', 0)
        serializer.save(user=self.request.user, is_pass=score >= 60)

class CertificationViewSet(viewsets.ModelViewSet):
    serializer_class = CertificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Certification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# app01/views.py

from rest_framework.permissions import IsAuthenticated
from .serializer import MemberInfoSerializer


# 自定义带调试日志的权限类，继承 IsAuthenticated
class DebugIsAuthenticated(IsAuthenticated):
    """自定义权限类：添加调试日志，查看权限校验失败原因"""

    def has_permission(self, request, view):
        # 打印当前请求的用户信息（权限校验阶段）
        print("===== 权限校验调试日志 =====")
        print("当前请求用户是否为匿名用户：", request.user.is_anonymous)
        print("当前请求用户对象：", request.user)
        print("当前请求 Authorization 头：", request.META.get('HTTP_AUTHORIZATION', '无'))
        print("===========================")

        # 调用父类的权限校验逻辑（保持原有 IsAuthenticated 功能）
        permission_result = super().has_permission(request, view)
        # 打印权限校验结果
        print("权限校验结果（True=通过，False=失败）：", permission_result)
        return permission_result


class MemberInfoView(APIView):
    """会员信息接口：使用自定义调试权限类"""
    permission_classes = [DebugIsAuthenticated]  # 替换为自定义调试权限类

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

# app01/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# 自定义 Token 序列化器：返回用户信息
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # 可选：在 Token 中存储用户信息（前端可解析，但不推荐存储敏感信息）
        token['nickname'] = user.nickname
        token['star_level'] = user.star_level
        return token

    # 关键：重写 validate 方法，自定义返回数据（包含用户信息）
    def validate(self, attrs):
        data = super().validate(attrs)
        # 获取当前登录用户
        user = self.user
        # 补充用户信息到返回数据中
        data['user_info'] = {
            'nickname': user.nickname,
            'star_level': user.star_level,
            'points': user.points,
            'coupon_count': user.coupon_count,
            'member_id': user.member_id,
            'user_type': user.user_type
        }
        return data

# 自定义 Token 视图：使用上面的序列化器
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# app01/views.py


from django.db import transaction
from .models import Cart,  Recipient
from .serializer import CartSerializer, RecipientSerializer, CartAddSerializer
from django.shortcuts import get_object_or_404
# ===================== 购物车接口 【核心修复区 ✅✅✅】=====================
class CartView(APIView):
    permission_classes = [IsAuthenticated]  # 需要登录

    # 1. 获取购物车列表 ✔️ 原有逻辑，正常使用
    def get(self, request):
        cart_list = Cart.objects.filter(user=request.user).select_related('goods')
        serializer = CartSerializer(cart_list, many=True)
        # 计算购物车总价
        total_all = sum([item['total_price'] for item in serializer.data])
        return Response({
            'code': 200,
            'msg': '获取购物车成功',
            'data': {
                'cart_list': serializer.data,
                'total_all': round(total_all, 2)  # 购物车商品总价
            }
        })

    # 2. 添加商品到购物车 ✔️ 原有逻辑，正常使用
    def post(self, request):
        goods_id = request.data.get('goods_id')
        num = int(request.data.get('num', 1))
        if not goods_id:
            return Response({'code': 400, 'msg': '商品ID不能为空'}, status=400)
        # 校验商品是否存在、库存是否足够
        try:
            goods = Goods.objects.get(id=goods_id)
            if goods.stock < num:
                return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
        except Goods.DoesNotExist:
            return Response({'code': 404, 'msg': '商品不存在'}, status=404)
        # 新增/更新购物车
        with transaction.atomic():
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                goods=goods,
                defaults={'num': num}
            )
            if not created:
                # 已存在则增加数量
                cart.num += num
                if cart.num > goods.stock:
                    return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
                cart.save()
        return Response({'code': 200, 'msg': '添加购物车成功'})

    # ✅【核心修复1】修改购物车商品数量 - 从URL路径接收cart_id，适配前端PUT请求 http://xxx/cart/1/
    def put(self, request, cart_id=None):
        # 从URL路径获取cart_id，替代原有的request.data.get('cart_id')
        if not cart_id:
            return Response({'code': 400, 'msg': '购物车ID不能为空'}, status=400)
        num = int(request.data.get('num', 1))  # 正数增加，负数减少
        try:
            # 只允许修改当前登录用户的购物车商品
            cart = Cart.objects.get(id=cart_id, user=request.user)
            # 计算新数量，保证数量≥1
            new_num = cart.num + num
            if new_num < 1:
                return Response({'code': 400, 'msg': '商品数量不能小于1'}, status=400)
            # 库存校验
            if new_num > cart.goods.stock:
                return Response({'code': 400, 'msg': '商品库存不足'}, status=400)
            # 更新数量并保存
            cart.num = new_num
            cart.save()
            return Response({'code': 200, 'msg': '修改数量成功', 'data': {'num': new_num}})
        except Cart.DoesNotExist:
            return Response({'code': 404, 'msg': '购物车商品不存在'}, status=404)

    # ✅【核心修复2】删除购物车商品 - 从URL路径接收cart_id，适配前端DELETE请求 http://xxx/cart/1/
    def delete(self, request, cart_id=None):
        # 从URL路径获取cart_id，替代原有的request.data.get('cart_id')
        if not cart_id:
            return Response({'code': 400, 'msg': '购物车ID不能为空'}, status=400)
        try:
            # 只允许删除当前登录用户的购物车商品
            Cart.objects.filter(id=cart_id, user=request.user).delete()
            return Response({'code': 200, 'msg': '删除成功'})
        except Exception as e:
            return Response({'code': 500, 'msg': f'删除失败：{str(e)}'}, status=500)


# ✅【修复加购逻辑BUG】原有CartAddView的数量累加错误修复
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

        # 库存校验
        goods = get_object_or_404(Goods, id=goods_id)
        if goods.stock < num:
            return Response({
                'code': 400,
                'msg': '库存不足',
                'data': {}
            })

        # 新增/更新购物车 - 修复原逻辑：if not created 时应该累加，不是直接赋值
        cart, created = Cart.objects.get_or_create(
            user=user,
            goods=goods,
            defaults={'num': num}
        )
        if not created:
            cart.num += num  # 修复BUG：累加数量
            if cart.num > goods.stock:
                return Response({'code':400, 'msg':'库存不足'}, status=400)
        cart.save()

        return Response({
            'code': 200,
            'msg': '加入购物车成功',
            'data': {'cart_id': cart.id, 'num': cart.num}
        })


# 保留原有冗余视图（兼容旧调用，无需删除，不影响功能）
# 正确的购物车列表视图
class CartListView(APIView):
    permission_classes = [IsAuthenticated]  # 仅要求登录，权限校验由DRF处理
    # permission_classes = []  # 允许匿名访问
    def get(self, request):
        print("===== 购物车视图调试 =====")
        print(f"请求用户：{request.user}")
        print(f"用户ID：{request.user.id}")
        print(f"会员ID：{request.user.member_id}")
        print(f"是否认证：{request.user.is_authenticated}")
        print(f"权限通过：{self.check_permissions(request)}")
        try:
            # 核心：用DRF认证后的request.user（当前登录用户）查询购物车
            cart_items = Cart.objects.filter(user=request.user)

            # 序列化购物车数据（包含商品名称、数量、价格等）
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
            # 注意：异常时返回500，而非401（避免混淆认证问题）
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
        # 库存校验
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
            # 增加调试日志，便于定位问题
            logger.info(f"清空购物车请求：用户ID={request.user.id}，订单ID={order_id}")

            if order_id:
                # 精准清空：删除该订单关联的购物车商品
                try:
                    order_id = int(order_id)
                    # 先查询是否有对应数据
                    cart_query = Cart.objects.filter(user=request.user, order_id=order_id)
                    cart_count = cart_query.count()

                    if cart_count == 0:
                        logger.warning(f"无订单{order_id}关联的购物车数据，执行全清")
                        # 无精准数据则降级为全清
                        Cart.objects.filter(user=request.user).delete()
                    else:
                        cart_query.delete()
                        logger.info(f"精准清空{cart_count}条购物车数据")
                except ValueError:
                    return Response({"code": 400, "msg": "订单ID格式错误"}, status=400)
            else:
                # 全清：删除当前用户所有购物车商品
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

# ===================== 收件人信息接口 =====================
class RecipientView(APIView):
    permission_classes = [IsAuthenticated]

    # 1. 获取收件人列表
    def get(self, request):
        recipient_list = Recipient.objects.filter(user=request.user)
        serializer = RecipientSerializer(recipient_list, many=True)
        # 获取默认收件人
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

    # 2. 新增/修改收件人信息
    def post(self, request):
        recipient_id = request.data.get('id')  # 有id则为修改，无则为新增
        # 处理默认收件人：若设置为默认，取消其他收件人的默认状态
        if request.data.get('is_default'):
            Recipient.objects.filter(user=request.user, is_default=True).update(is_default=False)
        # 序列化数据
        if recipient_id:
            try:
                recipient = Recipient.objects.get(id=recipient_id, user=request.user)
                serializer = RecipientSerializer(recipient, data=request.data)
            except Recipient.DoesNotExist:
                return Response({'code': 404, 'msg': '收件人信息不存在'}, status=404)
        else:
            serializer = RecipientSerializer(data={**request.data, 'user': request.user.id})
        # 验证并保存
        if serializer.is_valid():
            serializer.save()
            return Response({'code': 200, 'msg': '保存成功', 'data': serializer.data})
        return Response({'code': 400, 'msg': '参数错误', 'error': serializer.errors}, status=400)

# ===================== 结算接口（草稿） =====================
class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        recipient_id = request.data.get('recipient_id')
        # 校验收件人
        try:
            recipient = Recipient.objects.get(id=recipient_id, user=request.user)
        except Recipient.DoesNotExist:
            return Response({'code': 404, 'msg': '收件人信息不存在'}, status=404)
        # 获取购物车商品
        cart_list = Cart.objects.filter(user=request.user).select_related('goods')
        if not cart_list:
            return Response({'code': 400, 'msg': '购物车为空'}, status=400)
        # 计算总价（实际项目中可生成订单，此处仅返回结算信息）
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


from .models import Address, Order, OrderItem
from .serializer import AddressSerializer, OrderAddSerializer
import datetime, random


# ========== 收货地址接口 ==========
class AddressView(APIView):
    permission_classes = [IsAuthenticated]

    # 获取地址列表
    def get(self, request):
        address_list = Address.objects.filter(user=request.user)
        return Response(
            {"code": 200, "msg": "success", "data": {"address_list": AddressSerializer(address_list, many=True).data}})


# 新增地址
class AddressAddView(APIView):
    permission_classes = [IsAuthenticated]

    # POST 用于新增 (不带 pk)
    # views.py 这种方式不需要修改 URL，也不需要 pk
    def post(self, request):
        # 1. 先把该用户之前的地址全部删掉
        Address.objects.filter(user=request.user).delete()

        # 2. 存入这条新地址
        ser = AddressSerializer(data=request.data)
        if ser.is_valid():
            ser.save(user=request.user)
            return Response({"code": 200, "msg": "地址已覆盖更新"})
        return Response({"code": 400, "data": ser.errors})


# ========== 订单接口 ==========
from django.db import transaction

import logging

logger = logging.getLogger(__name__)


class OrderAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = OrderAddSerializer(data=request.data)
        if not ser.is_valid():
            logger.error(f"下单参数错误：{ser.errors}")
            return Response({"code": 400, "msg": "参数错误", "data": ser.errors})

        try:
            with transaction.atomic():
                # ========== 核心修改1：增加关键参数校验 ==========
                address_id = request.data.get("address_id")
                goods_list = request.data.get("goods_list", [])

                # 1. 校验收货地址
                if not address_id:
                    return Response({"code": 400, "msg": "收货地址ID不能为空"})
                try:
                    address = Address.objects.get(id=address_id, user=request.user)
                except Address.DoesNotExist:
                    return Response({"code": 404, "msg": "收货地址不存在"}, status=404)

                # 2. 校验商品列表非空
                if not isinstance(goods_list, list) or len(goods_list) == 0:
                    return Response({"code": 400, "msg": "请选择要购买的商品"})

                # 3. 校验总价（避免前端传递异常值）
                total_price = request.data.get("total_price", 0)
                try:
                    total_price = float(total_price)
                    if total_price <= 0:
                        return Response({"code": 400, "msg": "订单总价必须大于0"})
                except (ValueError, TypeError):
                    return Response({"code": 400, "msg": "订单总价格式错误"})

                # ========== 核心修改2：确保Order先保存（生成主键） ==========
                # 查找/创建订单（status=1：待付款）
                order = Order.objects.filter(user=request.user, status=1).first()
                if order:
                    # 更新现有订单：先保存，确保主键存在
                    order.address = address
                    order.total_price = total_price
                    order.save()  # 强制保存，更新主键（即使是现有订单，也确保状态同步）
                    logger.info(f"更新现有订单：order_id={order.id}, order_sn={order.order_sn}")
                    # 删除旧的订单明细（避免重复）
                    OrderItem.objects.filter(order=order).delete()
                    msg = "订单已更新"
                else:
                    # 新建订单：create方法会自动保存并生成主键
                    order_sn = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                    order = Order.objects.create(
                        user=request.user,
                        order_sn=order_sn,
                        address=address,
                        total_price=total_price,
                        status=1  # 1=待付款
                    )
                    logger.info(f"创建新订单：order_id={order.id}, order_sn={order_sn}")
                    msg = "下单成功"

                # ========== 核心修改3：安全创建OrderItem（增加异常捕获） ==========
                # 验证Order主键存在（兜底校验）
                if not order.pk:
                    raise Exception("订单创建失败，未生成主键ID")

                goods_names = []
                total_count = 0
                for item in goods_list:
                    cart_id = item.get("cart_id")
                    num = item.get("num", 1)

                    # 校验购物车ID和数量
                    if not cart_id or not isinstance(num, int) or num < 1:
                        raise Exception(f"购物车参数错误：cart_id={cart_id}, num={num}")

                    # 查询购物车（仅当前用户）
                    try:
                        cart = Cart.objects.get(id=cart_id, user=request.user)
                    except Cart.DoesNotExist:
                        raise Exception(f"购物车商品不存在：cart_id={cart_id}")

                    goods = cart.goods
                    # 库存校验
                    if goods.stock < num:
                        raise Exception(f"商品库存不足：{goods.name}（库存{goods.stock}，需{num}）")

                    # 创建订单明细（此时order已有主键，可安全关联）
                    OrderItem.objects.create(
                        order=order,  # ✅ 此时order.pk已存在
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

                # 更新订单的冗余字段（商品名称、数量）
                order.goods_names = "、".join(goods_names)
                order.goods_count = total_count
                order.save()  # 再次保存，确保冗余字段生效

            # 返回成功响应
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
            logger.error(f"下单失败：{str(e)}", exc_info=True)  # 打印完整异常栈
            return Response({"code": 500, "msg": f"操作失败: {str(e)}"})

# 示例：订单列表视图中获取产品名称
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
                # 方案1：调用动态属性
                "goods_names": order.goods_names,  # 列表：["商品A", "商品B"]
                "goods_names_str": order.goods_names_str,  # 字符串："商品A、商品B"
                # 方案2：直接取冗余字段（和方案1返回结果一致）
                # "goods_names": order.goods_names.split("、") if order.goods_names else [],
                # "goods_names_str": order.goods_names or "无商品",
                "goods_count": order.goods_count
            })
        return Response({"code": 200, "data": data_list})

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 获取前端传递的订单ID/订单编号
        order_id = request.query_params.get("order_id")
        order_sn = request.query_params.get("order_sn")

        # 校验参数
        if not (order_id or order_sn):
            return Response({"code": 400, "msg": "请传入订单ID或订单编号"}, status=400)

        # 查询订单（仅查询当前用户的订单）
        try:
            if order_id:
                order = Order.objects.get(id=order_id, user=request.user)
            else:
                order = Order.objects.get(order_sn=order_sn, user=request.user)
        except Order.DoesNotExist:
            return Response({"code": 404, "msg": "订单不存在"}, status=404)

        # 获取订单所有商品明细（关联商品表，提取名称）
        order_items = OrderItem.objects.filter(order=order).select_related('goods')
        goods_detail = [
            {
                "goods_id": item.goods.id,
                "goods_name": item.goods.name,  # 商品名称
                "goods_image": f"http://localhost:8000/media/{item.goods.image_url}" if item.goods.image_url else "",
                # 商品图片
                "num": item.num,  # 购买数量
                "price": str(item.price),  # 单价
                "total_price": str(item.num * item.price)  # 该商品总价
            }
            for item in order_items
        ]

        # 组装订单详情数据
        order_detail = {
            "order_id": order.id,
            "order_sn": order.order_sn,
            "total_price": str(order.total_price),
            "status": order.get_status_display(),
            "status_code": order.status,  # 状态码（便于前端判断）
            "create_time": order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            "address": {  # 收货地址信息
                "name": order.address.name,
                "phone": order.address.phone,
                "province": order.address.province,
                "city": order.address.city,
                "district": order.address.district,
                "detail": order.address.detail
            } if hasattr(order, 'address') else {},
            "goods_detail": goods_detail,  # 所有商品明细（含名称）
            "goods_names": [item["goods_name"] for item in goods_detail],  # 仅商品名称列表
            "item_count": len(goods_detail)  # 商品总数
        }

        return Response({
            "code": 200,
            "msg": "获取订单详情成功",
            "data": order_detail
        })

import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from django.views.decorators.csrf import csrf_exempt

ACCESS_KEY_ID = ""
ACCESS_KEY_SECRET = ""
REGION_ID = "cn"  # 固定，号码认证服务仅支持杭州地域

# 初始化阿里云客户端
client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION_ID)


@csrf_exempt
def send_sms_code(request):
    """发送短信验证码接口"""
    if request.method != "POST":
        return JsonResponse({"code": -1, "msg": "仅支持POST请求"})

    # 获取前端传递的手机号
    data = json.loads(request.body)
    phone = data.get("phone")
    if not phone or not phone.startswith("1") or len(phone) != 11:
        return JsonResponse({"code": -1, "msg": "手机号格式错误"})

    # 构造阿里云短信验证请求
    request = CommonRequest()
    request.set_domain("dypnsapi.aliyuncs.com")
    request.set_version("2017-05-25")
    request.set_action_name("SendSmsVerifyCode")
    request.set_method("POST")
    # 请求参数（必填）
    request.add_query_param("PhoneNumber", phone)  # 接收验证码的手机号
    request.add_query_param("SceneCode", "SMS_LOGIN")  # 场景码（固定：登录场景）
    request.add_query_param("OutId", "your_out_id")  # 自定义标识（可选）

    try:
        # 调用阿里云API
        response = client.do_action_with_exception(request)
        res_data = json.loads(response.decode("utf-8"))
        if res_data.get("Code") == "OK":
            # 返回BizId（验证时需要）
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
    """验证短信验证码接口"""
    if request.method != "POST":
        return JsonResponse({"code": -1, "msg": "仅支持POST请求"})

    # 获取前端传递的参数
    data = json.loads(request.body)
    phone = data.get("phone")
    code = data.get("code")
    biz_id = data.get("biz_id")
    if not (phone and code and biz_id):
        return JsonResponse({"code": -1, "msg": "参数不完整"})

    # 构造阿里云验证请求
    request = CommonRequest()
    request.set_domain("dypnsapi.aliyuncs.com")
    request.set_version("2017-05-25")
    request.set_action_name("VerifySmsVerifyCode")
    request.set_method("POST")
    # 请求参数（必填）
    request.add_query_param("PhoneNumber", phone)
    request.add_query_param("VerifyCode", code)  # 用户输入的验证码
    request.add_query_param("BizId", biz_id)  # 发送时返回的BizId

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
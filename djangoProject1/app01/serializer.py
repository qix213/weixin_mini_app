from rest_framework import serializers
from .models import Banner, Notice, Collection, Category, Goods, GoodsImage, Index_Annonce
class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'

class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = '__all__'

class IndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = Index_Annonce
        fields = '__all__'

class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = '__all__'
        depth = 1

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

# 新增商品图片序列化器
class GoodsImageSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(read_only=True)  # 读取自定义的URL属性

    class Meta:
        model = GoodsImage
        fields = ['id', 'image_url', 'order']

# 修改原有GoodsSerializer，嵌套图片序列化器
class GoodsSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(read_only=True)
    is_star = serializers.BooleanField(read_only=True)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    member_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # 嵌套序列化商品的所有图片（related_name='images'）
    images = GoodsImageSerializer(many=True, read_only=True)

    class Meta:
        model = Goods
        fields = '__all__'  # 包含images字段

from .models import Cart, Recipient
class CartSerializer(serializers.ModelSerializer):
    goods = GoodsSerializer(read_only=True)  # 嵌套商品信息
    total_price = serializers.SerializerMethodField()  # 计算商品总价（数量*单价）

    class Meta:
        model = Cart
        fields = ['id', 'goods', 'num', 'total_price']

    def get_total_price(self, obj):
        """计算单个商品总价"""
        return round(obj.num * obj.goods.member_price, 2)

class CartAddSerializer(serializers.Serializer):
    goods_id = serializers.IntegerField(required=True)
    num = serializers.IntegerField(required=True, min_value=1)

    def validate_goods_id(self, value):
        try:
            Goods.objects.get(id=value)
        except Goods.DoesNotExist:
            raise serializers.ValidationError('商品不存在')
        return value
# 收件人信息序列化器
class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = ['id', 'name', 'phone', 'province', 'city', 'area', 'address', 'is_default']
        extra_kwargs = {
            'phone': {'required': True},
            'address': {'required': True}
        }

from .models import VideoCourse
# 视频课程序列化器
class VideoCourseSerializer(serializers.ModelSerializer):
    required_level_name = serializers.CharField(source='get_required_level_display', read_only=True)
    cover_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = VideoCourse
        fields = ['id', 'title', 'required_level', 'required_level_name', 'cover_url', 'video_url', 'duration', 'play_count',
                  'desc', 'create_time']

    # 拼接完整图片URL
    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover_url and hasattr(obj.cover_url, 'url'):
            return request.build_absolute_uri(obj.cover_url.url)
        return ""

    # 拼接完整视频URL
    def get_video_url(self, obj):
        request = self.context.get('request')
        if obj.video_url and hasattr(obj.video_url, 'url'):
            return request.build_absolute_uri(obj.video_url.url)
        return ""



from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from .models import StudyCheckIn, ExamQuestion, ExamRecord, Certification
from django.core.validators import RegexValidator

User = get_user_model()  # 自动获取settings.py中配置的User模型

# ====================== 注册登录：序列化器 ======================
# 1. 自定义JWT登录序列化器（返回用户信息）
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # 补充用户信息到token
        token['member_id'] = user.member_id
        token['nickname'] = user.nickname
        token['user_type'] = user.user_type
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # 返回token + 用户核心信息
        data['user_info'] = {
            'member_id': self.user.member_id,
            'nickname': self.user.nickname,
            'user_type': self.user.user_type,
            'user_type_name': self.user.get_user_type_display(),
            'star_level': self.user.star_level,
            'points': self.user.points,
            'coupon_count': self.user.coupon_count
        }
        return data


# 2. 会员权益序列化器（注册时预览/返回）
class BenefitSerializer(serializers.Serializer):
    user_type = serializers.IntegerField()
    user_type_name = serializers.CharField()
    fee = serializers.CharField()
    benefits = serializers.ListField(child=serializers.CharField())


# app01/serializer.py（仅保留修复后的 RegisterSerializer 核心部分，其他序列化器不变）
from django.contrib.auth import get_user_model
import random
import string

User = get_user_model()


# 生成8位会员ID（数字+字母）
def generate_8bit_member_id():
    chars = string.ascii_uppercase + string.digits  # 大写字母+数字，避免大小写混淆
    while True:
        member_id = ''.join(random.choice(chars) for _ in range(8))
        if not User.objects.filter(member_id=member_id).exists():
            return member_id


class RegisterSerializer(serializers.ModelSerializer):
    # 新增：接收前端传递的recommender_id（推荐人ID）
    recommender_id = serializers.CharField(max_length=8, required=False, allow_blank=True)
    # 密码确认字段
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['nickname', 'phone', 'password', 'password_confirm', 'user_type', 'recommender_id']
        extra_kwargs = {
            'password': {'write_only': True},  # 密码仅写入，不返回
            'user_type': {'required': True}  # 会员/开店类型必传
        }

    # 验证密码一致性 + 推荐人ID（核心修复：缩进+返回逻辑）
    def validate(self, attrs):
        # 1. 校验两次密码是否一致
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("两次密码不一致")

        # 2. 验证推荐人ID（若传递了非空值）
        recommender_id = attrs.get('recommender_id', '').strip()
        if recommender_id:  # 仅当推荐人ID非空时校验
            try:
                # 通过 member_id 查找推荐人（上级）
                parent_user = User.objects.get(member_id=recommender_id)
                attrs['parent_user'] = parent_user  # 关联到上级
            except User.DoesNotExist:
                raise serializers.ValidationError(f"推荐人ID {recommender_id} 不存在")

        # ========== 核心：必须返回校验后的 attrs ==========
        # 移除确认密码（不需要存入数据库）
        attrs.pop('password_confirm')
        return attrs

    # 修复：仅保留一个 create 方法（合并原有逻辑）
    def create(self, validated_data):
        # 生成8位会员ID
        validated_data['member_id'] = generate_8bit_member_id()

        # 移除 parent_user（避免 create_user 接收未知参数）
        parent_user = validated_data.pop('parent_user', None)

        # 创建用户（密码自动加密）
        user = User.objects.create_user(
            username=validated_data['nickname'],  # 复用username字段（Django auth要求）
            nickname=validated_data['nickname'],
            member_id=validated_data['member_id'],
            phone=validated_data['phone'],
            password=validated_data['password'],
            user_type=validated_data['user_type']
        )

        # 关联推荐人（上级）
        if parent_user:
            user.parent_user = parent_user
            user.save()

        return user


# 4. 用户信息（我的页面）序列化器
class UserProfileSerializer(serializers.ModelSerializer):
    user_type_name = serializers.CharField(source='get_user_type_display')
    benefits = serializers.ListField(child=serializers.CharField(), source='get_benefits')

    class Meta:
        model = User
        fields = [
            'member_id', 'nickname', 'user_type', 'user_type_name', 'star_level',
            'points', 'coupon_count', 'phone', 'email', 'province', 'city',
            'district', 'address', 'birth_date', 'benefits'
        ]


# ====================== 打卡学习：序列化器 ======================
class StudyCheckInSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    user_nickname = serializers.CharField(source='user.nickname', read_only=True)

    class Meta:
        model = StudyCheckIn
        fields = '__all__'
        read_only_fields = ['user']  # 用户自动关联登录用户


class ExamQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamQuestion
        fields = '__all__'


class ExamRecordSerializer(serializers.ModelSerializer):
    course_type_name = serializers.CharField(source='get_course_type_display', read_only=True)
    user_nickname = serializers.CharField(source='user.nickname', read_only=True)

    class Meta:
        model = ExamRecord
        fields = '__all__'
        read_only_fields = ['user']


class CertificationSerializer(serializers.ModelSerializer):
    cert_type_name = serializers.CharField(source='get_cert_type_display', read_only=True)
    status_name = serializers.CharField(source='get_status_display', read_only=True)
    user_nickname = serializers.CharField(source='user.nickname', read_only=True)

    class Meta:
        model = Certification
        fields = '__all__'
        read_only_fields = ['user', 'status', 'review_time']

class MemberInfoSerializer(serializers.ModelSerializer):
    """会员信息序列化器：格式化返回会员核心字段"""
    # 格式化会员类型（返回文字描述，如“蓝粉”而非 1）
    user_type_text = serializers.CharField(source='get_user_type_display', read_only=True)
    # 格式化会员到期时间（可选，优化前端显示）
    # vip_expire_time_text = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        # 只返回前端需要的会员字段，隐藏敏感信息
        fields = [
            'member_id', 'nickname', 'phone', 'birth_date',
            'user_type', 'user_type_text', 'star_level', 'points',
            'coupon_count'
        ]

from .models import Address

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'phone', 'province', 'city', 'district', 'address', 'detail', 'is_default', 'user']
        read_only_fields = ['user']  # 仅限制user字段只读，无其他验证
class OrderAddSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(required=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    goods_list = serializers.ListField(required=True)

# app01/serializer.py

from .models import Order, OrderItem

# 1. 订单项序列化器（保持不变）
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['goods_name', 'num', 'price', 'total_price']

# 2. 订单序列化器（保持不变）
class OrderSerializer(serializers.ModelSerializer):
    goods_list = OrderItemSerializer(source='items', many=True, read_only=True)
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    status_name = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = ['order_sn', 'total_price', 'status', 'status_name', 'create_time', 'goods_list']

# 3. 下级会员信息序列化器（新增：拆分独立序列化器）
class SubMemberInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    member_id = serializers.CharField()
    nickname = serializers.CharField()
    user_type = serializers.IntegerField()
    user_type_name = serializers.CharField()
    star_level = serializers.IntegerField()

# 4. 下级消费记录序列化器（修复：使用嵌套序列化器替代DictField）
class SubConsumeRecordSerializer(serializers.Serializer):
    # 会员信息：使用独立的序列化器（DRF标准嵌套方式）
    member_info = SubMemberInfoSerializer(read_only=True)
    # 该会员的订单列表：嵌套OrderSerializer
    orders = OrderSerializer(many=True, read_only=True)
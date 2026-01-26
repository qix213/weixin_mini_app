from rest_framework import serializers
from .models import Banner, Notice, Collection, Category, Goods, Index_Annonce
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

class GoodsSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(read_only=True) # 自定义图片URL字段
    class Meta:
        model = Goods
        fields = '__all__'

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

from .models import CourseCategory, VideoCourse

# 课程分类序列化器
class CourseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = "__all__"

# 视频课程序列化器
class VideoCourseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    cover_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = VideoCourse
        fields = ['id', 'title', 'category', 'category_name', 'cover_url', 'video_url', 'duration', 'play_count',
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


# 3. 注册序列化器（动态验证字段）
import random
import string


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
            'user_type': {'required': True}     # 会员/开店类型必传
        }

    # 验证密码一致性
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("两次密码不一致")
        # 验证推荐人ID（若传递）
        recommender_id = attrs.get('recommender_id')
        if recommender_id:
            try:
                # 通过member_id查找推荐人（推荐人ID=会员ID）
                parent_user = User.objects.get(member_id=recommender_id)
                attrs['parent_user'] = parent_user  # 关联到parent_user字段
            except User.DoesNotExist:
                raise serializers.ValidationError("推荐人ID不存在")
        # 移除密码确认字段（无需存入数据库）
        attrs.pop('password_confirm')
        return attrs

    # 重写创建方法：加密密码
    def create(self, validated_data):
        # 弹出recommender_id（User模型无此字段，已通过validate关联到parent_user）
        validated_data.pop('recommender_id', None)
        # 创建用户并加密密码
        user = User.objects.create_user(
            username=validated_data['phone'],  # 用手机号作为Django默认的username
            nickname=validated_data['nickname'],
            phone=validated_data['phone'],
            user_type=validated_data['user_type'],
            parent_user=validated_data.get('parent_user'),  # 关联推荐人
            password=validated_data['password']  # create_user会自动加密密码
        )
        return user

    def create(self, validated_data):
        # 生成8位会员ID
        validated_data['member_id'] = generate_8bit_member_id()
        # 密码加密（Django AbstractUser 自带）
        user = User.objects.create_user(
            username=validated_data['nickname'],  # 复用username字段
            nickname=validated_data['nickname'],
            member_id=validated_data['member_id'],
            phone=validated_data['phone'],
            password=validated_data['password'],
            user_type=validated_data['user_type'],
            parent_user=validated_data.get('parent_user')  # 推荐人可为None
        )
        # ========== 核心修改3：删除生成推荐码的逻辑（不需要推荐码） ==========
        # user.generate_recommend_code()  # 注释/删除这行

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
    # user 由 request.user 提供，设为只读
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Address
        fields = ['id', 'user', 'name', 'phone', 'address', 'detail_address', 'create_time']

class OrderAddSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(required=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    goods_list = serializers.ListField(required=True)
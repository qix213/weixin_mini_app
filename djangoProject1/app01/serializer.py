from rest_framework import serializers
from .models import (Banner, Notice, Category, Goods, GoodsImage,
                     Index_Annonce, PointsRecord, Order, OrderItem)
from decimal import Decimal  # 导入Decimal


def force_https(url):
    """强行将 url 转换为 https"""
    if not url:
        return ""
    if url.startswith('http://'):
        return url.replace('http://', 'https://', 1)
    return url


class BannerSerializer(serializers.ModelSerializer):
    img = serializers.SerializerMethodField()  # 🌟 手动接管

    class Meta:
        model = Banner
        fields = '__all__'

    def get_img(self, obj):
        if not obj.img: return ""
        request = self.context.get('request')
        url = request.build_absolute_uri(obj.img.url) if request else obj.img.url
        return force_https(url)


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = '__all__'


class IndexSerializer(serializers.ModelSerializer):
    # 这里定义的是返回给前端的键名
    img_url = serializers.SerializerMethodField()

    class Meta:
        model = Index_Annonce
        fields = '__all__'

    def get_img_url(self, obj):
        # 🌟 重点修正：obj 是模型对象，必须使用模型里真实的字段名 'img'
        # 如果你的模型字段叫 image，就改成 obj.image
        if not obj.img:
            return ""

        request = self.context.get('request')
        # 使用 obj.img.url 获取相对路径，然后拼成绝对路径
        url = request.build_absolute_uri(obj.img.url) if request else obj.img.url

        # 调用之前定义的强转 HTTPS 函数
        return force_https(url)


# ================= 优化后的分类序列化器 =================
class CategorySerializer(serializers.ModelSerializer):
    # 🌟 强行接管图标字段（报错里有 /media/icon/，猜测字段名为 icon 或 image）
    icon = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_icon(self, obj):
        # 兼容处理：检查模型里是 icon 还是 image 字段
        img_field = getattr(obj, 'icon', None) or getattr(obj, 'image', None)
        if not img_field:
            return ""

        request = self.context.get('request')
        url = request.build_absolute_uri(img_field.url) if request else img_field.url
        return force_https(url)  # 调用你刚写的强转 HTTPS 方法


# ================= 优化后的商品多媒体(图/视频)序列化器 =================
class GoodsImageSerializer(serializers.ModelSerializer):
    # 改为 SerializerMethodField 以便控制 HTTPS
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = GoodsImage
        fields = ['id', 'media_type', 'image_url', 'video_url', 'media_url', 'order']

    def get_image_url(self, obj):
        return force_https(obj.image_url)  # 🌟 强行清洗模型返回的 property

    def get_video_url(self, obj):
        return force_https(obj.video_url)


# ================= 优化后的主商品序列化器 =================
class GoodsSerializer(serializers.ModelSerializer):
    # 🌟 废弃 ReadOnlyField，强行接管 image_url
    image_url = serializers.SerializerMethodField()
    # 🌟 如果 Goods 模型本身还有 image 字段，也必须接管
    image = serializers.SerializerMethodField()

    is_star = serializers.BooleanField(read_only=True)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    member_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    images = GoodsImageSerializer(many=True, read_only=True)

    can_point_exchange = serializers.BooleanField(read_only=True)
    exchange_points = serializers.IntegerField(read_only=True)

    class Meta:
        model = Goods
        fields = '__all__'
        read_only_fields = ['point_price']

    # 拦截并清洗 image_url（无论它是 property 还是普通字段）
    def get_image_url(self, obj):
        url = getattr(obj, 'image_url', "")
        if not url: return ""

        request = self.context.get('request')
        if request and not url.startswith('http'):
            url = request.build_absolute_uri(url)
        return force_https(url)

    # 拦截并清洗原始 image 字段
    def get_image(self, obj):
        if hasattr(obj, 'image') and obj.image:
            request = self.context.get('request')
            url = request.build_absolute_uri(obj.image.url) if request else obj.image.url
            return force_https(url)
        return ""

from .models import OfflineServiceRecord, UserOfflineProject


class UserOfflineProjectSerializer(serializers.ModelSerializer):
    member_id = serializers.CharField(source='user.member_id', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_nickname = serializers.SerializerMethodField(read_only=True)
    project_image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserOfflineProject
        # 🌟 统一规范：放弃 '__all__'，把前端需要的字段明明白白写出来
        fields = [
            'id', 'user', 'member_id', 'customer_nickname',
            'project', 'project_name', 'project_image',
            'total_times', 'remain_times', 'update_time'
        ]

    def get_customer_nickname(self, obj):
        user = obj.user
        if user:
            return getattr(user, 'nickname', None) or getattr(user, 'username', '未知用户')
        return '未知用户'

    def get_project_image(self, obj):
        if obj.project and obj.project.image:
            return obj.project.image_url
        return ""


class OfflineServiceRecordSerializer(serializers.ModelSerializer):
    # 🌟 统一规范：直接透出自定义的会员 ID
    member_id = serializers.CharField(source='user.member_id', read_only=True)

    # 🌟 修复冲突：全部改用 MethodField 动态安全获取，彻底告别 memberinfo
    customer_nickname = serializers.SerializerMethodField(read_only=True)
    customer_avatar = serializers.SerializerMethodField(read_only=True)
    manager_name = serializers.SerializerMethodField(read_only=True)

    project_name = serializers.CharField(source='project.name', read_only=True)
    project_image = serializers.SerializerMethodField(read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)
    appointment_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = OfflineServiceRecord
        # 🌟 统一规范：放弃 '__all__'，精准列出！
        fields = [
            'id', 'user', 'member_id', 'customer_nickname', 'customer_avatar',
            'manager', 'manager_name', 'project', 'project_name', 'project_image',
            'status', 'status_text', 'appointment_time',
            'rating', 'review_content', 'review_images',
            'create_time', 'confirm_time', 'review_time'
        ]

    def get_project_image(self, obj):
        if obj.project and obj.project.image:
            return obj.project.image_url
        return ""

    def get_customer_nickname(self, obj):
        user = obj.user
        if user:
            return getattr(user, 'nickname', None) or getattr(user, 'username', '未知用户')
        return '未知用户'

    def get_customer_avatar(self, obj):
        user = obj.user
        # 安全获取头像 URL
        if user and hasattr(user, 'avatar') and user.avatar:
            return user.avatar.url
        return ""

    def get_manager_name(self, obj):
        manager = obj.manager
        if manager:
            return getattr(manager, 'nickname', None) or getattr(manager, 'username', '未知店长')
        return '未知店长'

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
    num = serializers.IntegerField(required=True, min_value=Decimal('1'), )

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

from .models import VideoCourse, CourseCategory

class VideoCourseSerializer(serializers.ModelSerializer):
    # 🌟 核心：将分类 ID 转化为具体的分类名称字符串
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = VideoCourse
        # 将 required_level 移除，确保 category 在里面
        fields = ['id', 'title', 'category', 'cover_url', 'video_url', 'duration',
                  'play_count', 'desc', 'is_publish', 'create_time', 'sort_order']

    # 拼接完整图片URL
    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover_url and hasattr(obj.cover_url, 'url'):
            url = request.build_absolute_uri(obj.cover_url.url)
            return force_https(url)
        return ""

    # 🌟 修复：拼接完整视频URL (名字必须是 get_video_url，且取的是 obj.video_url)
    def get_video_url(self, obj):
        request = self.context.get('request')
        if obj.video_url and hasattr(obj.video_url, 'url'):
            url = request.build_absolute_uri(obj.video_url.url)
            return force_https(url)
        return ""
class CourseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = '__all__'


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
    # 接收前端传递的推荐人ID
    recommender_id = serializers.CharField(max_length=8, required=False, allow_blank=True, write_only=True)
    # 密码确认字段
    password_confirm = serializers.CharField(write_only=True)
    # 接收前端生成的会员ID
    member_id = serializers.CharField(max_length=8, required=False)

    class Meta:
        model = User
        # 🌟 必须包含 phone，因为 views.py 会把微信解密出来的真实手机号塞进来
        fields = ['member_id', 'nickname', 'phone', 'password', 'password_confirm', 'user_type', 'recommender_id']
        extra_kwargs = {
            'password': {'write_only': True},
            'user_type': {'required': True},
            'phone': {'required': True}  # 确保手机号必填
        }

    # 验证密码一致性 + 推荐人ID
    def validate(self, attrs):
        # 1. 校验两次密码是否一致
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError("两次密码不一致")

        # 2. 验证推荐人ID（若传递了非空值）
        recommender_id = attrs.get('recommender_id', '').strip()
        if recommender_id:
            try:
                # 通过 member_id 查找推荐人（上级）
                parent_user = User.objects.get(member_id=recommender_id)
                attrs['parent_user'] = parent_user
            except User.DoesNotExist:
                raise serializers.ValidationError(f"推荐人ID {recommender_id} 不存在")

        # 移除不需要存入数据库的辅助字段
        attrs.pop('password_confirm', None)
        attrs.pop('recommender_id', None)
        return attrs

    def create(self, validated_data):
        # 提取关联的上级
        parent_user = validated_data.pop('parent_user', None)

        # 1. 获取 member_id
        # 前端在注册页已经生成了 member_id，直接使用前端传来的，保持前后端一致
        member_id = validated_data.get('member_id')
        if not member_id:
            member_id = generate_8bit_member_id() # 兜底逻辑

        # 2. 提取手机号
        phone = validated_data.get('phone')

        # 🚨 3. 极其关键的修复：
        # Django 的 auth 系统严格要求 username 必须是唯一的！
        # 如果你用 nickname 作为 username，一旦有两个用户起了相同的昵称，数据库就会报错崩溃 (500)！
        # 所以，这里必须用唯一的真实手机号作为 username！
        user = User.objects.create_user(
            username=phone,  # 🌟 修复点：用绝对唯一的手机号作为账号
            nickname=validated_data.get('nickname', ''),
            member_id=member_id, # 🌟 修复点：使用前端传来的 ID
            phone=phone,
            password=validated_data.get('password'),
            user_type=validated_data.get('user_type', 1)
        )

        # 关联推荐人（上级）
        if parent_user:
            user.parent_user = parent_user
            user.save(update_fields=['parent_user'])

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
    status_name = serializers.CharField(source='status_display', read_only=True)
    user_nickname = serializers.CharField(source='user.nickname', read_only=True)

    class Meta:
        model = Certification
        fields = '__all__'
        read_only_fields = ['user', 'status', 'review_time']


class MemberInfoSerializer(serializers.ModelSerializer):
    """会员信息序列化器：格式化返回会员核心字段"""
    # 格式化会员类型（返回文字描述，如“蓝粉”而非 1）
    user_type_text = serializers.CharField(source='get_user_type_display', read_only=True)

    class Meta:
        model = User
        # 只返回前端需要的会员字段，隐藏敏感信息
        fields = [
            'member_id', 'nickname', 'phone', 'birth_date',
            'user_type', 'user_type_text', 'star_level', 'points',
            'coupon_count', 'create_time', 'expire_time', 'avatar'
        ]


from .models import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'phone', 'province', 'city', 'district', 'address', 'detail', 'is_default', 'user']
        read_only_fields = ['user']  # 仅限制user字段只读，无其他验证


class OrderGoodsItemSerializer(serializers.Serializer):
    cart_id = serializers.IntegerField(required=True, error_messages={"required": "购物车ID不能为空"})
    num = serializers.IntegerField(required=True, min_value=Decimal('1'), error_messages={
        "required": "商品数量不能为空",
        "min_value": "商品数量不能小于1"
    })


class OrderAddSerializer(serializers.Serializer):
    # 配送类型：1=快递配送 2=到店自取（必填）
    delivery_type = serializers.IntegerField(
        required=True,
        min_value=Decimal('1'),
        max_value=2,
        error_messages={
            "required": "配送类型不能为空",
            "min_value": "配送类型只能是1（快递）或2（到店）",
            "max_value": "配送类型只能是1（快递）或2（到店）"
        }
    )
    # 收货地址ID：快递时必填，自提时允许为null（非必填+允许null）
    address_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "地址ID必须是数字"}
    )
    # 取货门店ID：自提时必填，快递时允许为null（非必填+允许null）
    pick_up_store_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "门店ID必须是数字"}
    )
    # 订单总价：DecimalField兼容前端float输入（DRF自动转换）
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01'),
        error_messages={
            "required": "订单总价不能为空",
            "min_value": "订单总价必须大于0"
        }
    )
    # 商品列表：嵌套子序列化器，校验每个商品的cart_id和num
    goods_list = OrderGoodsItemSerializer(
        many=True,
        required=True,
        error_messages={"required": "请选择要购买的商品"}
    )
    deduct_point = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        error_messages={
            "min_value": "抵扣积分不能为负数"
        }
    )

    # 自定义校验：补充积分抵扣的校验
    def validate(self, attrs):
        delivery_type = attrs.get("delivery_type")
        address_id = attrs.get("address_id")
        pick_up_store_id = attrs.get("pick_up_store_id")
        deduct_point = attrs.get("deduct_point", 0)  # 新增积分抵扣参数
        request = self.context.get("request")

        # 规则1：快递配送（delivery_type=1）
        if delivery_type == 1:
            # 必须传address_id且不为null/0
            if not address_id:
                raise serializers.ValidationError({"address_id": "快递配送需选择收货地址"})
            # 禁止传pick_up_store_id
            if pick_up_store_id is not None:
                raise serializers.ValidationError({"pick_up_store_id": "快递配送无需选择取货门店"})
            # 额外校验：地址是否存在且属于当前用户（增加空值判断！）
            request = self.context.get("request")
            if request and request.user.is_authenticated:  # 先判断request是否存在+用户是否登录
                try:
                    Address.objects.get(id=address_id, user=request.user)
                except Address.DoesNotExist:
                    raise serializers.ValidationError({"address_id": "收货地址不存在或不属于当前用户"})
            # 若request不存在，不校验地址归属（交给视图层处理）

        # 规则2：到店自取（delivery_type=2）
        elif delivery_type == 2:
            # 必须传pick_up_store_id且不为null/0
            if not pick_up_store_id:
                raise serializers.ValidationError({"pick_up_store_id": "到店自取需选择取货门店"})
            # 禁止传address_id
            if address_id is not None:
                raise serializers.ValidationError({"address_id": "到店自取无需选择收货地址"})
            # 额外校验：门店是否存在（假设门店模型是Area，需根据你实际模型调整）
            try:
                from .models import Area  # 按需导入门店模型
                Area.objects.get(id=pick_up_store_id)
            except ImportError:
                pass  # 若没有Area模型，注释此行
            except Area.DoesNotExist:
                raise serializers.ValidationError({"pick_up_store_id": "取货门店不存在"})

        # 规则3：校验goods_list非空
        goods_list = attrs.get("goods_list")
        if len(goods_list) == 0:
            raise serializers.ValidationError({"goods_list": "商品列表不能为空"})

        if deduct_point > 0:
            # 1. 校验用户是否登录
            if not request or not request.user.is_authenticated:
                raise serializers.ValidationError({"deduct_point": "登录后才能使用积分抵扣"})
            # 2. 校验用户积分是否充足
            user_points = getattr(request.user, 'points', 0)
            if deduct_point > user_points:
                raise serializers.ValidationError(
                    {"deduct_point": f"积分不足：当前{user_points}分，需抵扣{deduct_point}分"})
            # 3. 校验积分抵扣金额不超过订单总价（1积分=0.01元）
            total_price = attrs.get("total_price")
            deduct_money = deduct_point * Decimal('0.01')
            if deduct_money > total_price:
                raise serializers.ValidationError(
                    {"deduct_point": f"抵扣积分过多：最多可抵扣{int(total_price / Decimal('0.01'))}积分"})
        return attrs


# ========== 订单项/订单序列化器 ==========
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['goods_name', 'num', 'price', 'total_price', 'weight', 'volume']


class OrderSerializer(serializers.ModelSerializer):
    goods_list = OrderItemSerializer(source='items', many=True, read_only=True)
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    status_name = serializers.CharField(source='status_display', read_only=True)

    # 补全所有收货人信息字段
    receiver_name = serializers.SerializerMethodField()  # 收货人姓名
    receiver_phone = serializers.SerializerMethodField()  # 收货人电话
    receiver_province = serializers.SerializerMethodField()  # 省
    receiver_city = serializers.SerializerMethodField()  # 市
    receiver_district = serializers.SerializerMethodField()  # 区/县
    receiver_address = serializers.SerializerMethodField()  # 详细地址
    receiver_full_address = serializers.SerializerMethodField()  # 完整地址（省+市+区+详细地址）

    point_deduct = serializers.IntegerField(read_only=True)  # 抵扣积分
    point_deduct_money = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)  # 积分抵扣金额
    actual_pay_money = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)  # 实际支付金额

    class Meta:
        model = Order
        fields = [
            'order_sn', 'total_price', 'status', 'status_name',
            'create_time', 'goods_list',
            # 收货人信息字段
            'receiver_name', 'receiver_phone', 'receiver_province',
            'receiver_city', 'receiver_district', 'receiver_address',
            'receiver_full_address',
            # 积分计费字段
            'point_deduct', 'point_deduct_money', 'actual_pay_money',

            # 🌟 新增：发件人信息与京东物流前置校验结果 🌟
            'sender_name', 'sender_phone', 'sender_address',
            'jd_precheck_status', 'jd_error_msg'
        ]

    # 优化权限逻辑：
    # 规则1：订单所属用户（自己）能看到完整收货信息
    # 规则2：4/5级用户能看到下级订单的收货信息
    # 规则3：其他用户返回空
    def _has_receiver_permission(self, obj, request_user):
        # 订单所属用户（自己）
        if obj.user == request_user:
            return True
        # 4/5级用户（可查看下级订单）
        if request_user.user_type in [4, 5]:
            return True
        return False

    # 实现各收货信息字段的获取逻辑
    def get_receiver_name(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.name or ''
        return ''

    def get_receiver_phone(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.phone or ''
        return ''

    def get_receiver_province(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.province or ''
        return ''

    def get_receiver_city(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.city or ''
        return ''

    def get_receiver_district(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.district or ''
        return ''

    def get_receiver_address(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return ''
        if self._has_receiver_permission(obj, request.user) and obj.address:
            return obj.address.detail or ''  # 注意：对应Address模型的detail字段（详细地址）
        return ''

    def get_receiver_full_address(self, obj):
        """拼接完整地址：省+市+区+详细地址"""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not obj.address:
            return ''
        if self._has_receiver_permission(obj, request.user):
            full_addr = f"{obj.address.province or ''} {obj.address.city or ''} {obj.address.district or ''} {obj.address.detail or ''}".strip()
            return full_addr
        return ''


# 3. 下级会员信息序列化器
class SubMemberInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    member_id = serializers.CharField()
    nickname = serializers.CharField()
    user_type = serializers.IntegerField()
    user_type_name = serializers.CharField()
    star_level = serializers.IntegerField()


# 4. 下级消费记录序列化器
class SubConsumeRecordSerializer(serializers.Serializer):
    # 会员信息：使用独立的序列化器（DRF标准嵌套方式）
    member_info = SubMemberInfoSerializer(read_only=True)
    # 该会员的订单列表：嵌套OrderSerializer
    orders = OrderSerializer(many=True, read_only=True)


# 积分变动记录序列化器（前端积分明细页面用）
class PointsRecordSerializer(serializers.ModelSerializer):
    points_type_name = serializers.CharField(source='get_points_type_display', read_only=True)
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)  # 格式化时间

    class Meta:
        model = PointsRecord
        # 🌟 修复：由于模型中的 related_desc 被重命名为了 description，这里同步修改
        fields = ['id', 'points', 'points_type', 'points_type_name', 'related_id', 'description', 'create_time']


from .models import UserCoupon, Coupon


class CouponTemplateSerializer(serializers.ModelSerializer):
    """优惠券模板序列化器（管理后台用）"""
    coupon_type_name = serializers.CharField(source='get_coupon_type_display', read_only=True)

    class Meta:
        model = Coupon
        fields = '__all__'


class UserCouponSerializer(serializers.ModelSerializer):
    """用户优惠券序列化器（前端展示用）"""
    # 从优惠券模板获取字段
    title = serializers.CharField(source='coupon.title', read_only=True)
    coupon_type = serializers.IntegerField(source='coupon.coupon_type', read_only=True)
    coupon_type_name = serializers.CharField(source='coupon.get_coupon_type_display', read_only=True)
    money = serializers.DecimalField(source='coupon.money', max_digits=10, decimal_places=2, read_only=True)
    discount_rate = serializers.DecimalField(source='coupon.discount_rate', max_digits=3, decimal_places=2,
                                             read_only=True)
    min_consume = serializers.DecimalField(source='coupon.min_consume', max_digits=10, decimal_places=2, read_only=True)

    # 格式化时间和状态
    start_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)
    end_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserCoupon
        fields = [
            'id', 'title', 'coupon_type', 'coupon_type_name',
            'money', 'discount_rate', 'min_consume',
            'start_time', 'end_time', 'is_used', 'is_expired', 'is_valid', 'order_sn'
        ]


# 补充用户优惠券统计序列化器
class UserCouponStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    valid = serializers.IntegerField()
    expired = serializers.IntegerField()
    used = serializers.IntegerField()

from .models import UserSkinProfile, SkinPhotoRecord

class SkinPhotoRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkinPhotoRecord
        fields = ['id', 'face_image', 'uploaded_at']

class UserSkinProfileSerializer(serializers.ModelSerializer):
    # 🌟 核心：嵌套照片记录，前端拉取档案时，会自动带上该档案下的所有历史照片
    photo_records = SkinPhotoRecordSerializer(many=True, read_only=True)

    class Meta:
        model = UserSkinProfile
        fields = [
            'id', 'subject_name', 'answers', 'skin_tags',
            'final_report', 'skincare_plan', 'created_time',
            'update_time', 'photo_records'
        ]
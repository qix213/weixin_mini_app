from django.db import models

# Create your models here

class Welcome(models.Model):
    img = models.ImageField(upload_to='welcome',default='welcome_fRb2uKK.png',verbose_name='图片')
    order = models.IntegerField(verbose_name='顺序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')
    class Meta:
        verbose_name_plural = '欢迎页面'
    def __str__(self):
        return str(self.img)

class Banner(models.Model):
    img = models.ImageField(upload_to='banner',default='banner1.png',verbose_name='图片')
    order = models.IntegerField(verbose_name='顺序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')
    class Meta:
        verbose_name_plural = '轮播图'

    def __str__(self):
        return str(self.img)

class Notice(models.Model):
    title = models.CharField(max_length=100, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    img = models.ImageField(upload_to='notice',default='notice.png',verbose_name='公告图片')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name_plural = '公告表'

    def __str__(self):
        return self.title

class Index_Annonce(models.Model):
    img = models.ImageField(upload_to='index_annonce/',default='banner1.png',verbose_name='宣传图片')
    order = models.IntegerField(verbose_name='顺序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')
    class Meta:
        verbose_name = '首页宣传图片'
        verbose_name_plural = verbose_name

    def __str__(self):
        return str(self.img)

class Collection(models.Model):
    name = models.CharField(max_length=32, verbose_name='姓名')
    name_pinyin = models.CharField(max_length=32, verbose_name='姓名拼音', null=True)
    avatar = models.ImageField(upload_to='collection/%Y/%m/%d', default='default.png', verbose_name='头像')
    create_time = models.DateTimeField(auto_now=True, verbose_name='采集时间')
    score = models.IntegerField(verbose_name='积分', default=0)
    area = models.ForeignKey(to='Area', null=True, verbose_name='门店名称', on_delete=models.CASCADE)

    class Meta:
        verbose_name = '会员信息采集表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

class Area(models.Model):
    name = models.CharField(max_length=32, verbose_name='门店全名')
    desc = models.CharField(max_length=32, verbose_name='门店简称')
    user = models.ForeignKey(to='UserInfo', on_delete=models.CASCADE, null=True, verbose_name='用户名')

    class Meta:
        verbose_name = '门店表'
        verbose_name_plural = verbose_name


    def __str__(self):
        return self.name

class UserInfo(models.Model):
    name = models.CharField(max_length=32, verbose_name='姓名')
    avatar = models.FileField(upload_to='avator', max_length=128, verbose_name='头像')
    create_time = models.DateTimeField(auto_now=True, verbose_name='日期')


    class Meta:
        verbose_name = '店主用户表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 商品分类
class Category(models.Model):
    name = models.CharField('分类名称', max_length=50)
    icon = models.FileField(upload_to='icon', max_length=128, verbose_name='分类图标')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '商品分类'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 商品信息
class Goods(models.Model):
    name = models.CharField('商品名称', max_length=100)
    brief_intro = models.CharField('简短介绍', max_length=200)
    intro = models.TextField('详细介绍')
    specs = models.TextField('规格参数', blank=True)
    original_price = models.DecimalField('原价', max_digits=10, decimal_places=2)
    member_price = models.DecimalField('会员价', max_digits=10, decimal_places=2)
    stock = models.IntegerField('库存', default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='所属分类')
    # 商品主图（可多图，这里简化为单图，多图可新建GoodsImage模型）
    image = models.ImageField('商品图片', upload_to='goods/')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    # 序列化时返回图片完整URL
    @property
    def image_url(self):
        return f"http://localhost:8000/{self.image.url}"

from django.contrib.auth.models import User

# 课程分类模型

class CourseCategory(models.Model):
    # 自定义主键：IntegerField + primary_key=True + auto_created=False（关闭自增）
    id = models.IntegerField(
        primary_key=True,  # 设为主键
        auto_created=False,  # 关闭自动生成（手动输入ID）
        verbose_name="分类ID"
    )
    name = models.CharField(max_length=50, verbose_name="分类名称")
    desc = models.CharField(max_length=200, blank=True, null=True, verbose_name="分类描述")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "课程分类"
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return self.name

# 视频课程模型
class VideoCourse(models.Model):
    title = models.CharField(max_length=100, verbose_name="课程标题")
    category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, verbose_name="课程分类")
    cover_url = models.ImageField(upload_to='course/cover/', verbose_name="封面图片")
    video_url = models.FileField(upload_to='course/video/', verbose_name="视频文件")
    duration = models.CharField(max_length=20, verbose_name="视频时长")  # 如：05:30
    play_count = models.IntegerField(default=0, verbose_name="播放次数")
    desc = models.TextField(blank=True, null=True, verbose_name="课程描述")
    is_publish = models.BooleanField(default=True, verbose_name="是否发布")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "视频课程"
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.title

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import random
import string

# 其他原有模型保持不变，仅修改 User 模型
class User(AbstractUser):
    # 会员类型（保持原有3个等级）
    USER_TYPE_CHOICES = (
        (1, "蓝朋友"),
        (2, "蓝明星"),
        (3, "TA创粉"),
    )
    user_type = models.IntegerField(choices=USER_TYPE_CHOICES, null=True, blank=True, verbose_name="会员等级")

    # 1. 会员ID改为8位数字/字母组合
    member_id = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]{8}$', '会员ID必须是8位数字或字母')],
        verbose_name="会员ID"
    )

    nickname = models.CharField(max_length=50, verbose_name="昵称", unique=True, null=True, blank=True)
    birth_date = models.DateField(verbose_name="出生日期", null=True, blank=True)
    phone = models.CharField(
        max_length=11,
        validators=[RegexValidator(r'^1[3-9]\d{9}$', '手机号格式错误')],
        verbose_name="手机号", null=True, blank=True
    )
    email = models.EmailField(verbose_name="邮箱", null=True, blank=True)
    province = models.CharField(max_length=20, verbose_name="省份", null=True, blank=True)
    city = models.CharField(max_length=20, verbose_name="城市", null=True, blank=True)
    district = models.CharField(max_length=20, verbose_name="区县", null=True, blank=True)

    # 2. 新增上下级关联：外键指向自身，关联推荐人（上级）
    parent_user = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='sub_users', verbose_name="上级会员")

    # 3. 新增推荐码字段（8位数字+字母）
    recommend_code = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]{8}$', '推荐码必须是8位数字或字母')],
        verbose_name="推荐码", null=True, blank=True
    )

    points = models.IntegerField(default=0, verbose_name="积分余额")
    coupon_count = models.IntegerField(default=0, verbose_name="星礼券数量")
    star_level = models.IntegerField(default=1, verbose_name="星级（1-5星）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="注册时间")

    # 解决 groups / user_permissions 反向访问器冲突（原有逻辑保留）
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='app01_user_groups',
        related_query_name='app01_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='app01_user_permissions',
        related_query_name='app01_user',
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.get_user_type_display()}-{self.member_id}"

    # 原有权益逻辑保留
    def get_benefits(self):
        if self.user_type == 1:  # 蓝朋友
            return [
                "蓝粉VIP大礼包：3套SSTA旅行mini装，5张100元兑换单品券（单次用一张）",
                "会员积分：SSTA家居产品，10元积1分，可兑换",
                "会员价：SSTA家居产品，一年蓝粉星价"
            ]
        elif self.user_type == 2:  # 蓝明星
            return [
                "SSTA产品，15%返点（奇肌币），可提现",
                "会员积分：SSTA家居产品，10元积1分，可兑换",
                "会员价：SSTA家居产品，一年蓝粉星价"
            ]
        elif self.user_type == 3:  # TA创粉
            return [
                "9800元线上会员价产品任选",
                "SSTA产品，30%或50%返点（奇肌币），可提现",
                "会员积分：SSTA家居产品，10元积1分，可兑换",
                "会员价：SSTA家居产品，永久蓝粉星价",
                "培训赋能：护肤私教证书",
                "系统化配套标准化工具设备",
                "蓝色奇肌商学院小程序专业皮肤课程",
                "高端疗愈营、沙龙活动权限；《她力量》、《明星代言人》首推官资格"
            ]
        return []

    # 新增：生成8位推荐码（关联会员ID）
    def generate_recommend_code(self):
        # 基于会员ID生成种子，保证唯一性
        seed = sum([ord(c) for c in self.member_id])
        random.seed(seed)
        chars = string.ascii_letters + string.digits
        code = ''.join(random.choice(chars) for _ in range(8))
        self.recommend_code = code
        self.save()
        return code

    # 新增：获取下级会员（递归/直接）
    def get_sub_users(self):
        # 直接下级
        direct_subs = self.sub_users.all()
        # 若需递归获取所有下级，可扩展此方法
        return direct_subs

    # 新增：获取下级消费记录
    def get_sub_consume_records(self):
        from .models import Order, OrderItem
        sub_users = self.get_sub_users()
        # 获取所有下级的订单
        sub_orders = Order.objects.filter(user__in=sub_users)
        # 组装消费记录（订单+商品）
        consume_records = []
        for order in sub_orders:
            items = OrderItem.objects.filter(order=order).values('goods__name', 'num', 'price')
            consume_records.append({
                "order_sn": order.order_sn,
                "total_price": order.total_price,
                "status": order.get_status_display(),
                "create_time": order.create_time,
                "goods": list(items)
            })
        return consume_records


# ====================== 打卡学习：4个核心模型（正确引用User） ======================

# 1. 学习打卡模型
class StudyCheckIn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="打卡用户")  # 大写User，无冲突
    course = models.ForeignKey(VideoCourse, on_delete=models.CASCADE, verbose_name="打卡课程")
    check_in_time = models.DateTimeField(auto_now_add=True, verbose_name="打卡时间")
    check_in_date = models.DateField(auto_now_add=True, verbose_name="打卡日期")
    note = models.TextField(blank=True, null=True, verbose_name="学习笔记")

    class Meta:
        verbose_name = "学习打卡"
        verbose_name_plural = verbose_name
        unique_together = ['user', 'course', 'check_in_date']  # 每日唯一打卡

    def __str__(self):
        return f"{self.user.nickname} - {self.course.title} - {self.check_in_date}"

# 2. 考核题库模型
class ExamQuestion(models.Model):
    COURSE_TYPE = [
        (1, "皮肤学"),
        (2, "四维三阶问题肌"),
        (3, "五维筋膜"),
        (4, "品牌篇"),
        (5, "产品篇"),
        (6, "各类皮肤问题家居解决方案"),
    ]
    question = models.TextField(verbose_name="题目")
    option_a = models.CharField(max_length=200, verbose_name="选项A")
    option_b = models.CharField(max_length=200, verbose_name="选项B")
    option_c = models.CharField(max_length=200, verbose_name="选项C")
    option_d = models.CharField(max_length=200, verbose_name="选项D", blank=True, null=True)
    answer = models.CharField(max_length=10, verbose_name="正确答案")  # A/B/C/D
    course_type = models.IntegerField(choices=COURSE_TYPE, verbose_name="对应课程分类")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "考核题库"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.question[:20]

# 3. 考核记录模型
class ExamRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="参考用户")  # 大写User，无冲突
    course_type = models.IntegerField(verbose_name="考核分类")
    score = models.IntegerField(verbose_name="考核分数")
    is_pass = models.BooleanField(default=False, verbose_name="是否通过")
    exam_time = models.DateTimeField(auto_now_add=True, verbose_name="考核时间")

    class Meta:
        verbose_name = "考核记录"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.nickname} - {self.get_course_type_display()} - {self.score}分"

# 4. 线下认证模型
class Certification(models.Model):
    CERT_TYPE = [
        (1, "护肤私教认证"),
        (2, "线下实操考核"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="认证用户")  # 大写User，无冲突
    cert_type = models.IntegerField(choices=CERT_TYPE, verbose_name="认证类型")
    name = models.CharField(max_length=50, verbose_name="真实姓名")
    phone = models.CharField(max_length=11, verbose_name="手机号")
    id_card = models.CharField(max_length=18, verbose_name="身份证号")
    upload_file = models.FileField(upload_to='certification/', verbose_name="认证材料")
    status = models.IntegerField(default=0, choices=[(0, "待审核"), (1, "已通过"), (2, "已驳回")], verbose_name="认证状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="提交时间")
    review_time = models.DateTimeField(blank=True, null=True, verbose_name="审核时间")

    class Meta:
        verbose_name = "线下认证"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.nickname} - {self.get_cert_type_display()} - {self.get_status_display()}"

# 新增：购物车模型
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    goods = models.ForeignKey(Goods, on_delete=models.CASCADE, verbose_name='商品')
    num = models.IntegerField('数量', default=1)  # 商品数量
    create_time = models.DateTimeField('添加时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'cart'
        verbose_name = '购物车'
        verbose_name_plural = verbose_name
        unique_together = ('user', 'goods')  # 一个用户对一个商品只能有一条购物车记录

# 新增：收件人信息模型
class Recipient(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    name = models.CharField('收件人姓名', max_length=50)
    phone = models.CharField('手机号', max_length=11)
    province = models.CharField('省份', max_length=20)
    city = models.CharField('城市', max_length=20)
    area = models.CharField('区县', max_length=20)
    address = models.CharField('详细地址', max_length=200)
    is_default = models.BooleanField('是否默认', default=False)  # 默认收件人
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'recipient'
        verbose_name = '收件人信息'
        verbose_name_plural = verbose_name

# 收货地址模型
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    name = models.CharField(max_length=50, verbose_name="收货人")
    phone = models.CharField(max_length=11, verbose_name="手机号")
    address = models.CharField(max_length=255, verbose_name="省市区地址")
    detail_address = models.CharField(max_length=255, verbose_name="详细地址")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "收货地址"
        verbose_name_plural = "收货地址"

# 订单主表
class Order(models.Model):
    ORDER_STATUS = (
        (0, "待付款"),
        (1, "待发货"),
        (2, "待收货"),
        (3, "已完成"),
        (4, "已取消"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    order_sn = models.CharField(max_length=64, unique=True, verbose_name="订单编号")
    address = models.ForeignKey(Address, on_delete=models.CASCADE, verbose_name="收货地址")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总价")
    status = models.IntegerField(choices=ORDER_STATUS, default=0, verbose_name="订单状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"

# 订单商品明细表
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="订单")
    goods = models.ForeignKey(Goods, on_delete=models.CASCADE, verbose_name="商品")
    num = models.IntegerField(verbose_name="购买数量")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="商品单价")

    class Meta:
        verbose_name = "订单商品"
        verbose_name_plural = "订单商品"
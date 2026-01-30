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

# 视频课程模型
class VideoCourse(models.Model):
    title = models.CharField(max_length=100, verbose_name="课程标题")
    # category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, verbose_name="课程分类")
    cover_url = models.ImageField(upload_to='course/cover/', verbose_name="封面图片")
    video_url = models.FileField(upload_to='course/video/', verbose_name="视频文件")
    duration = models.CharField(max_length=20, verbose_name="视频时长")  # 如：05:30
    play_count = models.IntegerField(default=0, verbose_name="播放次数")
    desc = models.TextField(blank=True, null=True, verbose_name="课程描述")
    is_publish = models.BooleanField(default=True, verbose_name="是否发布")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    # 新增：观看该视频的最低会员等级（关联User的user_type）
    REQUIRED_LEVEL_CHOICES = (
        (1, "蓝朋友"),
        (2, "蓝明星"),
        (3, "护肤私教"),
        (4, "MINI-studio 主理人"),
        (5, "Ta创+"),
    )
    required_level = models.IntegerField(
        choices=REQUIRED_LEVEL_CHOICES,
        default=1,
        verbose_name="最低观看会员等级"
    )
    class Meta:
        verbose_name = "视频课程"
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.title

# app01/models.py
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import random
import string

class User(AbstractUser):
    # 完整的用户类型（匹配前端1-5）
    USER_TYPE_CHOICES = (
        (1, "蓝朋友"),
        (2, "蓝明星"),
        (3, "护肤私教"),
        (4, "MINI-studio 主理人"),
        (5, "Ta创+"),
    )
    user_type = models.IntegerField(choices=USER_TYPE_CHOICES, null=True, blank=True, verbose_name="会员等级")

    # 会员ID：8位数字+字母，自动生成
    member_id = models.CharField(
        max_length=8,
        unique=True,
        blank=True,  # 允许空白，由save方法自动生成
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

    # 推荐人关联：外键指向自身（上级会员）
    parent_user = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='sub_users', verbose_name="上级会员")

    points = models.IntegerField(default=0, verbose_name="积分余额")
    coupon_count = models.IntegerField(default=0, verbose_name="星礼券数量")
    star_level = models.IntegerField(default=1, verbose_name="星级（1-5星）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="注册时间")

    # 解决反向访问器冲突
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

    # 原有权益逻辑保留（按需调整）
    def get_benefits(self):
        if self.user_type == 1:  # 蓝朋友
            return [
                "SSTA新人券：2张200元代金券套，只能用来购买368元mini旅行套；",
                "SSTA价格：零售价格购买产品，不享受会员价；",
                "SSTA卡券：节日活动或生日优享券，优享活动参与资格；",
                "公益课程：护肤知识课程。"
            ]
        elif self.user_type == 2:  # 蓝明星
            return [
                "蓝粉VIP大礼包（2选1）:（1）3套SSTA旅行套盒，2张100元兑换单品券（每单限用一张），限期一个月；（2）一套小油净化（6次），4张100元兑换单品券，每单限用一张），限期一个月；",
                "会员星价：SSTA家居产品，一年蓝粉星价",
                "会员积分：SSTA家居产品，10元积1分，可兑换",
                "SSTA卡券：节日活动或生日优享券，优享活动参与资格",
                "公益课程：家居护肤课程。"
            ]
        elif self.user_type == 3:  # 护肤私教
            return [
                "SSTA大礼包（2选1）:（1）3980元SSTA家居产品任选，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；（2）一年24次SSTA小油净化，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；",
                "SSTA积分：SSTA家居产品积分兑换，10元积1分；",
                "SSTA奇肌币：裂变客户购买产品15%返点，可提现；",
                "SSTA卡券：节日或活动优享券；",
                "专业课程：护肤专业课程。"
            ]
        elif self.user_type == 4:  # MINI-studio 主理人
            return [
                "产品折扣：享产品零售价5折权益，产品任选；",
                "培训赋能：护肤私教初级班+初级证书；",
                "工具系统：系统化配套标准化+工具设备；",
                "专业课程：蓝色奇肌商学院小程序专业皮肤课程。"
            ]
        elif self.user_type == 5:  # Ta创+
            return [
                "Ta创+高端俱乐部会员，享奇肌疗愈营，高端沙龙活动；",
                "产品折扣：享产品零售价2.5折权益，产品任选；",
                "SSTA运营：运营中心模版店的打造及扶持；",
                "培训赋能：护肤私教全部体系课程+证书；",
                "专业课程：蓝色奇肌商学院小程序专业皮肤课程；",
                "《她力量》，《明星代言人》首推官资格。"
            ]
        return []

    # 重写save方法：自动生成唯一member_id
    def save(self, *args, **kwargs):
        if not self.member_id:  # 首次保存时生成
            chars = string.ascii_uppercase + string.digits  # 大写字母+数字，避免大小写冲突
            while True:
                member_id = ''.join(random.choice(chars) for _ in range(8))
                # 确保会员ID唯一
                if not User.objects.filter(member_id=member_id).exists():
                    self.member_id = member_id
                    break
        super().save(*args, **kwargs)

    # 新增：获取下级会员（递归/直接）
    def get_sub_users(self):
        # 直接下级
        direct_subs = self.sub_users.all()
        # 若需递归获取所有下级，可扩展此方法
        return direct_subs

    # 获取下级消费记录
    def get_sub_consume_records(self, current_level=0):
        """
        返回按下级会员分组的消费记录（包含会员信息+订单列表）
        :param current_level: 要查询的下级层级
        :return: 列表，每个元素是{"member_info": 会员信息, "orders": 该会员的订单列表}
        """
        # 核心修复：确保current_level是整数
        try:
            current_level = int(current_level)
        except (ValueError, TypeError):
            current_level = 0

        from .models import Order

        # 1. 查询当前用户的所有下级会员（根据业务调整层级逻辑）
        sub_users = self.sub_users.all()  # 一级下级，多级可递归查询
        if current_level > 0:
            # 如需多级查询，可补充递归逻辑
            pass

        # 2. 按下级会员分组查询订单
        sub_consume_data = []
        for sub_user in sub_users:
            # 查询该下级会员的所有订单
            orders = Order.objects.filter(
                user=sub_user,
                status__in=[1, 2, 3]  # 仅查询有效订单（待付款/待发货/已发货）
            ).order_by('-create_time').prefetch_related('items')  # 预加载订单项，提升性能

            if orders:
                # 组装会员信息+订单列表
                sub_consume_data.append({
                    "member_info": {
                        "id": sub_user.id,
                        "member_id": sub_user.member_id,
                        "nickname": sub_user.nickname,
                        "user_type": sub_user.user_type,
                        "user_type_name": sub_user.get_user_type_display(),
                        "star_level": sub_user.star_level
                    },
                    "orders": orders
                })

        return sub_consume_data


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
# app01/models.py
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="关联用户")
    name = models.CharField(max_length=50, verbose_name="收件人姓名")
    phone = models.CharField(max_length=11, verbose_name="手机号")
    province = models.CharField(max_length=20, blank=True, null=True, verbose_name="省份")  # 新增
    city = models.CharField(max_length=20, blank=True, null=True, verbose_name="城市")      # 新增
    district = models.CharField(max_length=20, blank=True, null=True, verbose_name="区县")  # 新增
    address = models.CharField(max_length=200, verbose_name="省市区拼接")                 # 原有的拼接字段
    detail = models.CharField(max_length=200, verbose_name="详细地址")                    # 核心：确保字段名是detail
    is_default = models.BooleanField(default=False, verbose_name="是否默认地址")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "收货地址"
        verbose_name_plural = "收货地址"
        ordering = ["-update_time"]  # 按更新时间倒序

    def __str__(self):
        return f"{self.name} - {self.address}{self.detail_address}"

# 订单主表
class Order(models.Model):
    ORDER_STATUS = (
        (0, "待付款"),
        (1, "待发货"),
        (2, "待收货"),
        (3, "已完成"),
        (4, "已取消"),
    )
    # 原有核心字段保留
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    order_sn = models.CharField(max_length=64, unique=True, verbose_name="订单编号")
    goods_names = models.CharField(max_length=500, null=True, blank=True, verbose_name="订单产品名称（拼接）")
    goods_count = models.IntegerField(default=0, verbose_name="订单商品总数")
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="收货地址")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总价")
    status = models.IntegerField(choices=ORDER_STATUS, default=0, verbose_name="订单状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    # ========== 新增订单详情字段 ==========
    # 1. 支付相关
    PAY_METHOD_CHOICES = (
        (1, "微信支付"),
        (2, "支付宝支付"),
        (3, "线下支付"),
    )
    pay_method = models.IntegerField(choices=PAY_METHOD_CHOICES, null=True, blank=True, verbose_name="支付方式")
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name="支付时间")  # 支付完成时间
    pay_no = models.CharField(max_length=64, null=True, blank=True, verbose_name="支付单号（微信/支付宝）")

    # 2. 物流相关
    logistics_no = models.CharField(max_length=64, null=True, blank=True, verbose_name="物流单号")
    logistics_company = models.CharField(max_length=32, null=True, blank=True, verbose_name="物流公司")
    ship_time = models.DateTimeField(null=True, blank=True, verbose_name="发货时间")  # 商家发货时间
    receive_time = models.DateTimeField(null=True, blank=True, verbose_name="收货时间")  # 用户确认收货时间

    # 3. 取消/售后相关
    cancel_time = models.DateTimeField(null=True, blank=True, verbose_name="取消时间")
    cancel_reason = models.CharField(max_length=200, null=True, blank=True, verbose_name="取消原因")
    remark = models.CharField(max_length=500, null=True, blank=True, verbose_name="用户备注")  # 订单备注

    # 4. 软删除（避免误删订单）
    is_delete = models.BooleanField(default=False, verbose_name="是否删除")

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.order_sn} - {self.get_status_display()}"

    # ✅ 修复1：重写save方法，先保存生成主键，再处理订单商品统计
    def save(self, *args, **kwargs):
        # 标记是否是新建订单（无主键）
        is_new = self.pk is None

        # 第一步：先调用父类save生成主键（关键！）
        super().save(*args, **kwargs)

        # 第二步：只有订单已保存（有主键），才处理商品名称和数量统计
        if not is_new and self.items.exists():
            # 拼接商品名称
            self.goods_names = "、".join([item.goods_name for item in self.items.all()])
            # 计算商品总数
            self.goods_count = sum([item.num for item in self.items.all()])
            # 再次保存（仅更新统计字段，不会重复创建）
            super().save(update_fields=['goods_names', 'goods_count'])

    # ✅ 修复2：在Order模型中定义goods_names_str属性（视图需要的字段）
    @property
    def goods_names_str(self):
        """返回订单商品名称拼接字符串，如：商品A、商品B"""
        if self.goods_names:
            return self.goods_names
        # 兜底：如果goods_names为空，从items重新拼接
        if self.pk and self.items.exists():
            return "、".join([item.goods_name for item in self.items.all()])
        return "无商品"

    # 可选：快捷获取订单商品列表
    @property
    def goods_list(self):
        """返回订单商品详情列表"""
        if self.pk and self.items.exists():
            return [
                {
                    "name": item.goods_name,
                    "num": item.num,
                    "price": float(item.price),
                    "total_price": float(item.total_price)
                }
                for item in self.items.all()
            ]
        return []

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    goods = models.ForeignKey(Goods, on_delete=models.CASCADE, verbose_name='商品')
    num = models.IntegerField('数量', default=1)  # 商品数量
    create_time = models.DateTimeField('添加时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联订单")
    class Meta:
        db_table = 'cart'
        verbose_name = '购物车'
        verbose_name_plural = verbose_name
        unique_together = ('user', 'goods')  # 一个用户对一个商品只能有一条购物车记录

# 订单商品明细表（补充商品快照字段，确保订单详情独立完整）
class OrderItem(models.Model):
    # 原有核心字段保留
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="订单")
    goods = models.ForeignKey(Goods, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联商品")
    num = models.IntegerField(verbose_name="购买数量")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="商品单价")

    # ========== 商品快照字段（保留） ==========
    goods_name = models.CharField(max_length=100, default="未知商品", verbose_name="商品名称")  # 冗余存储商品名
    goods_image = models.CharField(max_length=255, null=True, blank=True, verbose_name="商品图片URL")  # 冗余存储图片
    goods_specs = models.CharField(max_length=200, null=True, blank=True, verbose_name="商品规格")  # 存储商品规格
    total_price = models.DecimalField(max_digits=10, default="0", decimal_places=2,
                                      verbose_name="该商品总价")  # num*price

    class Meta:
        verbose_name = "订单商品"
        verbose_name_plural = "订单商品"

    def __str__(self):
        return f"{self.order.order_sn} - {self.goods_name} x {self.num}"

    # 可选：重写save方法，自动计算商品总价
    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.num * self.price
        super().save(*args, **kwargs)


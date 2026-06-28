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

# 原有Goods模型保持不变，新增GoodsImage模型存储多组介绍图
class GoodsImage(models.Model):
    """商品多图模型（关联主商品）"""
    goods = models.ForeignKey(
        'Goods',
        on_delete=models.CASCADE,
        related_name='images',  # 反向关联名，用于查询商品的所有图片
        verbose_name='所属商品'
    )
    image = models.ImageField('商品介绍图', upload_to='goods/images/')  # 图片存储路径
    order = models.IntegerField('排序', default=0)  # 图片展示顺序
    create_time = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '商品图片'
        verbose_name_plural = verbose_name
        ordering = ['order']  # 按排序字段升序展示

    def __str__(self):
        return f"{self.goods.name} - 图片{self.order}"

    # 序列化时返回完整图片URL
    @property
    def image_url(self):
        return f"http://localhost:8000{self.image.url}"

class Goods(models.Model):
    name = models.CharField('商品名称', max_length=100)
    brief_intro = models.CharField('简短介绍', max_length=200)
    intro = models.TextField('详细介绍')
    specs = models.TextField('规格参数', blank=True)
    original_price = models.DecimalField('原价', max_digits=10, decimal_places=2)
    member_price = models.DecimalField('会员价', max_digits=10, decimal_places=2)
    stock = models.IntegerField('库存', default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='所属分类')
    image = models.ImageField('商品主图', upload_to='goods/')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)
    is_star = models.BooleanField('是否明星产品', default=False)
    # 保留商品自身的积分兑换开关
    is_support_point_exchange = models.BooleanField(default=False, verbose_name="是否支持积分兑换")
    exchange_points = models.IntegerField(default=0, verbose_name="兑换所需积分（备用）")

    # 积分定价，自动计算
    point_price = models.DecimalField(
        "积分定价",
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="自动按会员价×100计算，无需手动填写"
    )

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        return f"http://localhost:8000{self.image.url}"

    # 【核心修改】简化save方法：仅基于商品自身的is_support_point_exchange判断
    def save(self, *args, **kwargs):
        # 1. 计算积分定价 = 会员价×100（强制整数）
        if self.member_price:
            self.point_price = int(self.member_price * 100)
        else:
            self.point_price = 0

        # 2. 仅基于商品自身的开关判断：不支持积分兑换则积分定价归零
        if not (self.is_support_point_exchange and self.point_price > 0):
            self.point_price = 0

        super().save(*args, **kwargs)

    # 【核心修改】简化积分兑换资格判断：仅判断商品自身开关+积分定价>0
    @property
    def can_point_exchange(self):
        return self.is_support_point_exchange and self.point_price > 0

    # 积分兑换计算逻辑（无修改，仅依赖简化后的can_point_exchange）
    def calculate_point_exchange(self, buy_num, user_points):
        if not self.can_point_exchange:
            return {
                "can_exchange": False,
                "msg": f"商品「{self.name}」不支持积分兑换",
                "need_point": 0,
                "actual_deduct_point": 0,
                "deduct_money": 0.0,
                "cash_pay": float(self.member_price * buy_num),
                "total_pay": float(self.member_price * buy_num)
            }

        single_point_price = int(self.point_price)
        total_need_point = single_point_price * buy_num
        actual_deduct_point = min(user_points, total_need_point)
        deduct_money = actual_deduct_point * 0.01
        total_money = float(self.member_price * buy_num)
        cash_pay = max(total_money - deduct_money, 0)

        return {
            "can_exchange": True,
            "msg": "积分兑换计算完成",
            "need_point": total_need_point,
            "actual_deduct_point": actual_deduct_point,
            "deduct_money": deduct_money,
            "cash_pay": cash_pay,
            "total_pay": deduct_money + cash_pay,
            "single_point_price": single_point_price,
            "total_money": total_money
        }

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
    duration_seconds = models.IntegerField(default=0, verbose_name="视频总时长(秒)")
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


# 恢复为稳定版本的 VideoWatchLog（无类型冲突）
# 务必确保导入在文件中正确位置（建议放在VideoCourse模型下方）
from django.db import models
from django.conf import settings
from django.utils import timezone  # 引入Django时区工具（适配时间字段）

# 视频观看日志模型（完整、无冲突版本）
class VideoWatchLog(models.Model):
    """视频观看日志：记录用户观看视频的全生命周期数据"""
    # 关联用户（使用settings.AUTH_USER_MODEL适配自定义User，避免硬编码）
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_watch_logs",  # 反向关联：user.video_watch_logs 查用户所有观看记录
        verbose_name="观看用户"
    )
    # 关联视频课程（外键关联VideoCourse，允许null/blank适配异常场景）
    video = models.ForeignKey(
        'VideoCourse',
        on_delete=models.CASCADE,
        related_name="watch_logs",  # 反向关联：video.watch_logs 查视频所有观看记录
        null=True,
        blank=True,
        verbose_name="关联视频课程"
    )
    # 核心时间字段
    watch_start = models.DateTimeField(
        default=timezone.now,  # 默认当前时间，兼容手动创建场景
        verbose_name="开始观看时间"
    )
    watch_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="结束观看时间"  # 视频播放完成/用户退出时更新
    )
    # 播放数据字段
    total_watch_sec = models.IntegerField(
        default=0,
        verbose_name="累计观看秒数"  # 记录用户实际观看时长
    )
    last_progress_sec = models.IntegerField(
        default=0,
        verbose_name="最后上报进度（秒）"  # 新增：适配前端进度上报，避免重复统计
    )
    is_finished = models.BooleanField(
        default=False,
        verbose_name="是否完整观看"  # 累计时长≥视频总时长则标记为True
    )
    point_given = models.BooleanField(
        default=False,
        verbose_name="是否已发放积分"
    )

    class Meta:
        verbose_name = "视频观看日志"
        verbose_name_plural = "视频观看日志"
        # 唯一约束：同一用户对同一视频仅保留一条有效观看记录（按业务需求调整）
        unique_together = ('user', 'video')
        # 排序：按开始观看时间倒序，最新记录在前
        ordering = ['-watch_start']
        # 索引：优化查询（用户+视频、开始时间）
        indexes = [
            models.Index(fields=['user', 'video']),
            models.Index(fields=['watch_start']),
        ]

    def __str__(self):
        """友好的字符串展示，避免video为null时报错"""
        video_title = self.video.title if self.video else "未知视频"
        user_name = getattr(self.user, 'nickname', self.user.username)  # 兼容nickname/用户名
        return f"{user_name} - {video_title} - {self.watch_start.strftime('%Y-%m-%d %H:%M')}"

    # 新增：快捷方法 - 计算实际观看时长（秒）
    @property
    def watch_duration_sec(self):
        """返回用户实际观看时长（秒），未结束则计算到当前时间"""
        if self.watch_end:
            return int((self.watch_end - self.watch_start).total_seconds())
        else:
            return int((timezone.now() - self.watch_start).total_seconds())

    # 新增：更新观看完成状态（适配业务逻辑）
    def update_finished_status(self, video_total_sec):
        """
        根据累计观看时长更新是否完整观看
        :param video_total_sec: 视频总时长（秒）
        """
        if self.total_watch_sec >= video_total_sec:
            self.is_finished = True
            self.watch_end = self.watch_end or timezone.now()  # 未设置结束时间则补全
            self.save(update_fields=['is_finished', 'watch_end'])

# app01/models.py
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import random
import string

class PointsRecord(models.Model):
    """会员积分变动记录（注册/消费/观看视频均生成记录）"""
    # 积分类型：和三大送分场景严格对应，预留扩展
    POINTS_TYPE_CHOICES = (
        (1, '注册赠送'),
        (2, '消费赠送'),  # 订单支付成功
        (3, '观看视频赠送'),
        (4, '打卡赠送'),  # 预留：学习打卡
        (5, '活动赠送'),  # 预留：营销活动
    )
    # 外键指向自定义User模型，级联删除
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_records',
        verbose_name='所属会员'
    )
    points = models.IntegerField(verbose_name='积分值', help_text='正整数=增加，负整数=扣除（暂仅用增加）')
    points_type = models.IntegerField(choices=POINTS_TYPE_CHOICES, verbose_name='积分类型')
    related_id = models.CharField(max_length=64, blank=True, null=True, verbose_name='关联业务ID', help_text='消费=订单号，视频=视频ID，注册=空')
    description = models.CharField(max_length=256, blank=True, null=True, verbose_name='变动描述', help_text='前端展示用，如「消费100元赠10分」')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='变动时间')

    class Meta:
        verbose_name = '会员积分记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']  # 按时间倒序展示
        # 联合索引：核心防重复赠送（同一用户+同一场景+同一业务ID，仅能送1次）
        indexes = [
            models.Index(fields=['user', 'points_type', 'related_id']),
        ]

    def __str__(self):
        return f"{self.user.nickname}-{self.get_points_type_display()}-{self.points}分"

import logging  # 必须导入logging（模型里没导入会触发新错误）
logger = logging.getLogger(__name__)  # 定义logger
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
    coupon_count = models.IntegerField(default=0, verbose_name="优惠量")
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
            # 🔥 关键修改：新增 select_related('address') 关联地址字段
            orders = Order.objects.filter(
                user=sub_user,
                status__in=[1, 2, 3]  # 仅查询有效订单（待付款/待发货/已发货）
            ).select_related('address').order_by('-create_time').prefetch_related('items')  # 保留原有预加载

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

    # 在你的User模型中补充/修复add_points方法
    def add_points(self, points, points_type, related_id="", related_desc=""):
        """
        添加/扣减用户积分
        :param points: 积分值（正数=增加，负数=扣减）
        :param points_type: 积分类型（1=注册，2=消费，3=视频奖励，4=抵扣，5=其他）
        :param related_id: 关联ID（如订单号）
        :param related_desc: 描述（兼容原有参数名，内部映射到description字段）
        :return: (success: bool, msg: str)
        """
        try:
            # 转换为整数，避免浮点问题
            points = int(points)
            current_points = self.points or 0

            # 扣减积分时（points为负），校验积分是否充足
            if points < 0:
                deduct_points = abs(points)
                if current_points < deduct_points:
                    return False, f"积分不足（当前{current_points}分，需扣减{deduct_points}分）"

            # 更新积分（支持正负）
            self.points = current_points + points
            # 确保积分不会为负数
            if self.points < 0:
                self.points = 0
            self.save(update_fields=["points"])

            # 记录积分变动（关键修复：参数名从related_desc改为description）
            from .models import PointsRecord
            PointsRecord.objects.create(
                user=self,
                points=points,  # 保留正负，便于区分增减
                points_type=points_type,
                related_id=related_id,
                # 🔥 核心修复：参数名从 related_desc 改为 description
                description=related_desc,
                create_time=timezone.now()
            )

            return True, f"积分{'增加' if points > 0 else '扣减'}成功（{points}分）"
        except Exception as e:
            return False, f"积分操作失败：{str(e)}"

    def get_coupons(self, only_valid=False, coupon_type=None):
        """
        查询用户的优惠券
        :param only_valid: 是否仅返回可用优惠券（未使用+未过期）
        :param coupon_type: 筛选类型（1=代金券，2=折扣券）
        :return: UserCoupon查询集
        """
        queryset = self.user_coupons.all().select_related("coupon")  # 预加载优惠券模板，提升性能

        # 筛选可用优惠券
        if only_valid:
            queryset = queryset.filter(is_used=False).filter(end_time__gt=timezone.now())

        # 筛选优惠券类型
        if coupon_type in [1, 2]:
            queryset = queryset.filter(coupon__coupon_type=coupon_type)

        return queryset

    def get_coupon_stats(self):
        """获取用户优惠券统计（总数/可用数/过期数/已使用数）"""
        all_coupons = self.user_coupons.all()
        valid_coupons = self.get_coupons(only_valid=True)
        expired_coupons = all_coupons.filter(is_used=False, end_time__lt=timezone.now())
        used_coupons = all_coupons.filter(is_used=True)

        return {
            "total": all_coupons.count(),
            "valid": valid_coupons.count(),
            "expired": expired_coupons.count(),
            "used": used_coupons.count()
        }

    def exchange_goods_by_point(self, goods, buy_num=1):
        """用户积分兑换商品计算，带严格分类校验"""
        if not goods.can_point_exchange:
            return {
                "success": False,
                "msg": f"商品「{goods.name}」不支持积分兑换（非积分兑换分类）",
                "data": None
            }

        exchange_detail = goods.calculate_point_exchange(buy_num, self.points)
        exchange_detail.update({
            "user_points": self.points,
            "points_shortage": max(exchange_detail["need_point"] - self.points, 0),
            "points_shortage_money": exchange_detail["points_shortage"] * 0.01
        })

        return {
            "success": True,
            "msg": "积分兑换计算完成",
            "data": exchange_detail
        }

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
        return f"{self.name} - {self.address}{self.detail}"

import logging
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal  # 补充Decimal导入（计算积分抵扣金额用）

# 定义logger（解决deduct_user_points方法中logger未定义问题）
logger = logging.getLogger(__name__)

class Order(models.Model):
    ORDER_STATUS = (
        (0, "待付款"),
        (1, "待发货"),  # 快递专用：待发货；到店专用：待取货（通过方法动态替换）
        (2, "待收货"),  # 仅快递专用
        (3, "已完成"),
        (4, "已取消"),
    )
    # 到店自取专用状态映射（覆盖原状态名）
    PICK_UP_STATUS_MAP = {
        0: "待付款",
        1: "待取货",  # 把原“待发货”替换为“待取货”
        3: "已完成",
        4: "已取消",
    }

    DELIVERY_TYPE_CHOICES = (
        (1, "快递上门"),
        (2, "到店自取"),
    )
    # 原有核心字段保留
    user = models.ForeignKey('User', on_delete=models.CASCADE, verbose_name="用户")
    order_sn = models.CharField(max_length=64, unique=True, verbose_name="订单编号")
    goods_names = models.CharField(max_length=500, null=True, blank=True, verbose_name="订单产品名称（拼接）")
    goods_count = models.IntegerField(default=0, verbose_name="订单商品总数")
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="收货地址")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总价")
    status = models.IntegerField(choices=ORDER_STATUS, default=0, verbose_name="订单状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_point_deducted = models.BooleanField(default=False, verbose_name="积分是否已扣减")

    # ========== 新增配送相关字段 ==========
    delivery_type = models.IntegerField(
        choices=DELIVERY_TYPE_CHOICES,
        default=1,  # 默认快递上门
        verbose_name="配送方式"
    )
    pick_up_store = models.ForeignKey(
        'Area',  # 关联门店表
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="取货门店"
    )

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

    # ========== 【核心修复1】修复积分抵扣字段的verbose_name重复问题 ==========
    point_deduct = models.IntegerField(default=0, verbose_name="抵扣积分")  # 移除重复的位置参数'抵扣积分'
    point_deduct_money = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),  # 改用Decimal('0.00')更规范，避免浮点精度问题
        verbose_name="积分抵扣金额"
    )  # 移除重复的位置参数'积分抵扣金额'
    actual_pay_money = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="实际支付金额"
    )

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.order_sn} - {self.get_status_display()}"

    def get_status_name(self):
        """根据配送类型，返回对应的状态名称"""
        if self.delivery_type == 2:
            return self.PICK_UP_STATUS_MAP.get(self.status, f"未知状态({self.status})")
        else:
            return self.get_status_display()

    def clean(self):
        # 到店自取订单，禁止设置状态2（待收货）
        if self.delivery_type == 2 and self.status == 2:
            raise ValidationError("到店自取订单不支持「待收货」状态")
        # 到店自取订单，仅允许状态：0/1/3/4
        if self.delivery_type == 2 and self.status not in [0, 1, 3, 4]:
            raise ValidationError("到店自取订单仅支持状态：待付款(0)、待取货(1)、已完成(3)、已取消(4)")

    def save(self, *args, **kwargs):
        self.clean()  # 保存前校验状态合法性
        is_new = self.pk is None

        # 第一步：先调用父类save生成主键（关键！）
        super().save(*args, **kwargs)

        # 第二步：只有订单已保存（有主键），才处理商品名称和数量统计
        if not is_new and hasattr(self, 'items') and self.items.exists():
            self.goods_names = "、".join([item.goods_name for item in self.items.all()])
            self.goods_count = sum([item.num for item in self.items.all()])
            super().save(update_fields=['goods_names', 'goods_count'])

    @property
    def goods_names_str(self):
        """返回订单商品名称拼接字符串"""
        if self.goods_names:
            return self.goods_names
        if self.pk and hasattr(self, 'items') and self.items.exists():
            return "、".join([item.goods_name for item in self.items.all()])
        return "无商品"

    @property
    def goods_list(self):
        """返回订单商品详情列表"""
        if self.pk and hasattr(self, 'items') and self.items.exists():
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

    @property
    def status_display(self):
        return self.get_status_name()

    def deduct_user_points(self, user, deduct_point, goods_list):
        """
        积分抵扣核心方法（支付成功后调用）
        新增幂等性校验：已扣减则直接返回成功
        """
        from django.db import transaction

        # 1. 幂等性校验：已扣过积分则直接返回成功
        if self.is_point_deducted:
            return True, "该订单积分已扣减，无需重复操作"

        # 2. 二次校验：订单状态必须是已支付（待发货/待收货/已完成），避免未支付扣积分
        if self.status not in [1, 2, 3]:
            return False, f"订单状态异常（当前状态：{self.get_status_display()}），仅已支付订单可扣减积分"

        # 3. 原有校验逻辑（保留）
        for goods in goods_list:
            if not hasattr(goods, 'can_point_exchange') or not goods.can_point_exchange:
                return False, f"订单包含非积分兑换商品「{goods.name}」，无法使用积分抵扣"

        if deduct_point <= 0:
            return True, "无需积分抵扣"

        if not hasattr(user, 'points') or user.points < deduct_point:
            current_points = getattr(user, 'points', 0)
            return False, f"积分不足：当前{current_points}分，需{deduct_point}分"

        try:
            with transaction.atomic():
                # 1. 扣减用户积分
                user.points -= deduct_point
                user.save(update_fields=['points'])

                # 2. 记录积分变动
                from .models import PointsRecord
                PointsRecord.objects.create(
                    user=user,
                    points=-deduct_point,
                    points_type=4,
                    related_id=self.order_sn,
                    description=f"订单{self.order_sn}抵扣{deduct_point}积分(抵扣{deduct_point * 0.01}元)"
                )

                # 3. 更新订单字段（新增：标记积分已扣减）
                self.point_deduct = deduct_point
                self.point_deduct_money = Decimal(str(deduct_point * 0.01))
                self.actual_pay_money = max(self.total_price - self.point_deduct_money, Decimal('0.00'))
                self.is_point_deducted = True  # 标记已扣减
                self.save(update_fields=['point_deduct', 'point_deduct_money', 'actual_pay_money', 'is_point_deducted'])

            return True, f"成功抵扣{deduct_point}积分（抵扣{self.point_deduct_money}元）"

        except Exception as e:
            logger.error(f"订单{self.order_sn}积分抵扣失败：{str(e)}", exc_info=True)
            error_msg = str(e)[:20] if len(str(e)) > 20 else str(e)
            return False, f"积分抵扣失败：{error_msg}"

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


import datetime

class Coupon(models.Model):
    """优惠券模板模型（定义优惠券规则，不直接关联用户）"""
    # 优惠券类型
    COUPON_TYPE_CHOICES = (
        (1, "代金券"),  # 直接抵扣金额
        (2, "折扣券"),  # 按折扣系数计算
    )
    title = models.CharField(max_length=64, verbose_name="优惠券名称")
    coupon_type = models.IntegerField(choices=COUPON_TYPE_CHOICES, default=1, verbose_name="优惠券类型")

    # 代金券专属字段
    money = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="抵扣金额（元）")

    # 折扣券专属字段（0.1-0.99，如0.9=9折）
    discount_rate = models.DecimalField(max_digits=3, decimal_places=2, default=1.00, verbose_name="折扣系数")

    # 通用使用规则
    min_consume = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="最低使用门槛（元）")
    valid_days = models.IntegerField(default=90, verbose_name="有效期天数")  # 领取后N天有效
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "优惠券模板"
        verbose_name_plural = verbose_name

    def __str__(self):
        if self.coupon_type == 1:
            return f"{self.title} - 代金券{self.money}元"
        else:
            return f"{self.title} - {self.discount_rate * 10}折券"


class UserCoupon(models.Model):
    """用户持有的优惠券（关联用户和优惠券模板）"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_coupons",
                             verbose_name="所属用户")
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="user_coupons", verbose_name="优惠券模板")

    # 核心状态字段
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="领取时间")
    end_time = models.DateTimeField(verbose_name="过期时间")  # 自动计算：start_time + valid_days
    is_used = models.BooleanField(default=False, verbose_name="是否已使用")
    used_time = models.DateTimeField(null=True, blank=True, verbose_name="使用时间")
    order_sn = models.CharField(max_length=64, null=True, blank=True, verbose_name="关联订单号")  # 关联使用的订单

    class Meta:
        verbose_name = "用户优惠券"
        verbose_name_plural = verbose_name
        ordering = ["-start_time"]

    def __str__(self):
        status = "已使用" if self.is_used else ("已过期" if self.is_expired else "未使用")
        return f"{self.user.nickname} - {self.coupon.title} - {status}"

    def save(self, *args, **kwargs):
        # 自动计算过期时间（领取时间 + 模板的有效期天数）
        if not self.end_time:
            self.end_time = self.start_time + datetime.timedelta(days=self.coupon.valid_days)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """判断优惠券是否过期"""
        return timezone.now() > self.end_time

    @property
    def is_valid(self):
        """判断优惠券是否可用（未使用+未过期）"""
        return not self.is_used and not self.is_expired


# 快递物流轨迹模型（关联Order，记录每一条物流节点）
class ExpressLogistics(models.Model):
    """
    快递物流轨迹模型
    关联订单号，记录运单号、物流时间、地点、状态、派件人信息等
    一个订单可对应多条物流轨迹（如揽收、中转、派送、签收）
    """
    # 关联订单（核心外键，确保和订单主表关联）
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="express_logistics",
        verbose_name="关联订单"
    )
    # 冗余存储订单号（方便快速查询，无需关联Order表）
    order_sn = models.CharField(max_length=64, verbose_name="订单编号")

    # 物流核心字段
    logistics_no = models.CharField(max_length=64, verbose_name="运单号")  # 顺丰/圆通等运单号
    logistics_company = models.CharField(max_length=32, null=True, blank=True, verbose_name="物流公司")  # 如：顺丰速运

    # 物流轨迹节点信息
    logistics_time = models.DateTimeField(verbose_name="物流节点时间")  # 该节点的发生时间（如2025-10-02 19:10:44）
    accept_address = models.CharField(max_length=100, verbose_name="货物地点")  # 如：苏州市/杭州市
    # 物流状态（和顺丰接口状态对齐，覆盖核心场景）
    LOGISTICS_STATUS_CHOICES = (
        (101, "已揽收"),
        (201, "运送中"),
        (301, "派送中"),
        (401, "已签收"),
        (501, "已取消"),
        (601, "异常件"),
    )
    logistics_status = models.IntegerField(
        choices=LOGISTICS_STATUS_CHOICES,
        verbose_name="物流状态"
    )
    logistics_status_name = models.CharField(max_length=32, verbose_name="物流状态名称",
                                             help_text="冗余存储状态名称，如：已揽收/派送中")

    # 派件人信息（仅派送/签收节点有值）
    courier_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="派件人姓名")  # 如：杜保奎
    courier_phone = models.CharField(max_length=11, null=True, blank=True,
                                     verbose_name="派件人联系电话")  # 如：18358192592

    # 扩展字段
    remark = models.CharField(max_length=500, null=True, blank=True, verbose_name="物流备注")  # 如：快件已放在家门口
    sort = models.IntegerField(default=0, verbose_name="轨迹排序")  # 按时间正序排列轨迹
    is_delete = models.BooleanField(default=False, verbose_name="是否删除")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "快递物流轨迹"
        verbose_name_plural = "快递物流轨迹"
        # 核心修改：先按物流时间正序（asc），再按sort正序
        ordering = ["-logistics_time", "-sort"]
        indexes = [
            models.Index(fields=["order_sn"]),
            models.Index(fields=["logistics_no"]),
            # 新增：按物流时间索引，提升排序查询效率
            models.Index(fields=["logistics_time"]),
        ]

    def __str__(self):
        return f"{self.order_sn} - {self.logistics_no} - {self.logistics_status_name} - {self.accept_address}"

    # 重写save方法：自动同步订单号、状态名称
    def save(self, *args, **kwargs):
        # 1. 自动从关联订单同步order_sn
        if self.order and not self.order_sn:
            self.order_sn = self.order.order_sn
        # 2. 自动同步物流状态名称（从choices中获取）
        if self.logistics_status and not self.logistics_status_name:
            status_map = dict(self.LOGISTICS_STATUS_CHOICES)
            self.logistics_status_name = status_map.get(self.logistics_status, "未知状态")
        # 3. 同步到Order主表的物流单号（保持数据一致）
        if self.logistics_no and self.order and not self.order.logistics_no:
            self.order.logistics_no = self.logistics_no
            self.order.logistics_company = self.logistics_company
            self.order.save(update_fields=["logistics_no", "logistics_company"])
        super().save(*args, **kwargs)

    # 快捷属性：获取易读的物流状态
    @property
    def status_text(self):
        """返回友好的物流状态文本"""
        return self.get_logistics_status_display()

SF_STATUS_MAP = {
    "已揽收": 101,
    "运送中": 201,
    "派送中": 301,
    "已签收": 401,
    "已取消": 501,
    "异常件": 601,
}
# 反向映射（用于快速获取状态名称）
STATUS_NAME_MAP = {v: k for k, v in SF_STATUS_MAP.items()}
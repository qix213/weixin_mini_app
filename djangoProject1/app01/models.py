import uuid

from django.db import models
from decimal import Decimal
from django.conf import settings

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
    is_delete = models.BooleanField(default=False, verbose_name='是否隐藏')
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

class MemberPrivilege(models.Model):
    title = models.CharField(max_length=50, verbose_name="标题", default="会员权益长图")
    # 图片会保存在 media/privilege/ 目录下
    image = models.ImageField(upload_to='privilege/', verbose_name="权益图片")
    is_active = models.BooleanField(default=True, verbose_name="是否启用当前图")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "会员权益配置"
        verbose_name_plural = verbose_name
        # 默认按照更新时间倒序，确保取到最新配置的图
        ordering = ['-update_time']

    def __str__(self):
        status = "【使用中】" if self.is_active else "【已停用】"
        return f"{status} {self.title}"

class OfflineCertification(models.Model):
    title = models.CharField(max_length=50, verbose_name="标题", default="线下认证长图")
    # 图片会保存在 media/certification/ 目录下
    image = models.ImageField(upload_to='certification/', verbose_name="认证图片")
    is_active = models.BooleanField(default=True, verbose_name="是否启用当前图")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "线下认证配置"
        verbose_name_plural = verbose_name
        ordering = ['-update_time']

    def __str__(self):
        status = "【使用中】" if self.is_active else "【已停用】"
        return f"{status} {self.title}"

class UserInfo(models.Model):
    """
    【门店负责人表】
    这里通常是具体的“店长”或“现场合伙人”微型档案，属于具体的自然人。
    """
    name = models.CharField(max_length=32, verbose_name='姓名')
    avatar = models.FileField(upload_to='avatar/', max_length=128, verbose_name='头像')  # 修正拼写 avator -> avatar
    create_time = models.DateTimeField(auto_now=True, verbose_name='创建日期')

    class Meta:
        verbose_name = '门店负责人'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Area(models.Model):
    """
    【门店/线下项目表】
    """
    name = models.CharField(max_length=32, verbose_name='门店全名')
    desc = models.CharField(max_length=32, verbose_name='门店简称')

    # 🌟 1. 线下项目由谁管？关联原来的店长/负责人
    user = models.ForeignKey(
        to='UserInfo',
        on_delete=models.SET_NULL,  # 负责人离职，门店不至于被连带级联删除
        null=True,
        blank=True,
        verbose_name='门店负责人'
    )

    # 🌟 2. 核心联动：这个门店在经济上归属于 Ta创+ 的哪家企业账户？
    # 这样就彻底把 门店 -> 企业 -> Ta创+ 串联起来了！
    enterprise = models.ForeignKey(
        to='EnterpriseProfile',
        on_delete=models.PROTECT,  # 只要企业下面还有门店在营业，就保护起来不准删企业
        null=True,
        blank=True,
        related_name='stores',
        verbose_name='归属企业账户'
    )

    # 🌟 3. 双保险打桩：直接挂载所属的顶级 Ta创+ 老板
    # 这样做是为了能让 Ta创+ 在工作台里一键 .filter(belong_to_boss=request.user) 查到所有门店
    belong_to_boss = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='my_offline_stores',
        verbose_name='所属Ta创+大老板'
    )

    class Meta:
        verbose_name = '门店表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 商品分类
class Category(models.Model):
    name = models.CharField('分类名称', max_length=50)
    icon = models.FileField(upload_to='icon', max_length=128, verbose_name='分类图标')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    sort_order = models.IntegerField(
        '排序序号',
        default=0,
        help_text='数字越小越靠前（例如：1排在前面，99排在后面）'
    )

    class Meta:
        verbose_name = '商品分类'
        ordering = ['sort_order', 'id']
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

# 原有Goods模型保持不变，新增GoodsImage模型存储多组介绍图

class GoodsImage(models.Model):
    """商品多媒体模型（关联主商品，支持图片与视频）"""

    MEDIA_CHOICES = (
        (0, '图片'),
        (1, '视频'),
    )

    goods = models.ForeignKey(
        'Goods',
        on_delete=models.CASCADE,
        related_name='images',  # 保持旧名称兼容现有查询，如 goods.images.all()
        verbose_name='所属商品'
    )

    # 新增：区分当前记录是图片还是视频
    media_type = models.SmallIntegerField('媒体类型', choices=MEDIA_CHOICES, default=0)

    # 修改：改为非必填（null=True, blank=True），因为传视频时没有图
    image = models.ImageField('商品图片', upload_to='goods/images/', null=True, blank=True)

    # 新增：视频文件字段
    video = models.FileField('商品视频', upload_to='goods/videos/', null=True, blank=True)

    order = models.IntegerField('排序', default=0)
    create_time = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '商品媒体(图/视频)'
        verbose_name_plural = verbose_name
        ordering = ['order']

    def __str__(self):
        media_name = self.get_media_type_display()
        return f"{self.goods.name} - {media_name}{self.order}"

    # 新增数据校验：确保不会同时为空或传错类型
    def clean(self):
        if not self.image and not self.video:
            raise ValidationError("必须上传一张图片或一个视频！")
        if self.media_type == 0 and not self.image:
            raise ValidationError("媒体类型选择了【图片】，但未上传图片！")
        if self.media_type == 1 and not self.video:
            raise ValidationError("媒体类型选择了【视频】，但未上传视频！")

    @property
    def image_url(self):
        if self.image:
            return f"{settings.SERVER_BASE_URL}{self.image.url}"
        return ""

    @property
    def video_url(self):
        if self.video:
            return f"{settings.SERVER_BASE_URL}{self.video.url}"
        return ""

    # 新增：提供一个统一的对外 URL 属性，前端在渲染列表时直接取这个值最省事
    @property
    def media_url(self):
        return self.video_url if self.media_type == 1 else self.image_url

class Goods(models.Model):
    GOODS_TYPE_CHOICES = (
        (1, '居家产品'),
        (2, '线下项目'),
        (3, '京东物流'),
    )
    goods_type = models.SmallIntegerField('商品/项目类型', choices=GOODS_TYPE_CHOICES, default=1)
    service_times = models.IntegerField('项目包含次数', default=1, help_text='仅对线下项目有效，买一次包含几次服务')
    name = models.CharField('商品名称', max_length=100)
    brief_intro = models.TextField('核心成分', max_length=200, blank=True)
    intro = models.TextField('详细介绍')
    fuc = models.CharField('产品功效')
    method = models.TextField('使用方法')
    specs = models.CharField('适合肤质', blank=True)
    qualification = models.CharField('产品规格(g/ml)', blank=True)
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
    weight = models.DecimalField(
        max_digits=8, decimal_places=2, default=1.00,
        verbose_name="商品重量(g/瓶)", help_text="用于京东物流计费计算"
    )
    volume = models.DecimalField(
        max_digits=8, decimal_places=2, default=1.00,
        verbose_name="商品体积(ml/瓶)", help_text="用于京东物流计费计算"
    )
    # 积分定价，自动计算
    point_price = models.DecimalField(
        "积分定价",
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="自动按会员价×100计算，无需手动填写"
    )
    sort_order = models.IntegerField(
        '排序序号',
        default=0,
        help_text='数字越小越靠前'
    )
    class Meta:
        verbose_name = '商品'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-update_time']

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        return f"{settings.SERVER_BASE_URL}{self.image.url}"

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

class UserOfflineProject(models.Model):
    """
    用户线下项目资产表（记录谁买了什么，总共几次，还剩几次）
    """
    STATUS_CHOICES = (
        (0, '已预约_待到店'),  # 🌟 新增状态0：店长刚选好预约时间
        (1, '核销中_待确认'),  # 🌟 原来的状态0变成了状态1
        (2, '已完成'),  # 🌟 原来的状态1变成了状态2
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offline_projects', verbose_name="客户")
    project = models.ForeignKey('Goods', on_delete=models.CASCADE, verbose_name="线下项目")
    appointment_time = models.DateTimeField('预约到店时间', null=True, blank=True)
    status = models.SmallIntegerField('状态', choices=STATUS_CHOICES, default=0)
    total_times = models.IntegerField('总次数', default=0)
    remain_times = models.IntegerField('剩余次数', default=0)

    create_time = models.DateTimeField('获取时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '线下项目资产'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user} - {self.project.name} (剩 {self.remain_times} 次)"

class OfflineServiceRecord(models.Model):
    """
    线下服务核销与评价记录表（每一次到店服务，都会生成一条记录）
    """
    # 🌟 核心修改 1：扩充状态轴，匹配现在的三段式业务流
    STATUS_CHOICES = (
        (0, '已预约_待到店'),
        (1, '核销中_待确认'),
        (2, '已完成'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='service_records', on_delete=models.CASCADE, verbose_name="客户")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='managed_records', on_delete=models.SET_NULL, null=True, verbose_name="服务店长")
    project = models.ForeignKey('Goods', on_delete=models.CASCADE, verbose_name="服务项目")

    status = models.SmallIntegerField('状态', choices=STATUS_CHOICES, default=0)

    # 🌟 核心修改 2：新增预约时间字段
    appointment_time = models.DateTimeField('预约到店时间', null=True, blank=True)

    # 评价相关（全部允许为空，非强制）
    rating = models.SmallIntegerField('星级打分', null=True, blank=True, help_text="1-5星")
    review_content = models.TextField('评价文字', null=True, blank=True)
    review_images = models.JSONField('评价图片', null=True, blank=True, help_text="存储图片URL列表，如 ['url1', 'url2']")

    # 时间追踪
    create_time = models.DateTimeField('店长发起时间', auto_now_add=True)
    confirm_time = models.DateTimeField('客户确认时间', null=True, blank=True)
    review_time = models.DateTimeField('评价提交时间', null=True, blank=True)

    class Meta:
        verbose_name = '服务与评价记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        # 🌟 优化显示，直接调取状态名
        return f"{self.user} - {self.project.name} - {self.get_status_display()}"

# 视频课程模型
class CourseCategory(models.Model):
    name = models.CharField(max_length=50, verbose_name="分类名称", unique=True)
    sort_order = models.IntegerField(default=0, verbose_name="排序(从小到大)")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "视频分类"
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-create_time']

    def __str__(self):
        return self.name

class VideoCourse(models.Model):
    title = models.CharField(max_length=100, verbose_name="课程标题")
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="所属分类")
    cover_url = models.ImageField(upload_to='course/cover/', verbose_name="封面图片")

    # 🌟 核心修改：变成普通文本字段，只存相对路径
    video_url = models.CharField(
        max_length=255,
        verbose_name="视频播放路径",
        help_text="请填入专属视频服务器下的相对路径，例如：/rspf/rspf1/output_rspf1.m3u8"
    )

    duration = models.IntegerField(default=10, verbose_name="视频时长")
    play_count = models.IntegerField(default=0, verbose_name="播放次数")
    desc = models.TextField(blank=True, null=True, verbose_name="课程描述")
    is_publish = models.BooleanField(default=True, verbose_name="是否发布")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    sort_order = models.PositiveIntegerField(
        default=1,
        verbose_name="视频序号/集数",
        help_text="前端会按此数字从小到大正序排列（如 1, 2, 3...）"
    )
    class Meta:
        verbose_name = "视频课程"
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.title

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

class PointsRecord(models.Model):
    """会员积分变动记录（注册/消费/观看视频均生成记录）"""
    POINTS_TYPE_CHOICES = (
        (1, '注册赠送'),
        (2, '消费赠送'),  # 订单支付成功
        (3, '观看视频赠送'),
        (4, '抵扣消费'),  # 积分扣除
        (5, '系统扣除/过期'),  # 积分过期清理
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_records',
                             verbose_name='所属会员')
    points = models.IntegerField(verbose_name='积分值', help_text='正整数=增加，负整数=扣除')

    # ================= 🚀 新增：积分过期与消耗管理 =================
    available_points = models.IntegerField(default=0, verbose_name='剩余可用积分',
                                           help_text='该笔积分还剩多少没被花掉（先进先出扣减）')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='过期时间', help_text='自获取起12个月后过期')
    # =========================================================

    points_type = models.IntegerField(choices=POINTS_TYPE_CHOICES, verbose_name='积分类型')
    related_id = models.CharField(max_length=64, blank=True, null=True, verbose_name='关联业务ID',
                                  help_text='消费=订单号，视频=视频ID，注册=空')
    description = models.CharField(max_length=256, blank=True, null=True, verbose_name='变动描述',
                                   help_text='前端展示用，如「消费100元赠10分」')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='变动时间')

    class Meta:
        verbose_name = '会员积分记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        indexes = [
            models.Index(fields=['user', 'points_type', 'related_id']),
            models.Index(fields=['expire_time']),  # 加快过期清理的查询速度
        ]

    def __str__(self):
        return f"{self.user.nickname}-{self.get_points_type_display()}-{self.points}分"

import logging  # 必须导入logging（模型里没导入会触发新错误）
logger = logging.getLogger(__name__)  # 定义logger

import random
import string
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone


class User(AbstractUser):
    # ================= 🌟 基础业务字段 =================
    # 🌟 核心更新：扩展为 7 档会员体系
    USER_TYPE_CHOICES = (
        (1, "蓝朋友"),  # 0元
        (2, "蓝朋友1星"),  # 980元
        (3, "蓝朋友2星"),  # 1980元
        (4, "蓝朋友3星"),  # 3800元
        (5, "蓝朋友4星"),  # 9800元
        (6, "蓝朋友5星"),  # 39800元
        (7, "Ta创+"),  # 98000元
    )
    user_type = models.IntegerField(choices=USER_TYPE_CHOICES, null=True, blank=True, verbose_name="会员等级")
    can_use_ai = models.BooleanField(default=False, verbose_name="允许使用智能蓝博士")
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name="会籍到期时间")
    withdrawable_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="可提现余额")
    frozen_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                         verbose_name="冻结中余额（提现中）")
    # 会员ID：8位数字+字母，自动生成
    member_id = models.CharField(
        max_length=8, unique=True, blank=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]{8}$', '会员ID必须是8位数字或字母')],
        verbose_name="会员ID"
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="用户头像")
    nickname = models.CharField(max_length=50, verbose_name="昵称", unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=11, validators=[RegexValidator(r'^1[3-9]\d{9}$', '手机号格式错误')],
        verbose_name="手机号", null=True, blank=True
    )

    # ================= 🌟 新增：微信身份绑定字段 =================
    openid = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name="微信OpenID")

    email = models.EmailField(verbose_name="邮箱", null=True, blank=True)
    province = models.CharField(max_length=20, verbose_name="省份", null=True, blank=True)
    city = models.CharField(max_length=20, verbose_name="城市", null=True, blank=True)
    district = models.CharField(max_length=20, verbose_name="区县", null=True, blank=True)

    # 推荐人关联：外键指向自身（上级会员）
    parent_user = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='sub_users', verbose_name="上级会员")
    root_enterprise = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                        limit_choices_to={'user_type': 7},  # 🌟 核心更新：限制归属为顶级 7 (Ta创+)
                                        related_name='all_downline_users',
                                        verbose_name="归属的Ta创+(算发货用)")

    points = models.IntegerField(default=0, verbose_name="积分余额")
    coupon_count = models.IntegerField(default=0, verbose_name="优惠券数量")
    star_level = models.IntegerField(default=1, verbose_name="星级（1-5星）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="注册时间")

    # ================= 🚀 生日权益与限制字段 =================
    birth_date = models.DateField(verbose_name="出生日期", null=True, blank=True)
    last_birth_date_modify = models.DateTimeField(null=True, blank=True, verbose_name="生日最后修改时间")

    # ================= 🔒 Django 权限组防冲突配置 =================
    groups = models.ManyToManyField(
        'auth.Group', verbose_name='groups', blank=True,
        related_name='app01_user_groups', related_query_name='app01_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', verbose_name='user permissions', blank=True,
        related_name='app01_user_permissions', related_query_name='app01_user'
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        type_display = self.get_user_type_display() or "普通用户"
        return f"{type_display}-{self.member_id}"

    # ==============================================================
    #                   一、生命周期钩子方法
    # ==============================================================
    def save(self, *args, **kwargs):
        """保存时自动生成唯一的 8 位 member_id"""
        if not self.member_id:
            chars = string.ascii_uppercase + string.digits
            while True:
                member_id = ''.join(random.choice(chars) for _ in range(8))
                if not User.objects.filter(member_id=member_id).exists():
                    self.member_id = member_id
                    break
        super().save(*args, **kwargs)

    # ==============================================================
    #                   二、生日与积分流转中枢
    # ==============================================================
    def update_birth_date(self, new_date):
        """修改生日，限制一年只能改一次"""
        if self.last_birth_date_modify:
            days_since_last_modify = (timezone.now() - self.last_birth_date_modify).days
            if days_since_last_modify < 365:
                return False, f"生日一年内仅可修改一次（距离解禁还剩 {365 - days_since_last_modify} 天）"

        self.birth_date = new_date
        self.last_birth_date_modify = timezone.now()
        self.save(update_fields=['birth_date', 'last_birth_date_modify'])
        return True, "生日修改成功"

    def issue_birthday_coupon(self):
        """下发生日当月专属 200 元代金券（每年限领一张）"""
        if not self.birth_date or self.birth_date.month != timezone.now().month:
            return False, "宝贝，还没到您的生日月哦～"

        current_year = timezone.now().year
        # 校验今年是否已经发过（防刷）
        has_issued = self.user_coupons.filter(
            coupon__title__contains="生日专属",
            start_time__year=current_year
        ).exists()

        if has_issued:
            return False, "您今年的生日礼遇已经领取过了哦～"

        from .models import Coupon, UserCoupon
        coupon_template, _ = Coupon.objects.get_or_create(
            title="生日专属200元代金券",
            defaults={
                'coupon_type': 1, 'money': 200.00, 'discount_rate': 1.00,
                'min_consume': 0.00, 'valid_days': 30, 'is_active': True
            }
        )

        UserCoupon.objects.create(
            user=self,
            coupon=coupon_template,
            start_time=timezone.now(),
            end_time=timezone.now() + datetime.timedelta(days=coupon_template.valid_days),
            is_used=False
        )
        return True, "🎉 生日快乐！200元代金券已放入您的卡包。"

    def handle_consume_points(self, order_money, order_sn):
        """处理消费赠分（内置生日当月首笔消费双倍逻辑）"""
        # 🌟 核心更新：修复为“1元积1分”
        base_points = int(float(order_money))
        if base_points <= 0:
            return

        multiplier = 1
        desc_prefix = ""

        # 校验是否为生日当月首单双倍
        if self.birth_date and self.birth_date.month == timezone.now().month:
            current_year = timezone.now().year
            has_used_double = self.points_records.filter(
                points_type=2,
                description__contains="生日双倍",
                create_time__year=current_year
            ).exists()

            if not has_used_double:
                multiplier = 2
                desc_prefix = "【生日双倍礼遇】"

        final_points = base_points * multiplier
        desc = f"{desc_prefix}订单{order_sn}消费赠送"
        self.add_points(final_points, points_type=2, related_id=order_sn, related_desc=desc)

    def add_points(self, points, points_type, related_id="", related_desc=""):
        """
        积分核心账户引擎（带有 12 个月有效期和 FIFO 消耗算法）
        """
        try:
            from .models import PointsRecord

            points = int(points)
            if points == 0:
                return True, "积分无变动"

            with transaction.atomic():
                current_points = self.points or 0

                # ================= 扣减积分 (FIFO) =================
                if points < 0:
                    deduct_points = abs(points)
                    if current_points < deduct_points:
                        return False, f"积分不足（当前{current_points}分，需扣减{deduct_points}分）"

                    # 查找未过期且有余额的积分账单，按即将过期的时间优先排序
                    valid_records = self.points_records.filter(
                        available_points__gt=0,
                        expire_time__gt=timezone.now()
                    ).order_by('expire_time')

                    points_to_deduct = deduct_points
                    for record in valid_records:
                        if points_to_deduct <= 0:
                            break
                        if record.available_points >= points_to_deduct:
                            record.available_points -= points_to_deduct
                            record.save(update_fields=['available_points'])
                            points_to_deduct = 0
                        else:
                            points_to_deduct -= record.available_points
                            record.available_points = 0
                            record.save(update_fields=['available_points'])

                    self.points = current_points - deduct_points
                    self.save(update_fields=["points"])

                    PointsRecord.objects.create(
                        user=self, points=points, available_points=0,
                        points_type=points_type, related_id=related_id,
                        description=related_desc, create_time=timezone.now()
                    )

                # ================= 增加积分 (带过期时间) =================
                else:
                    import datetime
                    expire_time = timezone.now() + datetime.timedelta(days=365)
                    self.points = current_points + points
                    self.save(update_fields=["points"])

                    PointsRecord.objects.create(
                        user=self, points=points, available_points=points, expire_time=expire_time,
                        points_type=points_type, related_id=related_id,
                        description=related_desc, create_time=timezone.now()
                    )

            return True, f"积分{'增加' if points > 0 else '扣减'}成功（{abs(points)}分）"
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"积分操作失败：{str(e)}", exc_info=True)
            return False, f"积分操作失败：{str(e)}"

    def exchange_goods_by_point(self, goods, buy_num=1):
        """商品积分兑换业务封装"""
        if not goods.can_point_exchange:
            return {"success": False, "msg": f"商品「{goods.name}」不支持积分兑换", "data": None}

        exchange_detail = goods.calculate_point_exchange(buy_num, self.points)
        exchange_detail.update({
            "user_points": self.points,
            "points_shortage": max(exchange_detail["need_point"] - self.points, 0),
            "points_shortage_money": exchange_detail["points_shortage"] * 0.01
        })
        return {"success": True, "msg": "积分兑换计算完成", "data": exchange_detail}

    # ==============================================================
    #                   三、会员网络与下级查询
    # ==============================================================
    def get_sub_users(self):
        """获取直属下级会员"""
        return self.sub_users.all()

    def get_sub_consume_records(self, current_level=0):
        """获取下级消费详情 (带有订单地址预加载)"""
        try:
            current_level = int(current_level)
        except (ValueError, TypeError):
            current_level = 0

        from .models import Order

        sub_users = self.sub_users.all()
        sub_consume_data = []

        for sub_user in sub_users:
            orders = Order.objects.filter(
                user=sub_user,
                status__in=[1, 2, 3, 4],
                is_delete=False,
                order_type='normal',
                goods_count__gt=0
            ).select_related('address').order_by('-create_time').prefetch_related('items')

            if orders:
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

    # ==============================================================
    #                   四、优惠券系统查询
    # ==============================================================
    def get_coupons(self, only_valid=False, coupon_type=None):
        """获取用户的优惠券列表"""
        queryset = self.user_coupons.all().select_related("coupon")
        if only_valid:
            queryset = queryset.filter(is_used=False, end_time__gt=timezone.now())
        if coupon_type in [1, 2]:
            queryset = queryset.filter(coupon__coupon_type=coupon_type)
        return queryset

    def get_coupon_stats(self):
        """获取用户的优惠券资产数据统计"""
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

    # ==============================================================
    #                   五、会员分层权益文本配置
    # ==============================================================
    def get_benefits(self):
        """🌟 核心更新：返回对应会员级别的文字权益介绍（适配最新 7 档体系）"""
        if self.user_type == 1:
            return [
                "注册门槛：0元",
                "专享价格：零售价",
                "消费补贴：0%",
                "其他权益：关注小程序完成注册即可体验基础服务。"
            ]
        elif self.user_type == 2:
            return [
                "注册储值：980元",
                "专享价格：会员价",
                "消费补贴：0%",
                "会员礼遇：100元代金券"
            ]
        elif self.user_type == 3:
            return [
                "注册储值：1980元",
                "专享价格：会员价",
                "消费补贴：0%",
                "会员礼遇：300元代金券",
                "商学院权益：享受 3980元 护肤私教专业认证资格"
            ]
        elif self.user_type == 4:
            return [
                "注册储值：3800元",
                "专享价格：会员价",
                "消费补贴：家居品 10%",
                "会员礼遇：1000元代金券",
                "商学院权益：享受 3980元 护肤私教专业认证资格"
            ]
        elif self.user_type == 5:
            return [
                "注册储值：9800元",
                "专享价格：会员价",
                "消费补贴：全产品 15%",
                "会员礼遇：1次胶原mini",
                "商学院权益：享受 3980元 护肤私教专业认证资格"
            ]
        elif self.user_type == 6:
            return [
                "注册储值：39800元",
                "专享价格：会员价",
                "消费补贴：全产品 15%",
                "会员礼遇：1次胶原尊享 + 1套胶原润肌",
                "商学院权益：享受 3980元 护肤私教专业认证资格"
            ]
        elif self.user_type == 7:
            return [
                "开通门槛：9.8万元（需线下签约）",
                "高端圈层：Ta创+高端俱乐部会员，享奇肌疗愈营，高端沙龙活动；",
                "产品折扣：享极具竞争力的专属进货权益，产品任选；",
                "SSTA运营：运营中心模版店的打造及全面扶持；",
                "专业赋能：护肤私教全部体系课程+证书，《她力量》《明星代言人》首推官资格。"
            ]
        return []

    @property
    def is_valid_vip(self):
        """
        判断用户是否是有效的付费会员/店长
        """
        # 如果是普通用户，直接算无效
        if self.user_type <= 1:
            return False

        # 如果有过期时间，且当前时间大于过期时间，则已过期
        if self.expire_time and timezone.now() > self.expire_time:
            return False

        return True

    # ==============================================================
    #                   六、电子钱包快捷访问属性
    # ==============================================================
    @property
    def wallet_balance(self):
        """快捷获取电子账户总余额（本金+赠金）"""
        if hasattr(self, 'wallet') and self.wallet.status:
            return self.wallet.total_balance
        from decimal import Decimal
        return Decimal('0.00')

    @property
    def wallet_principal(self):
        """快捷获取电子账户本金（可用于未来本金提现或退款校验）"""
        if hasattr(self, 'wallet') and self.wallet.status:
            return self.wallet.principal
        from decimal import Decimal
        return Decimal('0.00')

    @property
    def wallet_bonus(self):
        """快捷获取电子账户赠送金"""
        if hasattr(self, 'wallet') and self.wallet.status:
            return self.wallet.bonus
        from decimal import Decimal
        return Decimal('0.00')

class EnterpriseProfile(models.Model):
    """
    【企业档案表】
    Ta创+ 专属的企业资质与对公结算账户。
    一个 Ta创+ 账号可以关联多个企业账户（改成 ForeignKey 关系，比 OneToOne 更灵活）
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # 关联你的 User 架构（5星Ta创+）
        on_delete=models.CASCADE,
        related_name='enterprise_profiles',
        verbose_name="所属Ta创+"
    )
    company_name = models.CharField(max_length=100, verbose_name="企业/公司名称")
    credit_code = models.CharField(max_length=18, unique=True, null=True, blank=True, verbose_name="统一社会信用代码")
    corporate_bank_account = models.CharField(max_length=50, null=True, blank=True, verbose_name="企业对公账户")
    bank_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="开户行")

    # 企业财务独立/独立结算开关
    is_active = models.BooleanField(default=True, verbose_name="是否启用结算")

    class Meta:
        verbose_name = "Ta创+企业档案"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.nickname if self.user else '未知'}-{self.company_name}"

class UserWallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet',
                                verbose_name='所属用户')

    # 🌟 强烈建议：本金和赠送金分开存！
    principal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='本金余额')
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='赠送金余额')

    total_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                        verbose_name='总余额')  # 冗余字段，等于 本金+赠金，方便前端查询
    status = models.BooleanField(default=True, verbose_name='账户状态')  # 用于风控，如果是黑产可以直接冻结钱包而不封禁账号
    update_time = models.DateTimeField(auto_now=True, verbose_name='最后变动时间')

    def save(self, *args, **kwargs):
        # 1. 强制洗牌：不管上游传过来的是 float、int 还是字符串，统统转化为高精度 Decimal
        # 先转 str 是为了防止直接把 float 转 Decimal 导致的无限循环小数精度问题
        self.principal = Decimal(str(self.principal or '0.00'))
        self.bonus = Decimal(str(self.bonus or '0.00'))

        # 2. 安全相加
        self.total_balance = self.principal + self.bonus

        super().save(*args, **kwargs)
    class Meta:
        verbose_name = '用户电子钱包'
        verbose_name_plural = verbose_name

class WalletTransaction(models.Model):
    TRANSACTION_TYPE = (
        (1, '充值'),
        (2, '消费扣款'),
        (3, '退款返还'),
        (4, '后台修改'),
    )

    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='transactions',
                               verbose_name='对应钱包')
    trade_no = models.CharField(max_length=64, unique=True, verbose_name='交易流水号')
    order_sn = models.CharField(max_length=64, null=True, blank=True, verbose_name='关联业务订单号')  # 记录是因为哪笔商城订单扣的钱

    transaction_type = models.SmallIntegerField(choices=TRANSACTION_TYPE, verbose_name='变动类型')

    # 变动金额（有正负）
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='变动总金额')
    principal_change = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='本金变动')
    bonus_change = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='赠金变动')

    # 变动后的账户快照（极其重要，用于查账防篡改）
    after_balance = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='变动后总余额')

    remark = models.CharField(max_length=255, verbose_name='变动说明')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    class Meta:
        verbose_name = '电子账户流水'
        verbose_name_plural = verbose_name

class RechargeActivity(models.Model):
    """储值活动/套餐配置表"""
    name = models.CharField(max_length=100, verbose_name='活动名称', help_text='例如：充1000送200元代金券')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='需充值金额(实付)')

    # 赠送权益配置
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                       verbose_name='额外赠送金额(进入赠金账户)')
    gift_coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name='赠送的代金券')
    gift_coupon_num = models.IntegerField(default=1, verbose_name='赠送代金券张数')

    is_active = models.BooleanField(default=True, verbose_name='是否上架')
    sort_order = models.IntegerField(default=0, verbose_name='排序(越小越靠前)')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '储值套餐'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'amount']

    def __str__(self):
        return f"{self.amount}元套餐 - {self.name}"

class RechargeOrder(models.Model):
    """用户充值订单表"""
    STATUS_CHOICES = ((0, '待支付'), (1, '充值成功'), (2, '已取消'))

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='recharge_orders', verbose_name='充值用户')
    order_sn = models.CharField(max_length=64, unique=True, verbose_name='充值单号')
    activity = models.ForeignKey(RechargeActivity, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='参与的储值套餐')

    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='应付金额')
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, verbose_name='支付状态')

    pay_method = models.IntegerField(choices=((1, '微信支付'), (2, '模拟支付')), default=1, verbose_name='支付方式')
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name='支付时间')
    transaction_id = models.CharField(max_length=64, null=True, blank=True, verbose_name='微信支付流水号')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '充值订单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.order_sn} - {self.get_status_display()}"
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

    # 新增：题型枚举
    QUESTION_TYPE = [
        (1, "单选题"),
        (2, "多选题"),
        (3, "判断题"),
    ]

    question = models.TextField(verbose_name="题目")
    question_type = models.IntegerField(choices=QUESTION_TYPE, default=1, verbose_name="题型")  # 新增：支持多种题型

    option_a = models.CharField(max_length=200, verbose_name="选项A")
    option_b = models.CharField(max_length=200, verbose_name="选项B")
    option_c = models.CharField(max_length=200, verbose_name="选项C", blank=True, null=True)  # 判断题可能没有C和D
    option_d = models.CharField(max_length=200, verbose_name="选项D", blank=True, null=True)

    answer = models.CharField(max_length=10, verbose_name="正确答案", help_text="多选题请用逗号分隔，如 A,B,C")
    explanation = models.TextField(blank=True, null=True, verbose_name="答案解析")  # 新增：错题解析
    score = models.IntegerField(default=5, verbose_name="单题分值")  # 新增：每题多少分

    course_type = models.IntegerField(choices=COURSE_TYPE, verbose_name="对应课程分类")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")  # 新增：软删除/上下架，防止题库删题导致历史记录报错
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "考核题库"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"[{self.get_course_type_display()}] {self.question[:20]}"


# 3. 考核记录模型
class ExamRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="参考用户")
    # 修复：复用 ExamQuestion 的 COURSE_TYPE
    course_type = models.IntegerField(choices=ExamQuestion.COURSE_TYPE, verbose_name="考核分类")
    score = models.IntegerField(verbose_name="考核分数")
    is_pass = models.BooleanField(default=False, verbose_name="是否通过")

    # ================= 🚀 核心新增：答题快照 =================
    # 存储格式示例：{"1": {"user_answer": "A", "is_correct": True}, "2": {"user_answer": "A,B", "is_correct": False}}
    # 这样用户考完就能直接看错题本了！
    user_answers = models.JSONField(blank=True, null=True, verbose_name="用户答题详情")
    # =========================================================

    exam_time = models.DateTimeField(auto_now_add=True, verbose_name="考核时间")

    class Meta:
        verbose_name = "考核记录"
        verbose_name_plural = verbose_name
        ordering = ["-exam_time"]  # 新增：默认按时间倒序，方便查询最近一次考试

    def __str__(self):
        return f"{self.user.nickname} - {self.get_course_type_display()} - {self.score}分"

# # 4. 线下认证模型
# class Certification(models.Model):
#     CERT_TYPE = [
#         (1, "护肤私教认证"),
#         (2, "线下实操考核"),
#     ]
#     user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="认证用户")  # 大写User，无冲突
#     cert_type = models.IntegerField(choices=CERT_TYPE, verbose_name="认证类型")
#     name = models.CharField(max_length=50, verbose_name="真实姓名")
#     phone = models.CharField(max_length=11, verbose_name="手机号")
#     id_card = models.CharField(max_length=18, verbose_name="身份证号")
#     upload_file = models.FileField(upload_to='certification/', verbose_name="认证材料")
#     status = models.IntegerField(default=0, choices=[(0, "待审核"), (1, "已通过"), (2, "已驳回")], verbose_name="认证状态")
#     create_time = models.DateTimeField(auto_now_add=True, verbose_name="提交时间")
#     review_time = models.DateTimeField(blank=True, null=True, verbose_name="审核时间")
#
#     class Meta:
#         verbose_name = "线下认证"
#         verbose_name_plural = verbose_name
#
#     def __str__(self):
#         return f"{self.user.nickname} - {self.get_cert_type_display()} - {self.get_status_display()}"

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

class StoreSenderAddress(models.Model):
    """
    发件人/发货仓地址库 (用于京东物流下单的 senderContact)
    """
    sender_name = models.CharField(max_length=50, verbose_name="发件人姓名")
    sender_phone = models.CharField(max_length=20, verbose_name="发件人手机号")
    province = models.CharField(max_length=20, verbose_name="省份")
    city = models.CharField(max_length=20, verbose_name="城市")
    district = models.CharField(max_length=20, verbose_name="区县")
    detail_address = models.CharField(max_length=200, verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="是否默认发货地址")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "发货人/仓库地址"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.sender_name} - {self.province}{self.city}{self.district}{self.detail_address}"

    @property
    def full_address(self):
        """拼接京东所需的 fullAddress"""
        return f"{self.province}{self.city}{self.district}{self.detail_address}"

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

class Order(models.Model):
    ORDER_STATUS = (
        (0, "待付款"),
        (1, "待发货"),  # 快递专用：待发货
        (2, "待收货"),  # 仅快递专用
        (3, "已完成"),
        (4, "已取消"),
    )
    # 到店自取专用状态映射（覆盖原状态名）
    PICK_UP_STATUS_MAP = {
        0: "待付款",
        1: "备货中",
        2: "待取货",
        3: "已完成",
        4: "已取消",
    }

    DELIVERY_TYPE_CHOICES = (
        (1, "快递上门"),
        (2, "到店自取"),
    )
    # 原有核心字段保留
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # 用户删除时订单保留，置空即可
        null=True,
        blank=True,
        verbose_name='所属用户'
    )
    order_sn = models.CharField(max_length=64, unique=True, verbose_name="商户订单编号")
    goods_names = models.CharField(max_length=500, null=True, blank=True, verbose_name="订单产品名称（拼接）")
    goods_count = models.IntegerField(default=0, verbose_name="订单商品总数")
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="收货地址")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总价")
    status = models.IntegerField(choices=ORDER_STATUS, default=0, verbose_name="订单状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_point_deducted = models.BooleanField(default=False, verbose_name="积分是否已扣减")
    order_type = models.CharField(max_length=20, default='normal', verbose_name='订单类型')  # normal/member/shop
    register_data = models.JSONField(null=True, blank=True, verbose_name='注册暂存数据')
    openid = models.CharField(max_length=64, null=True, blank=True, verbose_name='微信openid')
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
    # 1. 支付相关 (新增电子钱包和混合支付)
    PAY_METHOD_CHOICES = (
        (1, "微信支付"),
        (2, "线下支付"),
        (3, "电子账户支付"),  # 🌟 新增：全额用电子钱包支付
        (4, "混合支付"),  # 🌟 新增：钱包余额不足，剩余部分用微信补齐
    )
    pay_method = models.IntegerField(choices=PAY_METHOD_CHOICES, null=True, blank=True, verbose_name="支付方式")
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name="支付完成时间")
    pay_no = models.CharField(max_length=64, null=True, blank=True, verbose_name="支付单号")

    # ===================== 🌟🌟 【新增】订单资金拆分与返佣基数 =====================
    # 逻辑公式: total_price - point_deduct_money - coupon_deduct = actual_pay_money
    # actual_pay_money = wallet_pay + wechat_pay = commission_base

    coupon_deduct = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="优惠券抵扣金额"
    )
    wallet_pay = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="电子账户支付金额"
    )
    wechat_pay = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="第三方支付金额(微信/支付宝)"
    )

    # 💥 这个字段是整个防薅羊毛体系的灵魂！分佣系统只认这个字段！
    commission_base = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="返佣计算基数(真金白银)"
    )

    # ========== 物流与发货相关 ==========
    logistics_no = models.CharField(max_length=64, null=True, blank=True, verbose_name="物流单号/运单号")
    logistics_company = models.CharField(max_length=32, null=True, blank=True, verbose_name="物流公司")
    ship_time = models.DateTimeField(null=True, blank=True, verbose_name="发货时间")
    receive_time = models.DateTimeField(null=True, blank=True, verbose_name="收货时间")

    # --- 京东预下单/发件人信息（你已有的字段，保留） ---
    jd_precheck_status = models.BooleanField(default=False, verbose_name="京东预校验是否通过")
    jd_error_msg = models.CharField(max_length=255, null=True, blank=True, verbose_name="京东报错信息")
    # Order 模型必须包含
    sender_name = models.CharField(max_length=50, null=True, blank=True)
    sender_phone = models.CharField(max_length=20, null=True, blank=True)
    sender_province = models.CharField(max_length=50, null=True, blank=True)
    sender_city = models.CharField(max_length=50, null=True, blank=True)
    sender_district = models.CharField(max_length=50, null=True, blank=True)
    sender_detail = models.CharField(max_length=255, null=True, blank=True)
    sender_address = models.CharField(max_length=255, null=True, blank=True)  # 完整地址
    # --------------- 京东物流 合并关键字段（查询+取消）---------------

    jd_create_time = models.DateTimeField(blank=True, null=True, verbose_name='京东下单时间')
    jd_latest_status = models.CharField(max_length=20, blank=True, verbose_name='京东最新物流状态')  #

    # ✅ 【核心】取消订单 + 轨迹查询 共用关键字段
    jd_waybill_code = models.CharField(max_length=50, blank=True, verbose_name='京东运单号')
    jd_order_code = models.CharField(max_length=50, blank=True, verbose_name='京东订单号')
    jd_order_origin = models.IntegerField(default=1, verbose_name='下单来源(固定1)')
    jd_customer_code = models.CharField(max_length=50, blank=True, verbose_name='京东客户编码')
    track_reference_type = models.CharField(max_length=10, default='20000', verbose_name='轨迹单据类型(固定20000)')

    # 3. 取消/售后相关
    cancel_time = models.DateTimeField(null=True, blank=True, verbose_name="取消时间")
    cancel_reason = models.CharField(max_length=200, null=True, blank=True, verbose_name="取消原因")
    remark = models.CharField(max_length=500, null=True, blank=True, verbose_name="用户备注")

    # ===================== ✅【新增】京东物流核心扩展字段 =====================
    jd_freight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="京东运费")
    jd_order_status = models.CharField(
        max_length=20,
        choices=[
            ('created', '已下单/待揽收'),
            ('cancelled', '已取消'),
            ('intercepting', '拦截中'),
            ('intercepted', '拦截成功'),
            ('finished', '已妥投/已完成')
        ],
        blank=True,
        default='',
        verbose_name='京东揽收状态'
    )

    fulfill_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                   limit_choices_to={'user_type': 5},
                                   related_name='to_fulfill_orders',
                                   verbose_name="履约方(发货的Ta创+)")

    # 4. 软删除
    is_delete = models.BooleanField(default=False, verbose_name="是否删除")

    # ========== 积分抵扣字段 ==========
    point_deduct = models.IntegerField(default=0, verbose_name="抵扣积分")
    point_deduct_money = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="积分抵扣金额"
    )
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
        """根据配送类型返回状态名称"""
        if self.delivery_type == 2:
            return self.PICK_UP_STATUS_MAP.get(self.status, f"未知状态({self.status})")
        else:
            return self.get_status_display()

    def clean(self):
        if self.delivery_type == 2 and self.status not in [0, 1, 2, 3, 4]:
            raise ValidationError("到店自取订单仅支持：待付款/待取货/已完成/已取消")

    def save(self, *args, **kwargs):
        self.clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not is_new and hasattr(self, 'items') and self.items.exists():
            self.goods_names = "、".join([item.goods_name for item in self.items.all()])
            self.goods_count = sum([item.num for item in self.items.all()])
            super().save(update_fields=['goods_names', 'goods_count'])

    @property
    def goods_names_str(self):
        if self.goods_names:
            return self.goods_names
        if self.pk and hasattr(self, 'items') and self.items.exists():
            return "、".join([item.goods_name for item in self.items.all()])
        return "无商品"

    @property
    def goods_list(self):
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
        from django.db import transaction
        if self.is_point_deducted:
            return True, "该订单积分已扣减"
        if self.status not in [1, 2, 3]:
            return False, f"订单状态异常：{self.get_status_display()}"
        for goods in goods_list:
            if not hasattr(goods, 'can_point_exchange') or not goods.can_point_exchange:
                return False, f"商品「{goods.name}」不支持积分抵扣"
        if deduct_point <= 0:
            return True, "无需积分抵扣"
        if not hasattr(user, 'points') or user.points < deduct_point:
            return False, f"积分不足：当前{getattr(user, 'points', 0)}分，需{deduct_point}分"

        try:
            with transaction.atomic():
                user.points -= deduct_point
                user.save(update_fields=['points'])
                from .models import PointsRecord
                PointsRecord.objects.create(
                    user=user,
                    points=-deduct_point,
                    points_type=4,
                    related_id=self.order_sn,
                    description=f"订单{self.order_sn}抵扣{deduct_point}积分"
                )
                self.point_deduct = deduct_point
                self.point_deduct_money = Decimal(str(deduct_point * 0.01))
                self.actual_pay_money = max(self.total_price - self.point_deduct_money, Decimal('0.00'))
                self.is_point_deducted = True
                self.save(update_fields=['point_deduct', 'point_deduct_money', 'actual_pay_money', 'is_point_deducted'])
            return True, f"成功抵扣{deduct_point}积分"
        except Exception as e:
            logger.error(f"订单{self.order_sn}积分抵扣失败：{str(e)}", exc_info=True)
            return False, f"积分抵扣失败：{str(e)[:20]}"

class UpgradeOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="升级用户")
    out_trade_no = models.CharField(max_length=64, unique=True, verbose_name="订单编号")
    target_level = models.IntegerField(verbose_name="目标等级 (2-5)")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="支付金额")
    status = models.IntegerField(default=0, choices=((0, '待支付'), (1, '已支付')), verbose_name="订单状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name="支付时间")

    class Meta:
        verbose_name = "会员升级订单"
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        if not self.out_trade_no:
            # 生成带前缀的订单号，方便微信支付回调时区分业务
            self.out_trade_no = f"UPG{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

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
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=1.00, verbose_name="单件重量(kg)")
    volume = models.DecimalField(max_digits=8, decimal_places=4, default=0.0100, verbose_name="单件体积(m³)")
    class Meta:
        verbose_name = "订单商品"
        verbose_name_plural = "订单商品"

    def __str__(self):
        return f"{self.order.order_sn} - {self.goods_name} x {self.num}"

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.num * self.price
        # 新增：从 Goods 自动带出物理属性快照
        if self.goods and not self.pk:
            self.weight = self.goods.weight
            self.volume = self.goods.volume
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

class CommissionRecord(models.Model):
    """佣金返现流水表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commissions', verbose_name="获佣人(上级)")
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="购买人(下级)")
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, verbose_name="关联订单")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="佣金金额")
    desc = models.CharField(max_length=255, verbose_name="奖励说明")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="记账时间")

    class Meta:
        db_table = 'commission_record'
        ordering = ['-create_time']
        verbose_name = "佣金收益流水"
        verbose_name_plural = "佣金收益流水"

class WithdrawRecord(models.Model):
    """提现申请表"""
    STATUS_CHOICES = (
        (0, '待财务审核'),
        (1, '打款中(待用户微信确认)'),
        (2, '打款成功'),
        (3, '已拒绝/打款失败'),
    )

    # 微信转账所需的单号
    out_bill_no = models.CharField(max_length=64, unique=True, verbose_name="商户单号")
    transfer_bill_no = models.CharField(max_length=64, null=True, blank=True, verbose_name="微信转账单号")
    package_info = models.CharField(max_length=255, null=True, blank=True, verbose_name="微信收款包")
    # 基础信息
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdraws', verbose_name="提现用户")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="提现金额")
    status = models.IntegerField(choices=STATUS_CHOICES, default=0, verbose_name="状态")

    # 时间追踪
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="申请时间")

    # 财务审核相关
    audit_time = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    auditor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audited_withdraws', verbose_name="审核人(财务)"
    )
    audit_remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="审核备注")

    class Meta:
        db_table = 'withdraw_record'
        ordering = ['-create_time']
        verbose_name = "提现申请"
        verbose_name_plural = "提现申请"

    @classmethod
    def can_withdraw_this_month(cls, user):
        """
        核心业务逻辑：检查该用户本月是否还可以提现
        返回 Boolean
        """
        now = timezone.now()
        # 获取本月第一天的 00:00:00
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 查询该用户在本月内是否有过提现记录
        # 注意：通常只要提交了申请（不论是否通过），或者只算通过的，视你的具体业务而定。
        # 这里默认以“提交过申请（状态不是已拒绝）”来限制。
        existing_withdraws = cls.objects.filter(
            user=user,
            create_time__gte=first_day_of_month,
        ).exclude(status=3)  # 如果被财务拒绝了，可以允许他当月重新提现，所以排除掉状态3

        return not existing_withdraws.exists()

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

# ====================== AI 智能客服对话模型（小程序专用） ======================

class AIChatSession(models.Model):
    """
    AI 对话会话表
    一个用户对应一个会话，存储对话上下文
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_sessions",
        verbose_name="用户"
    )
    title = models.CharField(max_length=100, default="美业 AI 咨询", verbose_name="会话标题")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="最后对话时间")
    is_delete = models.BooleanField(default=False, verbose_name="是否删除")

    class Meta:
        verbose_name = "AI 对话会话"
        verbose_name_plural = verbose_name
        ordering = ["-update_time"]

    def __str__(self):
        return f"{self.user.nickname} - {self.title}"

class AIChatMessage(models.Model):
    """
    AI 对话消息表
    存储用户问题 + AI 回答，关联会话
    """
    ROLE_CHOICES = (
        ("user", "用户"),
        ("assistant", "AI 助手"),
    )
    # 🔥 新增：用于标识这条消息是由哪个模型生成的（可选，主要用于 assistant）
    MODEL_CHOICES = (
        ("lite", "快速小模型"),
        ("pro", "专业大模型"),
    )

    session = models.ForeignKey(
        "AIChatSession",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="所属会话"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")
    content = models.TextField(verbose_name="消息内容")

    # ================= 🚀 新增的核心计费溯源字段 =================
    model_type = models.CharField(max_length=20, choices=MODEL_CHOICES, default="lite", verbose_name="生成模型")
    tokens_used = models.IntegerField(default=0, verbose_name="消耗Token数")
    points_deducted = models.IntegerField(default=0, verbose_name="扣除积分数")
    # =========================================================

    create_time = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")

    class Meta:
        verbose_name = "AI 对话消息"
        verbose_name_plural = verbose_name
        ordering = ["create_time"]

    def __str__(self):
        return f"[{self.get_model_type_display()}] {self.get_role_display()}：{self.content[:20]}"

# ==============================================================================
# 🌟 用户AI测肤与动态肤质档案
# ==============================================================================

class UserSkinProfile(models.Model):
    """
    与系统用户一对多关联的AI测肤闭环数据舱（支持亲友建档）
    """
    # 🌟 核心修改 1：改为 ForeignKey，允许一个用户创建多个测肤档案
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='skin_profiles',
        verbose_name="所属登录用户"
    )

    # 🌟 核心修改 2：新增被测人姓名，作为档案的唯一标识
    subject_name = models.CharField(
        max_length=50,
        verbose_name="被测人姓名"
    )

    # ================= 📝 问卷阶段数据 =================
    answers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="问卷原生答案(Q1-Q8)"
    )
    skin_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="智能肤质标签（优先级排序，最多3个）"
    )

    # ================= 📸 视觉诊断数据 (已将原图片字段剥离至子表) =================
    image_analysis = models.TextField(
        null=True,
        blank=True,
        verbose_name="Qwen-VL 表皮客观特征提取文本"
    )

    # ================= 🧠 大模型最终分析输出 =================
    final_report = models.TextField(
        null=True,
        blank=True,
        verbose_name="蓝博士私教综合定性报告"
    )
    skincare_plan = models.TextField(
        null=True,
        blank=True,
        verbose_name="私教终极居家方案(Markdown表格)"
    )

    # ================= ⏳ 时间轴 =================
    created_time = models.DateTimeField(auto_now_add=True, verbose_name="首测建档时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="最近更新时间")

    class Meta:
        db_table = 'user_skin_profile'
        verbose_name = "被测人肤质档案"
        verbose_name_plural = verbose_name
        ordering = ["-update_time"]
        # 🌟 核心修改 3：联合唯一约束，确保同一个账号下不出现两个同名的被测人
        unique_together = ('user', 'subject_name')

    def __str__(self):
        tags_display = "、".join(self.skin_tags) if self.skin_tags else "暂无标签"
        return f"【档案】- {self.subject_name} (归属: {self.user.username}) | 肤质: {tags_display}"


# 🌟 核心修改 4：新增独立的照片时间轴记录表
class SkinPhotoRecord(models.Model):
    """
    测肤历史照片记录（支持同一被测人无限期追加）
    """
    profile = models.ForeignKey(
        UserSkinProfile,
        on_delete=models.CASCADE,
        related_name='photo_records',
        verbose_name="所属档案"
    )

    face_image = models.ImageField(
        upload_to='skin_images/%Y/%m/%d/',
        verbose_name="面部照片文件"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    class Meta:
        db_table = 'user_skin_photo_record'
        verbose_name = "历史测肤照片"
        verbose_name_plural = verbose_name
        ordering = ["-uploaded_at"]  # 最新的照片排在最前面

    def __str__(self):
        return f"{self.profile.subject_name} 的测肤记录 - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"


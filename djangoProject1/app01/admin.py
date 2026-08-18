from django.contrib import admin

# Register your models here.
from .models import (Welcome, Banner, Notice, Index_Annonce, UserInfo, Area, Category, Goods,
                     StudyCheckIn, ExamQuestion, ExamRecord, User, Cart, Recipient,
                     Address, Order, GoodsImage, Coupon, ExpressLogistics, UserSkinProfile, SkinPhotoRecord,
                     CourseCategory, VideoCourse, MemberPrivilege, UserOfflineProject, OfflineServiceRecord, CommissionRecord,
WithdrawRecord, UserWallet, WalletTransaction,UserCoupon, EnterpriseProfile,OfflineCertification
                     )

admin.site.register(Welcome)
admin.site.register(Banner)
admin.site.register(Notice)
admin.site.register(Index_Annonce)
admin.site.register(UserInfo)
admin.site.register(Area)
admin.site.register(UserCoupon)
admin.site.register(OfflineCertification)
admin.site.register(GoodsImage)
admin.site.register(StudyCheckIn)
admin.site.register(ExamQuestion)
admin.site.register(ExamRecord)
# admin.site.register(Certification)
admin.site.register(Cart)
admin.site.register(Recipient)
admin.site.register(Address)
admin.site.register(Order)
admin.site.register(Coupon)
admin.site.register(ExpressLogistics)
admin.site.register(CommissionRecord)
admin.site.register(WithdrawRecord)
admin.site.register(EnterpriseProfile)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # 后台列表显示的字段
    list_display = ['member_id', 'nickname', 'user_type', 'get_user_type_display', 'phone', 'star_level', 'points', 'create_time']
    # 可搜索的字段
    search_fields = ['member_id', 'nickname', 'phone', 'email']
    # 可筛选的字段
    list_filter = ['user_type', 'star_level', 'create_time']
    # 只读字段（无需手动修改的字段）
    readonly_fields = ['create_time']
    # 列表排序（默认按创建时间倒序）
    ordering = ['-create_time']
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # 🌟 在列表中显示 sort_order
    list_display = ['id', 'name', 'sort_order']
    # 🌟 允许在列表页直接修改数字，不用点进详情
    list_editable = ['sort_order']
    search_fields = ['name']

@admin.register(Goods)
class GoodsAdmin(admin.ModelAdmin):
    # 🌟 在列表页透出 goods_type 和 service_times
    list_display = ['id', 'name', 'goods_type', 'service_times', 'member_price', 'stock', 'is_star',
                    'sort_order']

    # 🌟 增加右侧过滤栏，方便管理员只看“线下项目”或“实体商品”
    list_filter = ['goods_type', 'category', 'is_star']

    search_fields = ['name', 'brief_intro']
    list_editable = ['sort_order',  'is_star']  # 方便在列表页直接修改排序和上下架

# 注册用户项目资产表（方便后台查看谁买了多少次）
@admin.register(UserOfflineProject)
class UserOfflineProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'project', 'total_times', 'remain_times', 'create_time']
    list_filter = ['project']
    # 假设你的 User 关联了 memberinfo，可以用 user__memberinfo__nickname 搜索
    search_fields = ['user__username', 'project__name']

# 注册服务核销与评价记录表（方便后台查阅评价和流水）
@admin.register(OfflineServiceRecord)
class OfflineServiceRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'manager', 'project', 'status', 'rating', 'create_time', 'confirm_time']
    list_filter = ['status', 'rating', 'project']
    search_fields = ['user__username', 'manager__username']

class SkinPhotoRecordInline(admin.TabularInline):
    model = SkinPhotoRecord
    extra = 0  # 默认不显示空的上传框
    readonly_fields = ['uploaded_at', 'image_preview']  # 设为只读
    fields = ['face_image', 'image_preview', 'uploaded_at']

    # 顺手写一个小图预览功能
    def image_preview(self, obj):
        if obj.face_image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-height: 80px; border-radius: 5px;" />', obj.face_image.url)
        return "-"

    image_preview.short_description = '照片预览'


# 注册主表
@admin.register(UserSkinProfile)
class UserSkinProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'subject_name', 'get_skin_tags', 'created_time', 'update_time']
    search_fields = ['subject_name', 'user__username', 'user__member_id']
    list_filter = ['created_time']

    # 🌟 核心：把上面的内联照片表挂载进来
    inlines = [SkinPhotoRecordInline]

    def get_skin_tags(self, obj):
        if obj.skin_tags:
            return "、".join(obj.skin_tags)
        return "尚未测试"

    get_skin_tags.short_description = '当前肤质标签'

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sort_order', 'is_active', 'create_time')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name',)

@admin.register(VideoCourse)
class VideoCourseAdmin(admin.ModelAdmin):
    # 移除了 required_level，加入了 category
    list_display = ('id', 'title', 'category', 'duration', 'play_count', 'is_publish', 'create_time')
    list_filter = ('category', 'is_publish')
    search_fields = ('title', 'desc')

@admin.register(MemberPrivilege)
class MemberPrivilegeAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'update_time']
    list_filter = ['is_active']


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_balance', 'principal', 'bonus', 'status', 'update_time']
    search_fields = ['user__phone', 'user__nickname', 'user__member_id']
    list_filter = ['status']

    # 🌟 财务红线：禁止在后台直接手敲修改余额数字！
    # 想要加钱或扣钱，必须去“资金流水表”里新增一条“后台修改”的流水记录。
    # readonly_fields = ['principal', 'bonus', 'total_balance', 'update_time']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['trade_no', 'get_user', 'transaction_type', 'amount', 'after_balance', 'create_time']
    search_fields = ['trade_no', 'order_sn', 'wallet__user__phone', 'remark']
    list_filter = ['transaction_type', 'create_time']
    readonly_fields = ['create_time']

    # 优化展示：在流水列表里直接显示是哪个用户的
    def get_user(self, obj):
        return f"{obj.wallet.user.nickname} ({obj.wallet.user.phone})"

    get_user.short_description = '所属用户'

    # # 🌟 安全防御：资金流水一旦生成，绝对不允许在后台删除或修改！只能查看！
    # def has_change_permission(self, request, obj=None):
    #     return False
    #
    # def has_delete_permission(self, request, obj=None):
    #     return False
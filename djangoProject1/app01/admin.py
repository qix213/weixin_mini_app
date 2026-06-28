from django.contrib import admin

# Register your models here.
from .models import (Welcome, Banner, Notice, Index_Annonce, UserInfo, Area, Category, Goods,
 VideoCourse, StudyCheckIn, ExamQuestion, ExamRecord, Certification, User, Cart, Recipient,
                     Address, Order,GoodsImage,Coupon,ExpressLogistics)

admin.site.register(Welcome)
admin.site.register(Banner)
admin.site.register(Notice)
admin.site.register(Index_Annonce)
admin.site.register(UserInfo)
admin.site.register(Area)
admin.site.register(Category)
admin.site.register(Goods)
admin.site.register(GoodsImage)
admin.site.register(VideoCourse)
admin.site.register(StudyCheckIn)
admin.site.register(ExamQuestion)
admin.site.register(ExamRecord)
admin.site.register(Certification)
admin.site.register(Cart)
admin.site.register(Recipient)
admin.site.register(Address)
admin.site.register(Order)
admin.site.register(Coupon)
admin.site.register(ExpressLogistics)
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
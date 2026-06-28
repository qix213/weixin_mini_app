"""
URL配置 - 最终稳定版
"""
from django.contrib import admin
from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

# 导入视图
from . import views
from .views import (
    welcome, BannerView, Index_AnnonceView,
    CustomTokenObtainPairView, RegisterAPIView, MemberInfoView,
    SubUserConsumeView, VideoCourseViewSet,
    CartView, CartAddView, CartListView, CartUpdateNumView, CartDeleteView, CartClearView,
    RecipientView, CheckoutView, AddressView, AddressManageView, AddressDetailView, SetDefaultAddressView,
    OrderAddView, OrderListView, GiveRegisterPointsView, OrderPaySuccessView
)

# ✅ 关键：添加子应用命名空间
app_name = 'app01'

# 初始化路由路由器
router = SimpleRouter()
router.register('banner', BannerView, basename='banner')
router.register(r'categories', views.CategoryView, basename='category')
router.register(r'goods', views.GoodsViewSet, basename='goods')
router.register(r'video_courses', VideoCourseViewSet)
router.register(r'check-in', views.StudyCheckInViewSet, basename='study_check_in')
router.register(r'exam_questions', views.ExamQuestionViewSet, basename='exam_question')
router.register(r'exam_records', views.ExamRecordViewSet, basename='exam_record')
router.register(r'certifications', views.CertificationViewSet, basename='certification')
router.register(r'benefits', views.BenefitViewSet, basename='benefits')
router.register(r'profile', views.UserProfileViewSet, basename='profile')

# 主路由配置
urlpatterns = [
    path('welcome/', welcome),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterAPIView.as_view(), name='register'),

    path('member/sub-consume/', SubUserConsumeView.as_view(), name='sub_consume'),
    path('member/info/', MemberInfoView.as_view(), name='member_info'),
    path('member/give-register-points/', GiveRegisterPointsView.as_view(), name='give_register_points'),

    path('index_annonce/', Index_AnnonceView.as_view(), name='index_annonce'),

    # 购物车
    path('cart/', CartView.as_view()),
    path('cart/<int:cart_id>/', CartView.as_view()),
    path('cart/add/', CartAddView.as_view()),
    path('cart/list/', CartListView.as_view()),
    path('cart/update_num/', CartUpdateNumView.as_view()),
    path('cart/delete/', CartDeleteView.as_view()),
    path('cart/clear/', CartClearView.as_view()),
    path('cart/clear/<int:order_id>/', CartClearView.as_view()),

    # 地址
    path('recipient/', RecipientView.as_view()),
    path('checkout/', CheckoutView.as_view()),
    path('address/', AddressView.as_view()),
    path('address/list/', AddressManageView.as_view(), name='address-list'),
    path('address/add/', AddressManageView.as_view(), name='address-add'),
    path('address/<int:pk>/', AddressDetailView.as_view(), name='address-detail'),
    path('address/<int:pk>/set_default/', SetDefaultAddressView.as_view(), name='address-set-default'),

    path('area/list/', views.AreaListView.as_view(), name='area_list'),

    # 订单
    path('order/add/', OrderAddView.as_view()),
    path('order/list/', OrderListView.as_view()),
    path('order/detail/', views.OrderDetailView.as_view()),
    path('order/pay_success/', OrderPaySuccessView.as_view(), name='order_pay_success'),

    path('send-sms/', views.send_sms_code),
    path('verify-sms/', views.verify_sms_code),
    path('video_proxy/', views.video_proxy, name='video_proxy'),

    # 优惠券/积分
    path('user/coupons/', views.UserCouponView.as_view(), name='user_coupons'),
    path('user/coupons/use/', views.UserCouponUseView.as_view(), name='user_coupon_use'),
    path('coupon/claim/', views.claim_coupon),
    path('user/points/', views.UserPointsView.as_view(), name='user_points'),
    path('user/points/deduct/', views.DeductPointsView.as_view(), name='deduct_points'),
    path('user/stats/', views.get_user_stats),

    # 快递
    path("express/create/", views.express_create, name="express_create"),
    path("express/list/", views.express_list, name="express_list"),

    # AI
    path("ai/chat/", views.ai_chat_api, name="ai_chat"),
    path("ai/history/", views.get_chat_history_api, name="ai_history"),

    # ===================== 京东物流路由（完全正确） =====================
    path('jd-logistics/precheck/', views.jd_order_precheck, name='jd-precheck'),
    path('jd-logistics/create-waybill/', views.jd_create_waybill, name='jd-create-waybill'),
]

urlpatterns += router.url
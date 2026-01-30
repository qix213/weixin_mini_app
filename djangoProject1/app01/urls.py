"""
URL配置 - 修复404错误 + 语法错误 + 重复路由
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

# 导入视图（整理导入顺序，避免冗余）
from . import views
from .views import (
    welcome, BannerView, Index_AnnonceView,
    CustomTokenObtainPairView, RegisterAPIView, MemberInfoView,
    SubUserConsumeView,VideoCourseViewSet,
    # 购物车相关
    CartView, CartAddView, CartListView, CartUpdateNumView, CartDeleteView, CartClearView,
    # 收件人/地址相关
    RecipientView, CheckoutView, AddressView, AddressManageView, AddressDetailView, SetDefaultAddressView,
    # 订单相关
    OrderAddView, OrderListView,
)

# 初始化路由路由器
router = SimpleRouter()
router.register('banner', BannerView, basename='banner')
router.register('collection', views.CollevtionView, basename='collection')
router.register(r'categories', views.CategoryView, basename='category')
router.register(r'goods', views.GoodsViewSet, basename='goods')
router.register(r'video_courses', VideoCourseViewSet)
router.register(r'check-in', views.StudyCheckInViewSet, basename='study_check_in')
router.register(r'exam_questions', views.ExamQuestionViewSet, basename='exam_question')
router.register(r'exam_records', views.ExamRecordViewSet, basename='exam_record')
router.register(r'certifications', views.CertificationViewSet, basename='certification')
router.register(r'benefits', views.BenefitViewSet, basename='benefits')
router.register(r'profile', views.UserProfileViewSet, basename='profile')

# 核心修复：去掉路径中的app01前缀（根urls已配置app01/）
urlpatterns = [
    path('welcome/', welcome),
    # 登录/刷新Token
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # 注册
    path('register/', RegisterAPIView.as_view(), name='register'),
    # 会员相关
    path('member/sub-consume/', SubUserConsumeView.as_view(), name='sub_consume'),
    path('member/info/', MemberInfoView.as_view(), name='member_info'),  # 修复重复路由：只保留一个
    # 首页公告
    path('index_annonce/', Index_AnnonceView.as_view(), name='index_annonce'),
    # 购物车接口
    path('cart/', CartView.as_view()),
    path('cart/<int:cart_id>/', CartView.as_view()),
    path('cart/add/', CartAddView.as_view()),
    path('cart/list/', CartListView.as_view()),
    path('cart/update_num/', CartUpdateNumView.as_view()),
    path('cart/delete/', CartDeleteView.as_view()),
    path('cart/clear/', CartClearView.as_view()),
    path('cart/clear/<int:order_id>/', CartClearView.as_view()),
    # 收件人接口
    path('recipient/', RecipientView.as_view()),
    path('checkout/', CheckoutView.as_view()),
    # 地址接口（核心修复：去掉app01前缀）
    path('address/', AddressView.as_view()),
    path('address/list/', AddressManageView.as_view(), name='address-list'),
    path('address/add/', AddressManageView.as_view(), name='address-add'),
    path('address/<int:pk>/', AddressDetailView.as_view(), name='address-detail'),
    path('address/<int:pk>/set_default/', SetDefaultAddressView.as_view(), name='address-set-default'),
    # 订单接口
    path('order/add/', OrderAddView.as_view()),
    path('order/list/', OrderListView.as_view()),
    path('order/detail/', views.OrderDetailView.as_view()),
    # 短信验证码
    path('send-sms/', views.send_sms_code),
    path('verify-sms/', views.verify_sms_code),
]

# 修复语法错误：单独拼接router.urls，避免和导入语句混写
urlpatterns += router.urls
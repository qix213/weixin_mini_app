"""
URL configuration for djangoProject1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from .views import welcome, BannerView
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (BannerView, CollevtionView, CategoryView, GoodsViewSet,
    CourseCategoryViewSet, VideoCourseViewSet, StudyCheckInViewSet,
    ExamQuestionViewSet, ExamRecordViewSet, CertificationViewSet,
    CustomTokenObtainPairView, RegisterAPIView, BenefitViewSet, UserProfileViewSet,
    MemberInfoView,Index_AnnonceView, CartView, CartAddView, CartListView, CartUpdateNumView, CartDeleteView,
    RecipientView, CheckoutView, AddressView, AddressAddView, OrderAddView, UserRecommendCodeView, SubUserConsumeView,)
from . import views  # 导入视图函数

router = SimpleRouter()
router.register('banner', BannerView, basename='banner')
router.register('collection', CollevtionView, basename='collection')
router.register(r'categories', CategoryView, basename='category')
router.register(r'goods', GoodsViewSet, basename='goods')
router.register(r'course_categories', CourseCategoryViewSet, basename='course_category')
router.register(r'video_categories', VideoCourseViewSet, basename='video_category')
router.register(r'check-in', StudyCheckInViewSet, basename='study_check_in')
router.register(r'exam_questions', ExamQuestionViewSet, basename='exam_question')
router.register(r'exam_records', ExamRecordViewSet, basename='exam_record')
router.register(r'certifications', CertificationViewSet, basename='certification')
router.register(r'benefits', BenefitViewSet, basename='benefits')
router.register(r'profile', UserProfileViewSet, basename='profile')


urlpatterns = [
    path('welcome/', welcome),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterAPIView.as_view(), name='register'),
    # 新增：获取自身推荐码
    path('user/recommend-code/', UserRecommendCodeView.as_view(), name='user_recommend_code'),
    # 新增：查看下级消费记录
    path('user/sub-consume/', SubUserConsumeView.as_view(), name='sub_consume'),
    path('member/info/', MemberInfoView.as_view(), name='member_info'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    # 可选：Token 刷新地址 /app01/token/refresh/
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('index_annonce/', Index_AnnonceView.as_view(), name='index_annonce'),
    path('member/info/', MemberInfoView.as_view(), name='member_info'),
    path('cart/', CartView.as_view()),
    path('cart/<int:cart_id>/', CartView.as_view()), # 新增：修改/删除 (PUT/DELETE) 路径带cart_id
    path('cart/add/', CartAddView.as_view()),  # 加入购物车
    path('cart/list/', CartListView.as_view()),  # 购物车列表
    path('cart/update_num/', CartUpdateNumView.as_view()),  # 修改数量
    path('cart/delete/', CartDeleteView.as_view()),  # 删除商品
    # 收件人信息接口
    path('recipient/', RecipientView.as_view()),
    # 结算接口
    path('checkout/', CheckoutView.as_view()),
    path('address/', AddressView.as_view()),
    path('address/add/', AddressAddView.as_view()),
    # 订单
    path('order/add/', OrderAddView.as_view()),
    # 你的其他接口（如注册接口 /register/）
    path('', include(router.urls)),
    path('send-sms/', views.send_sms_code),  # 发送验证码
    path('verify-sms/', views.verify_sms_code),  # 验证验证码
]
urlpatterns += router.urls
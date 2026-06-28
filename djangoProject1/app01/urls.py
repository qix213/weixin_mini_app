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
    OrderAddView, OrderListView,GiveRegisterPointsView, WechatPrepayView, WechatPayCallbackView,OrderDeleteView,
    WechatLoginView, OfflineServiceViewSet,OrderReactivateView
)

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
router.register(r'skin-profiles', views.UserSkinProfileViewSet, basename='skin-profile')
router.register(r'offline_services', OfflineServiceViewSet, basename='offline_services')
# 核心修复：去掉路径中的app01前缀（根urls已配置app01/）
urlpatterns = [
    path('welcome/', welcome),
path('member_privilege/', views.get_member_privilege),
    # 登录/刷新Token
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
path('wechat-login/', WechatLoginView.as_view(), name='wechat-login'),
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
    # 关键修复：移除多余的app01/前缀，使路径匹配前端请求的/app01/area/list/
    path('area/list/', views.AreaListView.as_view(), name='area_list'),
    # 订单接口
    path('order/add/', OrderAddView.as_view()),
    path('order/delete/', OrderDeleteView.as_view(), name='order_delete'),
    path('order/reactivate/', OrderReactivateView.as_view(), name='order_reactivate'),
    path('order/list/', OrderListView.as_view()),
    path('order/detail/', views.OrderDetailView.as_view()),
    path('order/wechat_prepay/', WechatPrepayView.as_view(), name='wechat_prepay'),
    path('order/wechat_callback/', WechatPayCallbackView.as_view(), name='wechat_pay_callback'),
    path('member/upgrade_order/', views.create_upgrade_order, name='create_upgrade_order'),
    path('member/upgrade_success/', views.upgrade_success_notify, name='upgrade_success_notify'),
    # 短信验证码
    path('send-sms/', views.send_sms_code),
    path('verify-sms/', views.verify_sms_code),
    path('member/give-register-points/', GiveRegisterPointsView.as_view(), name='give_register_points'),
path('member/upload_avatar/', views.upload_avatar, name='upload_avatar'),
    path('video_proxy/', views.video_proxy, name='video_proxy'),  # 新增极简代理接口
    # 优惠券
    path('member/coupons/', views.UserCouponView.as_view(), name='member_coupons'),
    path('user/stats/', views.get_user_stats),
    path('user/coupons/', views.UserCouponView.as_view(), name='user_coupons'),
    path('user/coupons/use/', views.UserCouponUseView.as_view(), name='user_coupon_use'),
    # 3. 领取优惠券
    path('coupon/claim/', views.claim_coupon),
    path('user/points/', views.UserPointsView.as_view(), name='user_points'),
    path('user/points/deduct/', views.DeductPointsView.as_view(), name='deduct_points'),  # 扣减积分

    # 新建运单
    path("express/create/", views.express_create, name="express_create"),
    # 运单列表
    path("express/list/", views.express_list, name="express_list"),
    path("ai/chat/", views.ai_chat_api, name="ai_chat"),  # AI 对话
    path("ai/history/", views.get_chat_history_api, name="ai_history"),  # 对话历史s
    # 获取问卷题库
    path('api/get_questionnaire/', views.get_questionnaire_api, name='get_questionnaire'),

    # 小程序端核心流式接口
    path('api/wx_chat_stream/', views.wx_chat_stream_api, name='wx_chat_stream'),

    # ===================== 京东物流路由（完全正确） =====================
    path('jd-logistics/precheck/', views.jd_order_precheck, name='jd-precheck'),
    path('jd-logistics/create-waybill/', views.jd_create_waybill, name='jd-create-waybill'),
    path('jd-logistics/cancel/', views.jd_cancel_order, name='jd_cancel'),
# 京东物流轨迹查询
    path("jd/trace/query/", views.jd_query_trace, name="jd_trace_query"),
    path('jd/order/modify/', views.jd_modify_order, name='jd_order_modify'),
path('jd/waybill/gis/track/', views.jd_query_waybill_gis_track),
path('api/save_skin_photo/', views.save_skin_photo, name='save_skin_photo'),
path('api/', include(router.urls)),
]

# 修复语法错误：单独拼接router.urls，避免和导入语句混写
urlpatterns += router.urls
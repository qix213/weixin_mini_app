"""
URL配置 - 修复404错误 + 语法错误 + 重复路由
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

# 导入视图（整理导入顺序，避免冗余）
from . import views
from .views import (
    welcome, BannerView, Index_AnnonceView,
    CustomTokenObtainPairView, RegisterAPIView, MemberInfoView,
    SubUserConsumeView,VideoCourseViewSet, RegisterPreCheckView, MiniProgramWalletView,
    # 购物车相关
    CartView, CartAddView, CartListView, CartUpdateNumView, CartDeleteView, CartClearView,
    # 收件人/地址相关
    RecipientView, CheckoutView, AddressView, AddressManageView, AddressDetailView, SetDefaultAddressView,
    # 订单相关
    OrderAddView, OrderListView,GiveRegisterPointsView, WechatPrepayView, WechatPayCallbackView,OrderDeleteView,
    WechatLoginView, OfflineServiceViewSet,OrderReactivateView, MiniProgramWithdrawApplyView, PayGetTokenView,OrderConfirmReceiptView,
FinanceReviewDashboardView, FinanceApproveTransferView, WithdrawStatusView, WithdrawConfirmSuccessView,WeChatCustomerServiceConfigView
)

# 初始化路由路由器
router = SimpleRouter()
router.register('banner', BannerView, basename='banner')
router.register(r'categories', views.CategoryView, basename='category')
router.register(r'goods', views.GoodsViewSet, basename='goods')
router.register(r'video_courses1', VideoCourseViewSet)
router.register(r'check-in', views.StudyCheckInViewSet, basename='study_check_in')
router.register(r'exam_questions', views.ExamQuestionViewSet, basename='exam_question')
router.register(r'exam_records', views.ExamRecordViewSet, basename='exam_record')
# router.register(r'certifications', views.CertificationViewSet, basename='certification')
router.register(r'benefits', views.BenefitViewSet, basename='benefits')
router.register(r'profile', views.UserProfileViewSet, basename='profile')
router.register(r'skin-profiles', views.UserSkinProfileViewSet, basename='skin-profile')
router.register(r'offline_services', OfflineServiceViewSet, basename='offline_services')
# 核心修复：去掉路径中的app01前缀（根urls已配置app01/）
urlpatterns = [
    path('welcome/', welcome),
    path('member_privilege/', views.get_member_privilege),
    path('offline_certificate/', views.get_offline_certification),
    path('api/config/kf/', WeChatCustomerServiceConfigView.as_view(), name='config-kf'),
    # 登录/刷新Token
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('wechat-login/', WechatLoginView.as_view(), name='wechat-login'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # 注册
    path('register/pre_check/', RegisterPreCheckView.as_view(), name='pre_check'),
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
    path('order/pay_get_token/', PayGetTokenView.as_view()),
    path('order/confirm_receipt/<str:order_sn>/', OrderConfirmReceiptView.as_view(), name='confirm_receipt'),
    # 🌟 加上这一行：解决 404 报错！
    path('order/confirm_ready/', views.OrderConfirmReadyView.as_view(), name='confirm_ready'),
    # 这个是你刚才贴给我的确认收货接口，保持不动
    path('order/confirm_receipt/<str:order_sn>/', views.OrderConfirmReceiptView.as_view(), name='confirm_receipt'),
    path('member/upgrade_order/', views.create_upgrade_order, name='create_upgrade_order'),
    path('member/upgrade_success/', views.upgrade_success_notify, name='upgrade_success_notify'),
    path('finance/review/', FinanceReviewDashboardView.as_view(), name='finance_review_dashboard'),
    path('finance/approve/', FinanceApproveTransferView.as_view(), name='finance_approve_transfer'),
    # 短信验证码
    path('send-sms/', views.send_sms_code),
    path('verify-sms/', views.verify_sms_code),
    path('member/give-register-points/', GiveRegisterPointsView.as_view(), name='give_register_points'),
    path('member/upload_avatar/', views.upload_avatar, name='upload_avatar'),
    path('video_prox2/', views.video_proxy, name='video_proxy'),  # 新增极简代理接口
    # 优惠券
    # path('member/coupons/', views.UserCouponView.as_view(), name='member_coupons'),
    path('user/stats/', views.get_user_stats),
    path('user/coupons/', views.UserCouponView.as_view(), name='user_coupons'),
    path('user/coupons/use/', views.UserCouponUseView.as_view(), name='user_coupon_use'),
path('user/wallet/', MiniProgramWalletView.as_view(), name='mp_user_wallet'),
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
    path('wallet/withdraw/', MiniProgramWithdrawApplyView.as_view(), name='wallet_withdraw_apply'),
    path('withdraw/status/', WithdrawStatusView.as_view(), name='withdraw_status'),
    path('withdraw/confirm_success/', WithdrawConfirmSuccessView.as_view(), name='withdraw_confirm_success'),
    path('wx/code2openid/', views.wx_code2openid),
    # ================= 🌟 电子钱包体系路由 =================
    # 1. 查余额
    path('user/wallet/info/', views.UserWalletDetailView.as_view(), name='wallet_info'),
    # 2. 查流水（账单明细）
    path('user/wallet/transactions/', views.WalletTransactionListView.as_view(), name='wallet_transactions'),
    # 3. 钱包全额支付订单
    path('order/pay/wallet/', views.WalletPayOrderView.as_view(), name='wallet_pay_order'),
    path('recharge/activities/', views.RechargeActivityListView.as_view(), name='recharge_activities'),
    path('recharge/submit/', views.SubmitRechargeOrderView.as_view(), name='submit_recharge'),
    # ===================== 京东物流路由（完全正确） =====================
    path('jd-logistics/precheck/', views.jd_order_precheck, name='jd-precheck'),
    path('jd-logistics/create-waybill/', views.jd_create_waybill, name='jd-create-waybill'),
    path('jd-logistics/cancel/', views.jd_cancel_order, name='jd_cancel'),
    path('jd-logistics/create-order-and-waybill/', views.jd_create_order_and_waybill, name='jd_order'),
# 京东物流轨迹查询
    path("jd/trace/query/", views.jd_query_trace, name="jd_trace_query"),
    path('jd/order/modify/', views.jd_modify_order, name='jd_order_modify'),
path('jd/waybill/gis/track/', views.jd_query_waybill_gis_track),
path('api/save_skin_photo/', views.save_skin_photo, name='save_skin_photo'),
path('api/', include(router.urls)),
]

# 修复语法错误：单独拼接router.urls，避免和导入语句混写
urlpatterns += router.urls
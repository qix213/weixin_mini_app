const api = require('../../config/settings.js');
const app = getApp();

Page({
  data: {
    banner_list: [{ img: '' }], 
    notice: 'xxx产品正在7折促销~', 
    isLogin: false, 
    fixed_images: [], 
    star_goods: [], 
    content: '', 
    userInfo: {}, 
    loading: true, 
    memberInfo: {}, 
    isAdminMember: false 
  },

  onLoad() {
    this.syncGlobalUserState();
    this.loadHomeData().finally(() => {
      this.setData({ loading: false });
    });
    setTimeout(() => {
      this.setData({ showAiPopup: true });
    }, 1000);
  },

  onShow() {
    this.syncGlobalUserState();
    if (this.data.isLogin) {
      this.getMemberInfo();
    }
  },
// 阻止蒙层滑动穿透到底部页面
preventTouchMove() {
  return;
},

// 点击取消 / 蒙层关闭弹窗
closeAiPopup() {
  this.setData({ showAiPopup: false });
},

// 点击体验跳转
toAiChat() {
  this.closeAiPopup(); // 先关闭弹窗
  
  // 请将此处路径替换为你实际的 AI Chat 页面路径
  wx.navigateTo({
    url: '/pages/ai-chat/ai-chat', 
    fail: (err) => {
      // 兜底方案：如果 ai-chat 是在底部 tabBar 上，需要用 switchTab 跳转
      wx.switchTab({
        url: '/pages/ai-chat/ai-chat'
      });
    }
  });
},
  syncGlobalUserState() {
    const isLogin = app.globalData.isLogin;
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    const userType = Number(memberInfo.user_type || 0);
    
    this.setData({
      isLogin: isLogin,
      userInfo: memberInfo,
      memberInfo: memberInfo,
      isAdminMember: isLogin && [5].includes(userType)
    });
  },

  getMemberInfo() {
    app.request({
      url: '/app01/member/info/',
      method: 'GET'
    }).then(res => {
      if (res.data.code === 200) {
        const memberInfo = res.data.data;
        app.globalData.memberInfo = memberInfo;
        wx.setStorageSync('memberInfo', memberInfo);

        const userType = Number(memberInfo.user_type || 0);
        this.setData({
          userInfo: memberInfo,
          memberInfo: memberInfo,
          isAdminMember: [5].includes(userType)
        });
      }
    }).catch(err => {
      console.error('❌ 会员信息同步失败：', err);
    });
  },

  loadHomeData() {
    return Promise.all([
      this.fetchBannerData(), 
      this.fetchFixedImages(),
      this.fetchStarGoods()
    ]);
  },

  fetchStarGoods() {
    return app.request({
      url: '/app01/goods/',
      method: 'GET'
    }).then(res => {
      if (res.data && res.data.code === 200) {
        const allGoods = res.data.data.results || [];
        const starGoods = allGoods.filter(item => item.is_star).map(item => ({
          id: item.id,
          name: item.name,
          image: item.image_url?.startsWith('http') ? item.image_url : `${app.globalData.baseUrl}${item.image_url || ''}`,
          price: item.member_price || item.price,
          original_price: item.original_price
        }));
        this.setData({ star_goods: starGoods });
      }
    }).catch(err => console.error('❌ 获取明星产品失败：', err));
  },

  fetchBannerData() {
    return app.request({
      url: api.banner
    }).then(res => {
      const resData = res.data;
      if (resData.code === 100) {
        const bannerArray = resData.banner?.results || (Array.isArray(resData.banner) ? resData.banner : []);
        this.setData({ 
          banner_list: bannerArray, 
          notice: resData.notice?.title || this.data.notice,
          content: resData.notice?.content || '',
          
        });
      }
    }).catch(err => console.error('❌ 获取轮播图失败：', err));
  },

  fetchFixedImages() {
    return app.request({
      url: '/app01/index_annonce/'
    }).then(res => {
      if (res.data && res.data.code === 200) {
        const rawImages = res.data.fixed_images || [];
        const fixedImages = rawImages.map(item => ({
          img: item?.img_url?.startsWith('http') ? item.img_url : `${app.globalData.baseUrl}${item?.img_url || item?.img || ''}`,
          id: item?.id || '',
          title: item?.title || ''
        }));
        this.setData({ fixed_images: fixedImages });
      }
    }).catch(err => console.error('❌ 获取固定图失败：', err));
  },

  // ========== 路由跳转 ==========
  goToOrderList() {
    if (!this.data.isAdminMember) return wx.showToast({ title: '暂无订单权限', icon: 'none' });
    wx.navigateTo({ url: '/pages/order-workbench/order-workbench' });
  },

  // 🌟 新增：跳转用户管理工作台
  goToUserWorkbench() {
    if (!this.data.isAdminMember) return wx.showToast({ title: '暂无用户管理权限', icon: 'none' });
    wx.navigateTo({ url: '/pages/user-workbench/user-workbench' }); // 请确保页面路径正确
  },

  goToGoodsDetail(event) {
    const goodsId = event.currentTarget.dataset.goodsid;
    if (goodsId) wx.navigateTo({ url: `/pages/mall/detail?goods_id=${goodsId}` });
  },

  goToLogin() { wx.navigateTo({ url: '/pages/login/login' }); },
  goToRegister() { wx.navigateTo({ url: '/pages/register/register' }); }
});
const app = getApp();
Page({
  data: {
    isLogin: false,
    memberInfo: {}, // 完整会员信息
    showQrcode: false,
    points: 0, 
    couponCount: 0, 
    // 🌟 核心修改：移除 0星，坐标轴仅保留 1星、2星、3星
    levelConfig: [
      { value: 2, cost: 980, name: '蓝朋友1星', shortName: '1星' },
      { value: 3, cost: 3980, name: '蓝朋友2星', shortName: '2星' },
      { value: 4, cost: 9800, name: '蓝朋友3星', shortName: '3星' }
    ]
  },

  onShow() {
    this.syncGlobalState();
    if (this.data.isLogin) {
      this.getMemberInfo();
      this.getValidCouponCount(); 
    }
  },

  checkLogin(redirectPage = '') {
    if (!this.data.isLogin) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再操作',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            let loginUrl = '/pages/login/login';
            if (redirectPage) {
              loginUrl += `?redirect=${encodeURIComponent(redirectPage)}`;
            }
            wx.navigateTo({ url: loginUrl });
          }
        }
      });
      return false;
    }
    return true;
  },

  goToSubMemberConsume() {
    if (!this.checkLogin('/pages/my/my?action=subMemberConsume')) return;
    const currentLevel = this.data.memberInfo.user_type;
    if (!currentLevel) {
      wx.showToast({ title: '会员等级未获取，请刷新页面', icon: 'none' });
      return;
    }
    if (currentLevel === 1) {
      wx.showToast({ title: '当前会员等级无查看下级消费记录权限', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: `/pages/sub-member-consume/sub-member-consume?currentLevel=${currentLevel}` });
  },

  goToBillRecord() {
    if (!this.checkLogin('/pages/my/my?action=billRecord')) return;
    wx.navigateTo({ url: '/pages/bill-record/bill-record' });
  },

  goToMemberCenter() {
    wx.navigateTo({ 
      url: '/pages/my/benefits', 
      success: () => {},
      fail: (err) => {
        console.error("跳转失败", err);
      }
    });
  },

  goToPoints() {
    if (!this.checkLogin('/pages/my/my?action=points')) return;
    wx.navigateTo({ url: '/pages/points/points' });
  },

  goToCoupon() {
    if (!this.checkLogin('/pages/my/my?action=coupon')) return;
    if (this.data.couponCount === 0) {
      wx.showToast({ title: '暂无可用优惠券', icon: 'none', duration: 1500 });
      return; 
    }
    wx.navigateTo({
      url: '/pages/coupun/coupun',
      fail: (err) => console.error('跳转失败：', err)
    });
  },

  goToAddressManage() {
    if (!this.checkLogin('/pages/my/my?action=address')) return;
    wx.navigateTo({ url: '/pages/address/address' });
  },

  goToInvoiceManage() {
    if (!this.checkLogin('/pages/my/my?action=invoice')) return;
    wx.navigateTo({ url: '/pages/order-list/order-list' });
  },

  goToSetting() {
    if (!this.checkLogin('/pages/my/my?action=setting')) return;
    wx.navigateTo({ url: '/pages/setting/setting' });
  },

  syncGlobalState() {
    const app = getApp();
    const memberInfo = app.globalData.memberInfo || {};
    this.setData({
      isLogin: app.globalData.isLogin || false,
      memberInfo: memberInfo,
      points: memberInfo.points || 0 
    });
  },

  getMemberInfo() {
    const app = getApp();
    const header = app.getRequestHeader();

    wx.showLoading({ title: '加载会员信息...', mask: true });
    wx.request({
      url: app.globalData.baseUrl + '/app01/member/info/',
      method: 'GET',
      header: header,
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          const memberInfo = res.data.data;

          const currentType = memberInfo.user_type || 1;
          const actualStars = Math.max(0, currentType - 1);
          memberInfo.starsArray = Array.from({ length: actualStars }, (v, i) => i);

          const joinDateStr = memberInfo.date_joined || memberInfo.create_time; 
          if (joinDateStr) {
            const safeDateStr = joinDateStr.substring(0, 10).replace(/-/g, '/');
            const joinDate = new Date(safeDateStr);
            joinDate.setFullYear(joinDate.getFullYear() + 1);
            const year = joinDate.getFullYear();
            const month = String(joinDate.getMonth() + 1).padStart(2, '0');
            const day = String(joinDate.getDate()).padStart(2, '0');
            memberInfo.expire_time_text = `${year}-${month}-${day}`;
          } else {
            memberInfo.expire_time_text = '永久有效'; 
          }

          const levelCosts = { 1: 0, 2: 980, 3: 3980, 4: 9800 };
          const levelNames = { 1: '蓝朋友0星', 2: '蓝朋友1星', 3: '蓝朋友2星', 4: '蓝朋友3星' };

          if (currentType < 4) {
            memberInfo.nextLevelDiff = levelCosts[currentType + 1] - levelCosts[currentType];
            memberInfo.nextLevelName = levelNames[currentType + 1];
          } else {
            memberInfo.nextLevelDiff = 0; 
          }
          
          memberInfo.user_type_text = levelNames[currentType] || '蓝朋友0星';

          app.globalData.memberInfo = memberInfo; 
          
          this.setData({
            memberInfo: memberInfo,
            points: memberInfo.points || 0,
            isLogin: true
          });
        } else {
          wx.showToast({ title: res.data.msg || '加载会员信息失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: '加载会员信息失败', icon: 'none' });
        this.setData({ points: 0 });
      }
    });
  },

  getValidCouponCount() {
    const app = getApp();
    const header = app.getRequestHeader();
    
    wx.request({
      url: app.globalData.baseUrl + '/app01/user/coupons/',
      method: 'GET',
      header: header,
      data: { only_valid: true },
      success: (res) => {
        if (res.data.code === 200) {
          let couponList = res.data.data?.coupons || [];
          const now = new Date().getTime(); 
          const validCoupons = couponList.filter(coupon => {
            const isUnused = !coupon.is_used && coupon.is_used !== 1;
            let expireTime = coupon.end_time || coupon.expire_time;
            if (!expireTime) return true; 
            if (typeof expireTime === 'string') {
              expireTime = new Date(expireTime).getTime();
            }
            return isUnused && (expireTime > now);
          });
          this.setData({ couponCount: validCoupons.length });
        } else {
          this.setData({ couponCount: 0 });
        }
      },
      fail: () => {
        this.setData({ couponCount: 0 });
      }
    });
  },

  goToLogin() { wx.navigateTo({ url: '/pages/login/login' }); },

  previewQrcode() {
    this.setData({ showQrcode: true });
    wx.showToast({ title: '长按二维码关注公众号', icon: 'none', duration: 2000 });
  },

  hideQrcode() { this.setData({ showQrcode: false }); },

  goToCustomerService() { wx.navigateTo({ url: '/pages/service/service' }); },

  goToLogout() {
    const app = getApp();
    wx.removeStorageSync('hakelong');
    wx.clearStorageSync();
    app.globalData = { ...app.globalData, isLogin: false, accessToken: '', memberInfo: {} };
    this.setData({ isLogin: false, memberInfo: {}, couponCount: 0 });
    wx.reLaunch({ url: '/pages/index/index' });
    wx.showToast({ title: '退出登录成功', icon: 'success' });
  },

  goToAIChat() {
    if (!this.checkLogin('/pages/my/my?action=aiChat')) return;
    wx.navigateTo({ url: '/pages/ai-chat/ai-chat' });
  },
});
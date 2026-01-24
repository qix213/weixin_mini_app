// pages/mine/mine.js
Page({
  data: {
    isLogin: false,
    memberInfo: {}, // 完整会员信息（渲染到页面）
    showQrcode: false
  },

  onShow() {
    // 同步全局登录状态
    this.syncGlobalState();
    // 若已登录，请求会员详情
    if (this.data.isLogin) {
      this.getMemberInfo();
    }
  },

  // 同步全局登录状态
  syncGlobalState() {
    const app = getApp();
    this.setData({
      isLogin: app.globalData.isLogin,
      memberInfo: app.globalData.memberInfo || {}
    });
  },

  // 核心：请求会员信息接口
  getMemberInfo() {
    const app = getApp();
    const header = app.getRequestHeader();
    console.log('请求头：', header); // 查看 Authorization 是否为正确格式
    console.log('accessToken：', app.globalData.accessToken); // 查看 Token 是否为空
  
    wx.showLoading({ title: '加载会员信息...', mask: true });
    wx.request({
      url: app.globalData.baseUrl + '/app01/member/info/',
      method: 'GET',
      header: header,
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          // 存储会员信息到全局和页面
          const memberInfo = res.data.data;
          app.globalData.memberInfo = memberInfo;
          this.setData({
            memberInfo: memberInfo
          });
          console.log('会员信息加载成功：', memberInfo);
        } else {
          wx.showToast({ title: res.data.msg || '加载会员信息失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        console.error('会员信息请求失败：', err);
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // 跳转登录页
  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login',
    });
  },

  // 跳转会员中心
  goToMemberCenter() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/member-center/member-center',
    });
  },

  // 跳转积分页面
  goToPoints() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/points/points',
    });
  },

  // 跳转礼券页面
  goToCoupon() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/coupon/coupon',
    });
  },

  // 跳转地址管理
  goToAddressManage() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/address/address',
    });
  },

  // 跳转发票管理
  goToInvoiceManage() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/invoice/invoice',
    });
  },

  // 预览公众号二维码
  previewQrcode() {
    this.setData({ showQrcode: true });
  },

  // 隐藏二维码弹窗
  hideQrcode() {
    this.setData({ showQrcode: false });
  },

  // 跳转我的客服
  goToCustomerService() {
    wx.navigateTo({
      url: '/pages/service/service',
    });
  },

  // 跳转设置页面
  goToSetting() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/setting/setting',
    });
  },

  // 退出跳转首页页面
  goToLogout() {
    //wx.removeStorageSync('hakelong'); // 清除特定的token
    wx.clearStorageSync(); // 清除所有本地缓存
    wx.reLaunch({
      url: '/pages/index/index' // 跳转到首页或登录页
    })
  }
});
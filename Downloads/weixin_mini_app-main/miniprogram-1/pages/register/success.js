Page({
  data: {
    memberType: '',
    benefits: []
  },

  onLoad(options) {
    const userInfo = wx.getStorageSync('userInfo') || {};
    this.setData({
      memberType: userInfo.memberType || options.type,
      benefits: userInfo.权益 || []
    });
  },

  // 跳转首页
  toHome() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  // 跳转我的
  toMine() {
    wx.switchTab({ url: '/pages/mine/mine' });
  }
});
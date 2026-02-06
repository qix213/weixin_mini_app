Page({
  data: {
    isLogin: false,
    memberInfo: {}, // 完整会员信息（渲染到页面）
    showQrcode: false,
    points: 0// 新增：积分单独字段（也可直接用memberInfo.points，二选一）
  },

  onShow() {
    // 同步全局登录状态
    this.syncGlobalState();
    // 若已登录，请求会员详情
    if (this.data.isLogin) {
      this.getMemberInfo();
    }
  },

  // ========== 核心优化：统一登录校验方法 ==========
  /**
   * 登录校验工具方法
   * @param {String} redirectPage - 登录后需要回跳的页面路径（可选）
   * @returns {Boolean} - 是否已登录
   */
  checkLogin(redirectPage = '') {
    if (!this.data.isLogin) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再操作',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            // 跳转登录页，并携带回跳参数（支持登录后返回原操作页面）
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

  // ========== 业务跳转方法（复用登录校验） ==========
  // 跳转推荐会员消费记录页面（带权限判断）
  goToSubMemberConsume() {
    // 1. 登录校验（携带回跳参数）
    if (!this.checkLogin('/pages/mine/mine?action=subMemberConsume')) {
      return;
    }

    // 2. 会员等级校验
    const currentLevel = this.data.memberInfo.user_type;
    if (!currentLevel) {
      wx.showToast({ title: '会员等级未获取，请刷新页面', icon: 'none' });
      return;
    }

    // 权限控制逻辑：
    // 1级：无下级可查看；2级：仅看1级；3级：看1-2级；4级：看1-3级；5级：看1-4级
    if (currentLevel === 1) {
      wx.showToast({ title: '当前会员等级无查看下级消费记录权限', icon: 'none' });
      return;
    }

    // 3. 跳转消费记录页面，并传递当前会员等级
    wx.navigateTo({
      url: `/pages/sub-member-consume/sub-member-consume?currentLevel=${currentLevel}`,
    });
  },

  // 新增：跳转账单记录页面（核心需求）
  goToBillRecord() {
    // 登录校验（携带回跳参数）
    if (!this.checkLogin('/pages/mine/mine?action=billRecord')) {
      return;
    }
    // 跳账单记录页
    wx.navigateTo({
      url: '/pages/bill-record/bill-record',
    });
  },

  // 跳转会员中心
  goToMemberCenter() {
    if (!this.checkLogin('/pages/mine/mine?action=memberCenter')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/member-center/member-center',
    });
  },

  // 跳转积分页面
  goToPoints() {
    if (!this.checkLogin('/pages/mine/mine?action=points')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/points/points',
    });
  },

  // 跳转礼券页面
  goToCoupon() {
    if (!this.checkLogin('/pages/mine/mine?action=coupon')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/coupon/coupon',
    });
  },

  // 跳转地址管理
  goToAddressManage() {
    if (!this.checkLogin('/pages/mine/mine?action=address')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/address/address',
    });
  },

  // 跳转发票管理（账单相关）
  goToInvoiceManage() {
    if (!this.checkLogin('/pages/mine/mine?action=invoice')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/order-list/order-list',
    });
  },

  // 跳转设置页面
  goToSetting() {
    if (!this.checkLogin('/pages/mine/mine?action=setting')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/setting/setting',
    });
  },

  // ========== 基础方法 ==========
  // 同步全局登录状态
  syncGlobalState() {
    const app = getApp();
    const memberInfo = app.globalData.memberInfo || {};
    this.setData({
      isLogin: app.globalData.isLogin || false,
      memberInfo: memberInfo,
      points: memberInfo.points || 0 // 同步积分，默认0避免渲染报错
    });
  },

  // 核心：请求会员信息接口
  getMemberInfo() {
    const app = getApp();
    const header = app.getRequestHeader();
    console.log('请求头：', header);
    console.log('accessToken：', app.globalData.accessToken);
  
    wx.showLoading({ title: '加载会员信息...', mask: true });
    wx.request({
      url: app.globalData.baseUrl + '/app01/member/info/',
      method: 'GET',
      header: header,
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          const memberInfo = res.data.data;
          app.globalData.memberInfo = memberInfo; // 全局存储（含积分）
          // 页面存储：解构积分，设置默认值0
          this.setData({
            memberInfo: memberInfo,
            points: memberInfo.points || 0 // 关键：积分兜底0，防止undefined
          });
          console.log('会员信息加载成功（含积分）：', memberInfo);
        } else {
          wx.showToast({ title: res.data.msg || '加载会员信息失败', icon: 'none' });
        }
      },
      fail: (err) => { /* 原有逻辑不变 */ }
    });
  },

  // 直接跳转登录页（供页面登录按钮调用）
  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login',
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

  // 跳转我的客服（无需登录）
  goToCustomerService() {
    wx.navigateTo({
      url: '/pages/service/service',
    });
  },

  // ========== 优化退出登录逻辑 ==========
  goToLogout() {
    const app = getApp();
    // 1. 清除本地缓存
    wx.removeStorageSync('hakelong');
    wx.clearStorageSync();
    // 2. 清空全局登录状态（关键）
    app.globalData = {
      ...app.globalData,
      isLogin: false,
      accessToken: '',
      memberInfo: {}
    };
    // 3. 刷新页面状态
    this.setData({
      isLogin: false,
      memberInfo: {}
    });
    // 4. 跳首页（关闭所有页面，避免回退）
    wx.reLaunch({
      url: '/pages/index/index'
    });
    // 5. 提示退出成功
    wx.showToast({ title: '退出登录成功', icon: 'success' });
  }
});
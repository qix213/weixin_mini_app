Page({
  data: {
    isLogin: false,
    memberInfo: {}, // 完整会员信息（渲染到页面）
    showQrcode: false,
    points: 0, // 新增：积分单独字段（也可直接用memberInfo.points，二选一）
    couponCount: 0 // 仅统计「有效期内未使用」的优惠券数量
  },

  onShow() {
    // 同步全局登录状态
    this.syncGlobalState();
    // 若已登录，先请求会员详情，再请求有效优惠券数量
    if (this.data.isLogin) {
      this.getMemberInfo();
      this.getValidCouponCount(); // 新增：单独请求有效优惠券数量
    }
  },

  // ========== 核心优化：统一登录校验方法 ==========
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

  // ========== 业务跳转方法（复用登录校验） ==========
  goToSubMemberConsume() {
    if (!this.checkLogin('/pages/my/my?action=subMemberConsume')) {
      return;
    }

    const currentLevel = this.data.memberInfo.user_type;
    if (!currentLevel) {
      wx.showToast({ title: '会员等级未获取，请刷新页面', icon: 'none' });
      return;
    }

    if (currentLevel === 1) {
      wx.showToast({ title: '当前会员等级无查看下级消费记录权限', icon: 'none' });
      return;
    }

    wx.navigateTo({
      url: `/pages/sub-member-consume/sub-member-consume?currentLevel=${currentLevel}`,
    });
  },

  goToBillRecord() {
    if (!this.checkLogin('/pages/my/my?action=billRecord')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/bill-record/bill-record',
    });
  },

  goToMemberCenter() {
    if (!this.checkLogin('/pages/my/my?action=memberCenter')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/member-center/member-center',
    });
  },

  goToPoints() {
    if (!this.checkLogin('/pages/my/my?action=points')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/points/points',
    });
  },

  goToCoupon() {
    if (!this.checkLogin('/pages/my/my?action=coupon')) {
      return;
    }
    // 优化：使用过滤后的有效优惠券数量判断
    if (this.data.couponCount === 0) {
      console.log('有效优惠券数量为0');
      wx.showToast({ title: '暂无可用优惠券', icon: 'none', duration: 1500 });
      return; // 空页面无需跳转，提升体验
    }
    console.log('执行跳转，路径：/pages/coupun/coupun');
    wx.navigateTo({
      url: '/pages/coupun/coupun',
      fail: (err) => {
        console.error('redirectTo 跳转失败：', err);
      }
    });
  },

  goToAddressManage() {
    if (!this.checkLogin('/pages/my/my?action=address')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/address/address',
    });
  },

  goToInvoiceManage() {
    if (!this.checkLogin('/pages/my/my?action=invoice')) {
      return;
    }
    wx.navigateTo({
      url: '/pages/order-list/order-list',
    });
  },

  goToSetting() {
    if (!this.checkLogin('/pages/my/my?action=setting')) {
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
          // 页面存储：解构积分，优惠券数量不再从这里取
          this.setData({
            memberInfo: memberInfo,
            points: memberInfo.points || 0,
            isLogin: true
          });
          console.log('会员信息加载成功（含积分）：', memberInfo);
        } else {
          wx.showToast({ title: res.data.msg || '加载会员信息失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: '加载会员信息失败', icon: 'none' });
        this.setData({
          points: 0
        });
        console.error('获取会员信息失败：', err);
      }
    });
  },

  // 新增核心方法：请求优惠券列表，过滤「有效期内未使用」的券并统计数量
  getValidCouponCount() {
    const app = getApp();
    const header = app.getRequestHeader();
    
    wx.request({
      url: app.globalData.baseUrl + '/app01/user/coupons/',
      method: 'GET',
      header: header,
      data: {
        only_valid: true // 优先用后端筛选（如果后端支持）
      },
      success: (res) => {
        if (res.data.code === 200) {
          let couponList = res.data.data?.coupons || [];
          
          // 前端二次过滤（双保险）：仅保留「未使用 + 有效期内」的优惠券
          const now = new Date().getTime(); // 当前时间戳（毫秒）
          const validCoupons = couponList.filter(coupon => {
            // 1. 未使用
            const isUnused = !coupon.is_used && coupon.is_used !== 1;
            // 2. 有效期内（兼容end_time/expire_time字段，支持时间戳/字符串）
            let expireTime = coupon.end_time || coupon.expire_time;
            if (!expireTime) return true; // 无有效期视为永久有效
            
            // 转换为时间戳（处理字符串日期，如2026-12-31）
            if (typeof expireTime === 'string') {
              expireTime = new Date(expireTime).getTime();
            }
            const isInValidPeriod = expireTime > now;

            return isUnused && isInValidPeriod;
          });

          // 更新有效优惠券数量
          this.setData({
            couponCount: validCoupons.length
          });
          console.log('有效优惠券数量：', validCoupons.length, '筛选后列表：', validCoupons);
        } else {
          console.error('获取优惠券列表失败：', res.data.msg);
          this.setData({ couponCount: 0 });
        }
      },
      fail: (err) => {
        console.error('请求优惠券列表失败：', err);
        this.setData({ couponCount: 0 });
      }
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
      memberInfo: {},
      couponCount: 0 // 退出后清空优惠券数量
    });
    // 4. 跳首页（关闭所有页面，避免回退）
    wx.reLaunch({
      url: '/pages/index/index'
    });
    // 5. 提示退出成功
    wx.showToast({ title: '退出登录成功', icon: 'success' });
  }
});
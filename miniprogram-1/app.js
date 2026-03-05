App({
  // 全局数据（统一规范）
  globalData: {
    baseUrl: 'http://localhost:8000', // 后端基础地址
    isLogin: false,                   // 登录状态
    userInfo: {},                     // 用户基础信息
    memberInfo: {},                   // 会员信息
    accessToken: '',                  // JWT访问Token
    refreshToken: '',                 // 刷新Token
    goodsPointCache: {}               // 商品积分标识缓存 {goodsId: isPointGoods}
  },

  // 缓存商品积分标识
  setGoodsPointCache(goodsId, isPointGoods) {
    this.globalData.goodsPointCache[goodsId] = isPointGoods;
  },

  // 获取缓存的商品积分标识（兜底false）
  getGoodsPointCache(goodsId) {
    return this.globalData.goodsPointCache[goodsId] || false;
  },

  // 应用启动：恢复本地缓存的登录状态
  onLaunch() {
    console.log('App 启动，恢复登录状态...');
    const cached = {
      isLogin: wx.getStorageSync('isLogin') || false,
      userInfo: wx.getStorageSync('userInfo') || {},
      memberInfo: wx.getStorageSync('memberInfo') || {},
      accessToken: wx.getStorageSync('accessToken') || '',
      refreshToken: wx.getStorageSync('refreshToken') || ''
    };
    Object.assign(this.globalData, cached);
    console.log('恢复的登录状态：', {
      isLogin: this.globalData.isLogin,
      accessToken: this.globalData.accessToken ? '已存在' : '为空'
    });
  },

  // 统一请求头（Token来源唯一）
  getRequestHeader() {
    const { accessToken } = this.globalData;
    return {
      'Content-Type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
    };
  },

  // 全局请求方法（统一错误处理+Token过期）
  request(options) {
    const that = this;
    const fullUrl = options.url.startsWith('http') ? options.url : `${that.globalData.baseUrl}${options.url}`;

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: options.method || 'GET',
        data: options.data || {},
        header: that.getRequestHeader(),
        success: function (res) {
          // 401 Token过期处理
          if (res.statusCode === 401 || (res.data && res.data.code === 401)) {
            console.warn('Token过期，清除登录状态');
            that.clearLoginState();
            wx.showModal({
              title: '登录过期',
              content: '您的登录已过期，请重新登录',
              showCancel: false,
              success: () => {
                wx.redirectTo({ url: '/pages/login/login' });
              }
            });
            reject(new Error('Token已过期'));
            return;
          }
          resolve(res);
        },
        fail: function (err) {
          console.error('请求失败：', err);
          wx.showToast({ title: '网络请求失败', icon: 'none' });
          reject(err);
        }
      });
    });
  },

  // 刷新Token（进阶优化）
  refreshToken() {
    const that = this;
    const { refreshToken } = that.globalData;
    if (!refreshToken) return Promise.reject('无刷新Token');

    return new Promise((resolve, reject) => {
      wx.request({
        url: `${that.globalData.baseUrl}/app01/token/refresh/`,
        method: 'POST',
        data: { refresh: refreshToken },
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          if (res.data && res.data.access) {
            that.globalData.accessToken = res.data.access;
            wx.setStorageSync('accessToken', res.data.access);
            resolve(res.data.access);
          } else {
            that.clearLoginState();
            reject(new Error('刷新Token失败'));
          }
        },
        fail: (err) => {
          console.error('刷新Token失败：', err);
          reject(err);
        }
      });
    });
  },

  // 清除登录状态（退出/过期）
  clearLoginState() {
    wx.removeStorageSync('isLogin');
    wx.removeStorageSync('userInfo');
    wx.removeStorageSync('memberInfo');
    wx.removeStorageSync('accessToken');
    wx.removeStorageSync('refreshToken');
    this.globalData = {
      ...this.globalData,
      isLogin: false,
      userInfo: {},
      memberInfo: {},
      accessToken: '',
      refreshToken: ''
    };
  },

  // 设置登录状态（登录成功）
  setLoginState(userInfo, accessToken, refreshToken) {
    this.globalData.isLogin = true;
    this.globalData.userInfo = userInfo;
    this.globalData.accessToken = accessToken;
    this.globalData.refreshToken = refreshToken;
    wx.setStorageSync('isLogin', true);
    wx.setStorageSync('userInfo', userInfo);
    wx.setStorageSync('accessToken', accessToken);
    wx.setStorageSync('refreshToken', refreshToken);
  }
});
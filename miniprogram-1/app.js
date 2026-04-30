App({
  globalData: {
    baseUrl: 'https://101.42.20.250', 
    isLogin: false,
    userInfo: {},
    memberInfo: {}, // 🌟 存储完整的会员信息
    accessToken: '',
    refreshToken: '',
    goodsPointCache: {}
  },

  // 应用启动：恢复本地缓存
  onLaunch() {
    console.log('App 启动，恢复登录状态...');
    const cached = {
      isLogin: wx.getStorageSync('isLogin') || false,
      userInfo: wx.getStorageSync('userInfo') || {},
      memberInfo: wx.getStorageSync('memberInfo') || {}, // 🌟 确保从缓存读取
      accessToken: wx.getStorageSync('accessToken') || '',
      refreshToken: wx.getStorageSync('refreshToken') || ''
    };
    Object.assign(this.globalData, cached);
  },

  // 统一请求头
  getRequestHeader() {
    const token = this.globalData.accessToken || wx.getStorageSync('accessToken');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
  },

  // 全局请求方法（增加静默刷新 Token 逻辑）
  request(options) {
    const that = this;
    // 🌟 优化路径拼接：确保域名和路径之间只有一个斜杠
    const baseUrl = that.globalData.baseUrl;
    const path = options.url.startsWith('/') ? options.url : `/${options.url}`;
    const fullUrl = options.url.startsWith('http') ? options.url : `${baseUrl}${path}`;

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: options.method || 'GET',
        data: options.data || {},
        header: that.getRequestHeader(),
        success: async (res) => {
          // 401 Token 过期处理
          if (res.statusCode === 401) {
            console.warn('Token过期，尝试刷新...');
            try {
              // 🌟 尝试静默刷新 Token
              await that.doRefreshToken(); 
              // 刷新成功后，重新发起原始请求
              const retryRes = await that.request(options);
              resolve(retryRes);
            } catch (err) {
              // 刷新失败，才真正踢下线
              that.clearLoginState();
              wx.showModal({
                title: '登录过期',
                content: '请重新登录以继续使用',
                showCancel: false,
                success: () => wx.redirectTo({ url: '/pages/login/login' })
              });
              reject(new Error('登录已失效'));
            }
            return;
          }
          resolve(res);
        },
        fail: (err) => {
          console.error('网络请求失败：', err);
          reject(err);
        }
      });
    });
  },

  // 内部使用的刷新 Token 逻辑
  doRefreshToken() {
    const that = this;
    const refresh = that.globalData.refreshToken || wx.getStorageSync('refreshToken');
    if (!refresh) return Promise.reject('无刷新Token');

    return new Promise((resolve, reject) => {
      wx.request({
        url: `${that.globalData.baseUrl}/app01/token/refresh/`,
        method: 'POST',
        data: { refresh: refresh },
        success: (res) => {
          if (res.data && res.data.access) {
            const newAccess = res.data.access;
            that.globalData.accessToken = newAccess;
            wx.setStorageSync('accessToken', newAccess);
            resolve(newAccess);
          } else {
            reject();
          }
        },
        fail: reject
      });
    });
  },

  // 设置登录状态（登录成功时调用）
  // 🌟 增加对 memberInfo 的支持
  setLoginState(data) {
    const { userInfo, memberInfo, accessToken, refreshToken } = data;
    this.globalData.isLogin = true;
    this.globalData.userInfo = userInfo || {};
    this.globalData.memberInfo = memberInfo || {};
    this.globalData.accessToken = accessToken;
    this.globalData.refreshToken = refreshToken;

    wx.setStorageSync('isLogin', true);
    wx.setStorageSync('userInfo', this.globalData.userInfo);
    wx.setStorageSync('memberInfo', this.globalData.memberInfo);
    wx.setStorageSync('accessToken', accessToken);
    wx.setStorageSync('refreshToken', refreshToken);
  },

  // 清除状态
  clearLoginState() {
    wx.clearStorageSync(); // 简单粗暴，清除所有缓存
    this.globalData.isLogin = false;
    this.globalData.userInfo = {};
    this.globalData.memberInfo = {};
    this.globalData.accessToken = '';
    this.globalData.refreshToken = '';
  }
});
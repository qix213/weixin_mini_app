// app.js
App({
  globalData: {
    // 🌟 核心修改：必须以 https:// 开头，且结尾不要带斜杠
    baseUrl: 'https://www.lansik2026.com', 
    isLogin: false,
    userInfo: {},
    memberInfo: {}, // 存储完整的会员信息
    accessToken: '',
    refreshToken: '',
    goodsPointCache: {}
  },

  // 应用启动：恢复本地缓存
  onLaunch() {
    console.log('App 启动，正在同步 HTTPS 环境下的登录状态...');
    const cached = {
      isLogin: wx.getStorageSync('isLogin') || false,
      userInfo: wx.getStorageSync('userInfo') || {},
      memberInfo: wx.getStorageSync('memberInfo') || {}, 
      accessToken: wx.getStorageSync('accessToken') || '',
      refreshToken: wx.getStorageSync('refreshToken') || ''
    };
    Object.assign(this.globalData, cached);
  },

  // 统一获取请求头
  getRequestHeader() {
    const token = this.globalData.accessToken || wx.getStorageSync('accessToken');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
  },

  /**
   * 全局请求方法
   * 自动处理域名拼接、Token 过期静默刷新
   */
  request(options) {
    const that = this;
    const baseUrl = that.globalData.baseUrl;
    
    // 🌟 路径拼接优化逻辑：
    // 1. 如果传入的是完整路径(http开头)，直接用
    // 2. 如果是相对路径，处理斜杠确保拼接后只有一个斜杠，如：https://domain.com/app01/...
    let fullUrl = options.url;
    if (!options.url.startsWith('http')) {
      const cleanPath = options.url.startsWith('/') ? options.url : `/${options.url}`;
      fullUrl = `${baseUrl}${cleanPath}`;
    }

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: options.method || 'GET',
        data: options.data || {},
        header: that.getRequestHeader(),
        success: async (res) => {
          // 处理 401 Token 过期
          if (res.statusCode === 401) {
            console.warn('Token过期，尝试使用域名接口刷新...');
            try {
              await that.doRefreshToken(); 
              // 刷新成功，重试请求
              const retryRes = await that.request(options);
              resolve(retryRes);
            } catch (err) {
              that.clearLoginState();
              wx.showModal({
                title: '登录过期',
                content: '为了您的账户安全，请重新登录',
                showCancel: false,
                success: () => wx.reLaunch({ url: '/pages/login/login' })
              });
              reject(new Error('登录已失效'));
            }
            return;
          }
          resolve(res);
        },
        fail: (err) => {
          console.error('网络请求失败，请检查合法域名配置：', err);
          reject(err);
        }
      });
    });
  },

  // 刷新 Token 逻辑
  doRefreshToken() {
    const refresh = this.globalData.refreshToken || wx.getStorageSync('refreshToken');
    if (!refresh) return Promise.reject('无有效刷新凭证');

    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.globalData.baseUrl}/app01/token/refresh/`,
        method: 'POST',
        data: { refresh: refresh },
        success: (res) => {
          if (res.data && res.data.access) {
            const newAccess = res.data.access;
            this.globalData.accessToken = newAccess;
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

  // 设置登录状态
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

  // 清除登录状态
  clearLoginState() {
    wx.clearStorageSync(); 
    this.globalData.isLogin = false;
    this.globalData.userInfo = {};
    this.globalData.memberInfo = {};
    this.globalData.accessToken = '';
    this.globalData.refreshToken = '';
  }
});
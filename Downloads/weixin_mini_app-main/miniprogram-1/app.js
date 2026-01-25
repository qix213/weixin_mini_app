// app.js 正确写法（无语法错误，可正常创建 App 实例）
App({
  // 全局数据（格式正确，可自定义字段）
  globalData: {
    token: wx.getStorageSync('token') || '', // 从本地缓存读取 Token
    baseUrl: 'http://localhost:8000' ,// 示例接口地址
    // baseUrl: 'http://192.168.28.40:8000',
    isLogin: false,        // 登录状态
    userInfo: {},          // 简易用户信息
    memberInfo: {},        // 完整会员信息
    accessToken: '',       // 访问Token
    refreshToken: '',      // 刷新Token
  },
  // 全局Token请求头（复用，避免重复编写）
  getRequestHeader() {
    return {
      'Content-Type': 'application/json',
      // 正确格式：确保 Bearer 后有一个英文空格
      'Authorization': 'Bearer ' + (this.globalData.accessToken || '')
    };
  },
  // 全局生命周期：应用启动时执行

  // 全局生命周期：应用显示时执行
  onShow(options) {
    console.log('App onShow', options);
  },

  // 全局生命周期：应用隐藏时执行
  onHide() {
    console.log('App onHide');
  },

  // 全局生命周期：应用报错时执行
  onError(msg) {
    console.error('App error:', msg);
  },

  // 自定义全局方法（可选）
  getGlobalToken() {
    return this.globalData.token;
  },
  refreshToken() {
    const that = this;
    if (!that.globalData.refreshToken) return;
    wx.request({
      url: that.globalData.baseUrl + '/app01/token/refresh/',
      method: 'POST',
      data: {
        refresh: that.globalData.refreshToken
      },
      success: (res) => {
        if (res.data.access) {
          that.globalData.accessToken = res.data.access;
        }
      }
    });
  },
  onLaunch() {
    const userInfo = wx.getStorageSync('userInfo') || null;
    const accessToken = wx.getStorageSync('accessToken') || '';
    const refreshToken = wx.getStorageSync('refreshToken') || '';
    const isLogin = wx.getStorageSync('isLogin') || false;
    this.globalData = {
      baseUrl: 'http://localhost:8000', // 你的后端地址，不变
      userInfo: userInfo,
      accessToken: accessToken,
      refreshToken: refreshToken,
      isLogin: isLogin // 登录状态标记
    }
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token; // 检查括号、分号是否缺失
    } // 检查是否少闭合大括号
  },

  request(options) {
    const that = this;
    const token = that.globalData.token;
    const baseUrl = that.globalData.baseUrl;
    // 拼接完整URL
    const fullUrl = `${baseUrl}${options.url}`;
    console.log('👉 请求地址：', fullUrl);

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: options.method || 'GET',
        data: options.data || {},
        header: {
          'content-type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        // 成功时必须调用 resolve(res)
        success: function (res) {
          console.log('👉 请求成功返回：', res.data);
          // 401登录过期处理
          if (res.statusCode === 401) {
            wx.removeStorageSync('token');
            that.globalData.token = '';
            wx.showModal({
              title: '提示',
              content: '登录已过期，请重新登录',
              showCancel: false,
              success: () => {
                wx.navigateTo({ url: '/pages/login/login' });
              }
            });
            reject(res);
            return;
          }
          resolve(res); // 核心：必须resolve，否则页面的success不执行
        },
        // 失败时必须调用 reject(err)
        fail: function (err) {
          console.error('👉 请求失败：', err);
          reject(err); // 核心：必须reject，否则页面的fail不执行
        },
        complete: function () {
          console.log('👉 请求完成');
        }
      })
    })
  },
});
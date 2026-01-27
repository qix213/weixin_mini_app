// app.js 最终修正版（解决Token混乱+认证失败问题）
App({
  // ===================== 1. 全局数据（统一规范，仅保留必要字段） =====================
  globalData: {
    baseUrl: 'http://localhost:8000', // 统一后端基础地址（只定义一次）
    isLogin: false,                   // 登录状态标记
    userInfo: {},                     // 用户基础信息
    memberInfo: {},                   // 会员详细信息
    accessToken: '',                  // 核心：JWT访问Token（统一用这个字段）
    refreshToken: ''                  // 刷新Token（用于Token过期时刷新）
  },

  // ===================== 2. 全局生命周期 - 应用启动（优先执行） =====================
  onLaunch() {
    console.log('App 启动，恢复登录状态...');
    // 从本地缓存批量恢复登录状态（避免重复赋值globalData）
    const cached = {
      isLogin: wx.getStorageSync('isLogin') || false,
      userInfo: wx.getStorageSync('userInfo') || {},
      memberInfo: wx.getStorageSync('memberInfo') || {},
      accessToken: wx.getStorageSync('accessToken') || '',
      refreshToken: wx.getStorageSync('refreshToken') || ''
    };

    // 合并到全局数据（不覆盖原有结构，仅更新缓存数据）
    Object.assign(this.globalData, cached);

    // 日志：验证恢复的Token（方便调试）
    console.log('恢复的登录状态：', {
      isLogin: this.globalData.isLogin,
      accessToken: this.globalData.accessToken ? '已存在' : '为空',
      refreshToken: this.globalData.refreshToken ? '已存在' : '为空'
    });
  },

  // ===================== 3. 全局生命周期 - 应用显示 =====================
  onShow(options) {
    console.log('App 显示', options);
    // 可选：每次显示时检查Token是否过期（进阶优化）
    // this.checkTokenExpire();
  },

  // ===================== 4. 全局生命周期 - 应用隐藏 =====================
  onHide() {
    console.log('App 隐藏');
  },

  // ===================== 5. 全局生命周期 - 应用报错 =====================
  onError(msg) {
    console.error('App 运行错误:', msg);
  },

  // ===================== 6. 核心：统一请求头（所有请求复用，Token来源唯一） =====================
  getRequestHeader() {
    const { accessToken } = this.globalData;
    return {
      'Content-Type': 'application/json',
      // 关键修复：只使用accessToken，且确保Bearer后有英文空格
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
    };
  },

  // ===================== 7. 核心：全局请求方法（统一Token+错误处理） =====================
  request(options) {
    const that = this;
    const baseUrl = that.globalData.baseUrl;
    // 拼接完整URL（兼容绝对路径/相对路径）
    const fullUrl = options.url.startsWith('http') ? options.url : `${baseUrl}${options.url}`;

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: options.method || 'GET',
        data: options.data || {},
        // 关键修复：使用统一的请求头（Token来源唯一）
        header: that.getRequestHeader(),
        // 请求成功处理
        success: function (res) {
          
          // 401 Token过期处理（核心逻辑）
          if (res.statusCode === 401 || (res.data && res.data.code === 401)) {
            console.warn('Token过期，清除登录状态');
            // 清除本地缓存+全局状态
            that.clearLoginState();
            // 提示并跳转登录页
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
          
          // 正常响应：返回完整响应对象（兼容前端所有场景）
          resolve(res);
        },
        // 请求失败处理
        fail: function (err) {
          console.error('👉 请求失败：', err);
          wx.showToast({ title: '网络请求失败', icon: 'none' });
          reject(err);
        },
        // 请求完成（无论成功/失败）
        complete: function () {
        }
      });
    });
  },

  // ===================== 8. 辅助：刷新Token（Token过期时调用） =====================
  refreshToken() {
    const that = this;
    const { refreshToken } = that.globalData;
    
    // 无刷新Token则直接返回
    if (!refreshToken) {
      console.warn('无刷新Token，无法刷新');
      return Promise.reject('无刷新Token');
    }

    return new Promise((resolve, reject) => {
      wx.request({
        url: `${that.globalData.baseUrl}/app01/token/refresh/`,
        method: 'POST',
        data: { refresh: refreshToken },
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          if (res.data && res.data.access) {
            // 刷新成功：更新Token并缓存
            that.globalData.accessToken = res.data.access;
            wx.setStorageSync('accessToken', res.data.access);
            resolve(res.data.access);
          } else {
            // 刷新失败：清除登录状态
            that.clearLoginState();
            reject(new Error('刷新Token失败'));
          }
        },
        fail: (err) => {
          console.error('刷新Token请求失败：', err);
          reject(err);
        }
      });
    });
  },

  // ===================== 9. 辅助：清除登录状态（退出/过期时调用） =====================
  clearLoginState() {
    // 清除本地缓存
    wx.removeStorageSync('isLogin');
    wx.removeStorageSync('userInfo');
    wx.removeStorageSync('memberInfo');
    wx.removeStorageSync('accessToken');
    wx.removeStorageSync('refreshToken');
    
    // 重置全局状态
    this.globalData = {
      ...this.globalData, // 保留baseUrl不变
      isLogin: false,
      userInfo: {},
      memberInfo: {},
      accessToken: '',
      refreshToken: ''
    };
  },

  // ===================== 10. 辅助：设置登录状态（登录成功时调用） =====================
  setLoginState(userInfo, accessToken, refreshToken) {
    // 更新全局状态
    this.globalData.isLogin = true;
    this.globalData.userInfo = userInfo;
    this.globalData.accessToken = accessToken;
    this.globalData.refreshToken = refreshToken;
    
    // 持久化到本地缓存
    wx.setStorageSync('isLogin', true);
    wx.setStorageSync('userInfo', userInfo);
    wx.setStorageSync('accessToken', accessToken);
    wx.setStorageSync('refreshToken', refreshToken);
    
  }
});
// pages/login/login.js
Page({
  data: {
    nickname: '',        // 昵称（登录账号）
    password: '',        // 登录密码
    verifyCode: '',      // 验证码（模拟验证，可根据后端需求保留/删除）
    countDown: 0,        // 验证码倒计时
    timer: null          // 倒计时定时器
  },

  onUnload() {
    // 页面卸载清除定时器，避免内存泄漏
    if (this.data.timer) {
      clearInterval(this.data.timer);
      this.setData({ timer: null });
    }
  },

  // 处理昵称输入
  handleNicknameInput(e) {
    this.setData({
      nickname: e.detail.value.trim()
    });
  },

  // 处理密码输入
  handlePasswordInput(e) {
    this.setData({
      password: e.detail.value.trim()
    });
  },

  // 处理验证码输入（模拟功能，后端若不需要可删除）
  handleCodeInput(e) {
    this.setData({
      verifyCode: e.detail.value.trim()
    });
  },

  // 验证码倒计时（模拟功能，后端若不需要可删除）
  handleGetVerifyCode() {
    const { nickname } = this.data;
    if (!nickname) {
      wx.showToast({ title: '请先输入昵称', icon: 'none' });
      return;
    }

    let count = 60;
    this.setData({ countDown: count });
    this.data.timer = setInterval(() => {
      count--;
      this.setData({ countDown: count });
      if (count <= 0) {
        clearInterval(this.data.timer);
        this.setData({ countDown: 0, timer: null });
      }
    }, 1000);

    wx.showToast({ title: '验证码发送成功（123456）', icon: 'success' });
  },

  // 核心：登录请求（适配 /app01/token/ 地址）
  handleLogin() {
    const { nickname, password, verifyCode } = this.data;
    const app = getApp();

    // 1. 前端基础验证
    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' });
      return;
    }
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' });
      return;
    }
    // 密码格式验证（与注册页一致）
    const pwdReg = /^(?=.*[0-9])(?=.*[a-zA-Z])(?!.*\s).{8,}$/;
    if (!pwdReg.test(password)) {
      wx.showToast({ title: '密码需8位以上数字+字母组合', icon: 'none' });
      return;
    }
    // 模拟验证码验证（后端若不需要，可删除该判断）
    if (verifyCode !== '123456') {
      wx.showToast({ title: '验证码错误（正确：123456）', icon: 'none' });
      return;
    }

    // 2. 发送登录请求（核心：地址改为 /app01/token/）
    wx.showLoading({ title: '登录中...', mask: true });
    wx.request({
      url: app.globalData.baseUrl + '/app01/token/', // 适配后端 /app01/token/ 地址
      method: 'POST',
      header: {
        'Content-Type': 'application/json' // 明确请求格式，避免后端解析异常
      },
      data: {
        username: nickname, // 传递昵称（后端需适配该参数）
        password: password
      },
      success: (res) => {
        wx.hideLoading();
        // 3. 处理后端返回结果（兼容 SimpleJWT 默认格式 + 自定义格式）
// login.js 中 handleLogin 的 success 回调（仅修改这部分）
if (res.data.access && res.data.refresh) {
  // SimpleJWT 默认返回：access（访问Token）、refresh（刷新Token）
  const accessToken = res.data.access;
  const refreshToken = res.data.refresh;
  
  // 修复：存储到storage的正确字段（和app.js onLaunch对应）
  wx.setStorageSync('accessToken', accessToken); // 关键！之前存的是token，现在改accessToken
  wx.setStorageSync('refreshToken', refreshToken);
  wx.setStorageSync('isLogin', true); // 存储登录状态
  wx.setStorageSync('userInfo', res.data.user_info || { nickname }); // 存储用户信息

  // 更新全局变量（统一用accessToken，废弃token字段）
  app.globalData.isLogin = true;
  app.globalData.accessToken = accessToken; // 核心：全局请求头依赖这个字段
  app.globalData.refreshToken = refreshToken;
  app.globalData.userInfo = res.data.user_info || {
    nickname: nickname,
    star_level: res.data.star_level || 0,
    points: res.data.points || 0,
    coupon_count: res.data.coupon_count || 0
  };
  app.globalData.token = accessToken; // 兼容旧代码，可后续删除

  // 登录成功提示 + 跳转主页
  wx.showToast({ title: '登录成功', icon: 'success', duration: 1500 });
  setTimeout(() => {
    wx.switchTab({ url: '/pages/index/index' });
  }, 1500);
        } else {
          // 登录失败提示
          wx.showToast({ title: res.data.msg || '昵称或密码错误', icon: 'none', duration: 2000 });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        console.error('登录请求失败：', err);
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // 跳转注册页
  goToRegister() {
    wx.navigateTo({
      url: '/pages/register/register',
    });
  }
});
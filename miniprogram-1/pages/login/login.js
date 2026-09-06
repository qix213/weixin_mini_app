// pages/login/login.js
const app = getApp();

Page({
  data: {
    // 登录方式
    loginType: "wechat",
  
    // 用户名密码登录
    username: "",
    password: "",
    statusBarHeight: 20
    
  },

  onLoad() {
    // 🌟 获取系统状态栏高度，防止我们的自定义按钮被刘海遮挡
    const sysInfo = wx.getSystemInfoSync();
    this.setData({
      statusBarHeight: sysInfo.statusBarHeight
    });

    // 现有的清理旧登录态逻辑
    app.clearLoginState && app.clearLoginState();
  },

  // 🌟 新增：强制回主页的方法
  goHome() {
    wx.switchTab({
      url: '/pages/index/index'
    });
  },

// 切换登录方式
changeTab(e) {
  this.setData({
    loginType: e.currentTarget.dataset.type
  });
},

// 用户名输入
onUsernameInput(e) {
  this.setData({
    username: e.detail.value
  });
},

// 密码输入
onPasswordInput(e) {
  this.setData({
    password: e.detail.value
  });
},

// 用户名密码登录
handleAccountLogin() {

  const { username, password } = this.data;

  if (!username) {
    wx.showToast({
      title: '请输入用户名',
      icon: 'none'
    });
    return;
  }

  if (!password) {
    wx.showToast({
      title: '请输入密码',
      icon: 'none'
    });
    return;
  }

  wx.showLoading({
    title: '登录中...',
    mask: true
  });

  wx.request({
    url: app.globalData.baseUrl + '/app01/login/',
    method: 'POST',
    header: {
      'Content-Type': 'application/json'
    },
    data: {
      username,
      password
    },

    success: (res) => {

      console.log("status:", res.statusCode);
      console.log("data:", res.data);
    
      wx.hideLoading();
    
      const resData = res.data;
    
      // ✅ 统一判断后端结构
      if (res.statusCode === 200 && resData.code === 200 && resData.data?.access) {
    
        const { access, refresh, user_info } = resData.data;
    
        // 存储 token
        wx.setStorageSync('accessToken', access);
        wx.setStorageSync('refreshToken', refresh);
        wx.setStorageSync('isLogin', true);
        wx.setStorageSync('memberInfo', user_info || {});
    
        // 全局变量
        app.globalData.isLogin = true;
        app.globalData.accessToken = access;
        app.globalData.refreshToken = refresh;
        app.globalData.memberInfo = user_info || {};
    
        wx.showToast({
          title: resData.msg || '登录成功',
          icon: 'success'
        });
    
        setTimeout(() => {
          wx.switchTab({
            url: '/pages/index/index'
          });
        }, 1200);
    
      } else {
    
        wx.showToast({
          title: resData.msg || '账号或密码错误',
          icon: 'none'
        });
    
      }
    },
    fail: (err) => {
      wx.hideLoading();
      console.error(err);
      wx.showToast({
          title: '网络异常',
          icon: 'none'
      });
  }
  });
  },
  handleCancelLogin() {
    // 提示用户并返回主页
    wx.showToast({
      title: '已取消登录',
      icon: 'none'
    });
    
    setTimeout(() => {
      // 注意：由于 index 通常是底部的 tab 页面，必须用 switchTab
      // 如果你的 index 不是 tab 页面，请换成 wx.reLaunch 或 wx.navigateBack
      wx.switchTab({
        url: '/pages/index/index'
      });
    }, 800);
  },
// ================= 🌟 优化：一键手机号授权登录 =================
handleWechatLogin(e) {
  // 1. 检查用户是否同意了授权 (这里处理用户在原生弹窗点击“拒绝/取消”的情况)
  if (e.detail.errMsg !== "getPhoneNumber:ok") {
    wx.showToast({ 
      title: '已取消手机号授权', 
      icon: 'none' 
    });
    
    // 取消授权后，自动退回到主页
    setTimeout(() => {
      wx.switchTab({
        url: '/pages/index/index'
      });
    }, 1000);
    
    return;
  }

  // 2. 拿到解密手机号的专属 code
  const phoneCode = e.detail.code;

  wx.showLoading({ title: '安全登录中...', mask: true });

  // 3. 调用 wx.login 拿到换取 openid 的 code
  wx.login({
    success: (res) => {
      if (res.code) {
        const loginCode = res.code;

        // 4. 发送双 code 给后端验证
        wx.request({
          url: app.globalData.baseUrl + '/app01/wechat-login/', 
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          data: {
            login_code: loginCode,
            phone_code: phoneCode
          },
          success: (backendRes) => {
            wx.hideLoading();
            const resData = backendRes.data;

            if (resData.code === 200 && resData.data?.access) {
              const { access, refresh, user_info } = resData.data;

              wx.setStorageSync('accessToken', access);
              wx.setStorageSync('refreshToken', refresh);
              wx.setStorageSync('isLogin', true);
              wx.setStorageSync('memberInfo', user_info || {});

              app.globalData.isLogin = true;
              app.globalData.accessToken = access;
              app.globalData.refreshToken = refresh;
              app.globalData.memberInfo = user_info || {};

              wx.showToast({ title: '登录成功', icon: 'success', duration: 1500 });
              setTimeout(() => {
                wx.switchTab({ url: '/pages/index/index' });
              }, 1500);

            } else if (resData.code === 404 || resData.code === 4004) {
              wx.showToast({ title: '未查询到您的注册信息，请先注册', icon: 'none', duration: 2000 });
              setTimeout(() => {
                wx.navigateTo({ url: '/pages/register/register' });
              }, 1500);
            } else {
              wx.showToast({ title: resData.msg || '登录异常', icon: 'none' });
            }
          },
          fail: (err) => {
            wx.hideLoading();
            console.error('登录接口请求失败', err);
            wx.showToast({ title: '网络连接失败', icon: 'none' });
          }
        });
      } else {
        wx.hideLoading();
        wx.showToast({ title: '微信环境调用失败', icon: 'none' });
      }
    },
    fail: () => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常，请重试', icon: 'none' });
    }
  });
},
  // 备用：给界面上可能存在的“去注册”文字按钮绑定事件
  goToRegister() {
    wx.navigateTo({
      url: '/pages/register/register',
    });
  }
});
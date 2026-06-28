// pages/login/login.js
const app = getApp();

Page({
  data: {
    // 之前所有的手动输入变量都被清理掉了，体验极致轻量
  },

  onLoad() {
    // 进入登录页时，为了安全，可以先清理一下旧的登录态
    app.clearLoginState && app.clearLoginState();
  },

  // ================= 🌟 核心：一键手机号授权登录 =================
  handleWechatLogin(e) {
    // 1. 检查用户是否同意了授权
    if (e.detail.errMsg !== "getPhoneNumber:ok") {
      wx.showToast({ title: '需授权手机号才能快捷登录', icon: 'none' });
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
            // 假设你的后端登录接口是 /app01/wechat-login/，请确认这个路径与你 urls.py 匹配
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

              // 🌟 场景一：后端验证通过，此手机号已注册，正常登录
              if (resData.code === 200 && resData.data?.access) {
                const { access, refresh, user_info } = resData.data;

                // 存入本地缓存
                wx.setStorageSync('accessToken', access);
                wx.setStorageSync('refreshToken', refresh);
                wx.setStorageSync('isLogin', true);
                wx.setStorageSync('memberInfo', user_info || {});

                // 同步全局变量
                app.globalData.isLogin = true;
                app.globalData.accessToken = access;
                app.globalData.refreshToken = refresh;
                app.globalData.memberInfo = user_info || {};

                wx.showToast({ title: '登录成功', icon: 'success', duration: 1500 });
                setTimeout(() => {
                  wx.switchTab({ url: '/pages/index/index' });
                }, 1500);

              } 
              // 🌟 场景二：后端查无此人，跳转注册！
              // (注意：这里假设后端返回 404 或自定义 4004 代表未注册)
              else if (resData.code === 404 || resData.code === 4004) {
                wx.showToast({ title: '未查询到您的注册信息，请先注册', icon: 'none', duration: 2000 });
                setTimeout(() => {
                  wx.navigateTo({ url: '/pages/register/register' });
                }, 1500);
              } 
              // 其他错误
              else {
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
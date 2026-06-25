Page({
  data: {
    second: 4,
    bgUrl: '' // 🌟 修复1：显式初始化变量，防止 WXML 报未定义警告，利于页面丝滑渲染
  },
  
  timer: null,      // 保存定时器实例
  isJumping: false, // 跳转锁

  onLoad(options) {
    this.startTimer();
    this.getWelcomeBg();
  },

  // 获取欢迎页背景图
  getWelcomeBg() {
    const that = this;
    
    // 🌟 修复2：在函数内部动态安全获取 app 实例，彻底避免全局 ReferenceError
    const appInstance = getApp();
    if (!appInstance || !appInstance.globalData) {
      console.warn('App 实例尚未完全初始化，启用本地兜底图');
      that.setData({ bgUrl: '/images/bg/bg.png' });
      return;
    }

    wx.request({
      url: `${appInstance.globalData.baseUrl}/app01/welcome/`, 
      method: 'GET',
      success: (res) => {
        if (res.data.code === 100 && res.data.result) {
          that.setData({
            bgUrl: res.data.result 
          });
          // 缓存图片绝对路径
          wx.setStorageSync('index_bg_url', res.data.result);
        } else {
          that.setData({ bgUrl: '/images/bg/bg.png' });
        }
      },
      fail: () => {
        // 失败兜底
        that.setData({ bgUrl: '/images/bg/bg.png' });
      }
    });
  },

  // 开启倒计时
  startTimer() {
    // 安全防范：开启前先清理已有定时器，防止死锁或重复叠加
    this.clearWelcomeTimer();

    this.timer = setInterval(() => {
      if (this.data.second <= 1) {
        this.doJump(); // 时间到，自动跳转
      } else {
        this.setData({
          second: this.data.second - 1
        });
      }
    }, 1000);
  },

  // 执行跳转
  doJump() {
    // 1. 防止重复点击锁
    if (this.isJumping) return;
    this.isJumping = true;

    // 2. 彻底销毁定时器
    this.clearWelcomeTimer();
    
    // 3. 执行跳转
    wx.switchTab({
      url: '/pages/index/index',
      success: () => {
        console.log('跳转首页成功');
      },
      fail: (err) => {
        // ⚠️ 如果跳不过去，这里会在控制台清晰打印报错原因
        // 常见错误：app.json 的 tabBar 数组里没有配置过 "/pages/index/index"
        console.error('跳转首页失败，请确认该路径是否在 app.json 的 tabBar 中：', err);
        this.isJumping = false; // 失败了解锁，允许用户再次点击尝试
      }
    });
  },

  // 封装统一的定时器清理方法
  clearWelcomeTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  // 🌟 修复3：switchTab 触发的是 onHide 而不是 onUnload，必须在这里防范性清理定时器
  onHide() {
    this.clearWelcomeTimer();
  },

  // 页面真正被销毁时清理
  onUnload() {
    this.clearWelcomeTimer();
  }
});
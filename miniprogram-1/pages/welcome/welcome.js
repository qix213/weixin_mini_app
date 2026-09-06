Page({
  data: {
    second: 5,
    // 🌟 1. 初始值只读缓存，如果没有缓存就为空字符串，绝不用本地假路径
    bgUrl: wx.getStorageSync('index_bg_url') || '', 
    isImageLoaded: false 
  },
  
  timer: null,
  isJumping: false,

  onLoad(options) {
    this.startTimer();
    this.getWelcomeBg(); 
  },

  onImageLoad() {
    this.setData({ isImageLoaded: true });
  },

  onImageError(err) {
    console.error("网络图片加载失败或地址失效", err);
    // 🌟 2. 失败了直接清空，露出底层的 CSS 高级渐变色即可
    this.setData({ bgUrl: '' });
  },

  getWelcomeBg() {
    const appInstance = getApp();
    if (!appInstance || !appInstance.globalData) return;

    wx.request({
      url: `${appInstance.globalData.baseUrl}/app01/welcome/`, 
      method: 'GET',
      success: (res) => {
        if (res.data.code === 100 && res.data.result) {
          const newUrl = res.data.result;
          const oldUrl = this.data.bgUrl;
          
          // 🌟 3. 核心逻辑：如果当前屏幕上没图(第一次打开小程序)，拿到新图立刻显示！
          if (!oldUrl) {
            this.setData({ bgUrl: newUrl });
          }

          // 无论如何，都把最新获取的 URL 存入缓存，下次秒开
          if (newUrl !== wx.getStorageSync('index_bg_url')) {
            wx.setStorageSync('index_bg_url', newUrl);
          }
        }
      }
    });
  },
  // --- 下方的倒计时与跳转逻辑保持不变 ---
  startTimer() {
    this.clearWelcomeTimer();
    this.timer = setInterval(() => {
      if (this.data.second <= 1) {
        this.doJump();
      } else {
        this.setData({ second: this.data.second - 1 });
      }
    }, 1000);
  },

  doJump() {
    if (this.isJumping) return;
    this.isJumping = true;
    this.clearWelcomeTimer();
    
    wx.switchTab({
      url: '/pages/index/index',
      fail: (err) => {
        console.error('跳转首页失败：', err);
        this.isJumping = false;
      }
    });
  },

  clearWelcomeTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  onHide() { this.clearWelcomeTimer(); },
  onUnload() { this.clearWelcomeTimer(); }
});
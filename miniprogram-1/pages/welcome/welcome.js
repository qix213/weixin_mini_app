const app = getApp(); // 必须在 Page 之前，并且确保这行代码在执行时被加载
Page({
  data: {
    second: 4
  },
  
  timer: null, // 定义一个变量来保存定时器

  onLoad(options) {
    this.startTimer();
    this.getWelcomeBg();
  },
  getWelcomeBg() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/welcome/`, // 确保这里的 URL 与 urls.py 匹配
      method: 'GET',
      success: (res) => {
        // 对应后端返回的结构：res.data.result
        if (res.data.code === 100 && res.data.result) {
          that.setData({
            bgUrl: res.data.result // 直接使用后端拼接好的完整绝对路径
          });
          // 顺便缓存一下，提升下次启动速度
          wx.setStorageSync('index_bg_url', res.data.result);
        }
      },
      fail: () => {
        // 加载失败时使用本地兜底图片，防止空白
        that.setData({ bgUrl: '/images/bg/bg.png' });
      }
    });
  },
  // 开启倒计时
  startTimer() {
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

  // 执行跳转（手动点击和倒计时结束都会调用这里）
// 执行跳转
doJump() {
  // 1. 防止重复点击
  if (this.isJumping) return;
  this.isJumping = true;

  // 2. 销毁定时器
  if (this.timer) {
    clearInterval(this.timer);
    this.timer = null;
  }
  
  // 3. 执行跳转，并捕获可能的报错
  wx.switchTab({
    url: '/pages/index/index',
    success: () => {
      console.log('跳转首页成功');
    },
    fail: (err) => {
      // ⚠️ 如果跳不过去，这里会在控制台打印红字报错
      // 常见错误：app.json 的 tabBar 里没有配置 /pages/index/index
      console.error('跳转失败：', err);
      this.isJumping = false; // 失败了解锁
    }
  });
},

  // 页面卸载时防范性清理
  onUnload() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }
});
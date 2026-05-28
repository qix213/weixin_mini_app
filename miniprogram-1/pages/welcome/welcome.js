Page({
  data: {
    second: 4
  },
  
  timer: null, // 定义一个变量来保存定时器

  onLoad(options) {
    this.startTimer();
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
  doJump() {
    // ⚠️ 跳转前，必须销毁定时器，防止后台继续计时导致二次跳转！
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    
    wx.switchTab({
      url: '/pages/index/index',
    });
  },

  // 页面卸载时防范性清理
  onUnload() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }
});
Page({
  data: {
    privilegeImg: '',
    isImageLoaded: false // 🌟 新增：图片加载完成标识
  },
  onLoad() {
    this.getPrivilegeImg();
  },
  getPrivilegeImg() {
    wx.request({
      url: `${getApp().globalData.baseUrl}/app01/offline_certificate/`,
      method: 'GET',
      success: (res) => {
        if (res.data.code === 200 && res.data.result) {
          this.setData({ privilegeImg: res.data.result });
        }
      }
    });
  },
  // 🌟 新增：图片真正下载并渲染完成时触发
  onImageLoad() {
    this.setData({ isImageLoaded: true });
  },
  // 🌟 新增：防白屏安全网，万一图片损坏不至于一直闪烁
  onImageError() {
    console.error("长图加载失败");
    this.setData({ isImageLoaded: true });
  }
})
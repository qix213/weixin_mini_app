Page({
  data: {
    privilegeImg: ''
  },
  onLoad() {
    this.getPrivilegeImg();
  },
  getPrivilegeImg() {
    wx.request({
      url: `${getApp().globalData.baseUrl}/app01/member_privilege/`,
      method: 'GET',
      success: (res) => {
        if (res.data.code === 200 && res.data.result) {
          this.setData({ privilegeImg: res.data.result });
        }
      }
    });
  }
})
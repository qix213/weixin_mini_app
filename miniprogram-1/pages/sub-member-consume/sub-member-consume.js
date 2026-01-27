// pages/sub-member-consume/sub-member-consume.js
Page({
  data: {
    loading: true,
    consumeList: [], // 推荐会员消费记录列表
    currentLevel: 0 // 当前会员等级
  },

  onLoad(options) {
    // 获取从我的页面传递的当前会员等级
    this.setData({
      currentLevel: options.currentLevel || 0
    });
    // 请求消费记录
    this.getSubMemberConsumeList();
  },

  // 核心：请求推荐会员消费记录接口
  getSubMemberConsumeList() {
    const app = getApp();
    const header = app.getRequestHeader();

    wx.request({
      url: app.globalData.baseUrl + '/app01/member/sub-consume/',
      method: 'GET',
      header: header,
      data: {
        current_level: this.data.currentLevel // 传递当前等级，后端筛选可查看的下级
      },
      success: (res) => {
        this.setData({ loading: false });
        if (res.data.code === 200) {
          // 格式化时间（后端返回的时间可能是字符串，需格式化）
          const consumeList = res.data.data.map(item => {
            return {
              ...item,
              // 格式化创建时间（示例：2026-01-27 15:30:45）
              create_time: item.create_time ? this.formatDate(item.create_time) : ''
            };
          });
          this.setData({ consumeList });
        } else {
          wx.showToast({ title: res.data.msg || '获取消费记录失败', icon: 'none' });
        }
      },
      fail: (err) => {
        this.setData({ loading: false });
        console.error('消费记录请求失败：', err);
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // 辅助：格式化时间
  formatDate(dateStr) {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hour = date.getHours().toString().padStart(2, '0');
    const minute = date.getMinutes().toString().padStart(2, '0');
    const second = date.getSeconds().toString().padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
  }
});
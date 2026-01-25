// pages/order-list/order-list.js
const app = getApp();

Page({
  data: {
    orderList: []
  },

  onShow() {
    console.log("1. 页面 onShow 触发");
    this.fetchOrders();
  },

  fetchOrders() {
    // A. 这里的日志如果没印出来，说明 fetchOrders 没被调用
    console.log("2. 进入 fetchOrders 函数"); 

    const token = wx.getStorageSync('token');
    if (!token) {
      console.log("3. 诊断：因为没有 Token，流程被拦截了");
      wx.hideLoading();
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    console.log("4. 准备调用 app.request，URL: /app01/order/list/");
    wx.showLoading({ title: '加载中...' });

    app.request({
      url: '/app01/order/list/',
      method: 'GET'
    }).then(res => {
      console.log("5. 后端响应成功:", res.data);
      this.setData({
        orderList: res.data.data || []
      });
    }).catch(err => {
      console.error("6. 请求发生了错误:", err);
    }).finally(() => {
      console.log("7. 流程结束，关闭 Loading");
      wx.hideLoading();
    });
  }
});
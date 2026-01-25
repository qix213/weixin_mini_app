const app = getApp();
Page({
  data: {
    typeName: '',    // 所选类型名称
    amount: 0,       // 应付金额
    phone: '',       // 用户手机号
    payLoading: false, // 支付加载状态
    // ====== 新增：支付方式相关 ======
    payMethods: [
      { id: 1, name: '微信支付', icon: 'https://mmbiz.qpic.cn/mmbiz_png/9t5m99X9riaT7OiaiaibC9iaGd8XrHiaPicUe2OiaOQ5wTjiaYg6cJ25sUic4s6j9XtQiaiciaaCw/0?wx_fmt=png', selected: true },
      { id: 2, name: '支付宝支付', icon: 'https://mmbiz.qpic.cn/mmbiz_png/9t5m99X9riaT7OiaiaibC9iaGd8XrHiaPicUe2OiaOQ5wTjiaYg6cJ25sUic4s6j9XtQiaiciaaCw/0?wx_fmt=png', selected: false }
    ],
    selectedPayMethod: 1 // 默认选中微信支付（id=1）
  },

  onLoad(options) {
    // 接收注册页传递的参数（解码中文）
    this.setData({
      typeName: decodeURIComponent(options.typeName),
      amount: Number(options.amount),
      phone: options.phone
    });
  },

  // ====== 新增：切换支付方式 ======
  switchPayMethod(e) {
    const payMethodId = e.currentTarget.dataset.methodid;
    // 更新选中状态
    const payMethods = this.data.payMethods.map(method => {
      method.selected = method.id === payMethodId;
      return method;
    });
    this.setData({
      payMethods,
      selectedPayMethod: payMethodId
    });
  },

  // 模拟支付操作（适配选中的支付方式）
  handlePay() {
    if (this.data.payLoading) return; // 防止重复点击

    this.setData({ payLoading: true });
    // 获取选中的支付方式名称
    const selectedMethod = this.data.payMethods.find(method => method.id === this.data.selectedPayMethod).name;

    // 模拟支付接口请求（延迟2秒）
    setTimeout(() => {
      this.setData({ payLoading: false });
      // 动态提示支付方式
      wx.showToast({
        title: `${selectedMethod}${this.data.amount}元成功`,
        icon: 'success',
        duration: 2000
      });
      // 延迟跳转首页
      setTimeout(() => {
        wx.switchTab({
          url: '/pages/index/index'
        });
      }, 2000);
    }, 2000);
  },

  // 取消支付（返回注册页）
  handleCancel() {
    wx.navigateBack({
      delta: 1 // 返回上一级页面
    });
  }
});
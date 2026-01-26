const app = getApp();
Page({
  data: {
    typeName: '',        // 支付类型名称（会员缴费/商品订单）
    amount: 0,           // 支付金额
    scene: 'order',      // 场景标识：member=会员缴费，order=商品订单
    payMethods: [        // 支付方式列表
      { 
        id: 1, 
        name: '微信支付', 
        icon: 'https://mmbiz.qpic.cn/mmbiz_png/ajNVdqHZLLBuyXif9WGH0TsCqZLsNO1G1QN85V1U8ICH9nq4iciaibQDR8iaZs8YF0gE8Cn4u4Y1Q2iaYiciaY9d9iaicw/640?wx_fmt=png', 
        selected: true 
      },
      { 
        id: 2, 
        name: '支付宝支付', 
        icon: 'https://mmbiz.qpic.cn/mmbiz_png/ajNVdqHZLLAib60Jcz9oxrGibHibqV46STP8OSuibPqQ64D508nqVq1Q4y6q0cQic9nZg/640?wx_fmt=png', 
        selected: false 
      }
    ],
    selectedPayMethod: 1, // 默认选中微信支付
    payLoading: false     // 支付加载状态
  },

  // 页面加载：解析场景和参数
  onLoad(options) {
    // 1. 获取场景标识（默认商品订单）
    const scene = options.scene || 'order';
    // 2. 解析参数（兼容会员/商品场景）
    const typeName = decodeURIComponent(options.typeName || (scene === 'member' ? '会员缴费' : '商品订单支付'));
    const amount = Number(options.amount || options.totalAll || 0);

    this.setData({
      scene,
      typeName,
      amount
    });
    console.log('支付页参数：', this.data);
  },

  // 切换支付方式
  switchPayMethod(e) {
    const payMethodId = e.currentTarget.dataset.methodid;
    const payMethods = this.data.payMethods.map(method => {
      method.selected = method.id === payMethodId;
      return method;
    });
    this.setData({
      payMethods,
      selectedPayMethod: payMethodId
    });
  },

  // 核心：模拟支付
  handlePay() {
    if (this.data.payLoading || this.data.amount <= 0) return;

    this.setData({ payLoading: true });
    // 获取选中的支付方式名称
    const selectedMethod = this.data.payMethods.find(m => m.id === this.data.selectedPayMethod).name;

    // 模拟支付接口请求（2秒延迟）
    setTimeout(() => {
      this.setData({ payLoading: false });
      // 支付成功提示
      wx.showToast({
        title: `${selectedMethod}¥${this.data.amount}元支付成功`,
        icon: 'success',
        duration: 2000
      });

      // 根据场景跳转不同页面
      setTimeout(() => {
        if (this.data.scene === 'member') {
          // 会员缴费成功跳首页
          wx.switchTab({ url: '/pages/index/index' });
        } else {
          // 商品订单支付成功跳商城
          wx.switchTab({ url: '/pages/mall/mall' });
        }
      }, 2000);
    }, 2000);
  },

  // 取消支付：返回上一级页面
  handleCancel() {
    wx.navigateBack({ delta: 1 });
  }
});
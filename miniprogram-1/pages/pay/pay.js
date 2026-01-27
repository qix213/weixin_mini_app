const app = getApp();
Page({
  data: {
    typeName: '',        // 支付类型名称（会员缴费/商品订单）
    amount: 0,           // 支付金额
    scene: 'order',      // 场景标识：member=会员缴费，order=商品订单
    orderId: '',         // 新增：接收订单ID（关键）
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

  // 页面加载：解析场景和参数（新增接收orderId）
  onLoad(options) {
    // 1. 获取场景标识（默认商品订单）
    const scene = options.scene || 'order';
    // 2. 解析参数（兼容会员/商品场景）
    const typeName = decodeURIComponent(options.typeName || (scene === 'member' ? '会员缴费' : '商品订单支付'));
    const amount = Number(options.amount || options.totalAll || 0);
    // 新增：接收订单ID（结算页跳转时传递的）
    const orderId = options.orderId || '';

    this.setData({
      scene,
      typeName,
      amount,
      orderId // 保存订单ID到data
    });
    console.log('支付页参数：', this.data); // 此时能看到orderId
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

  // 核心：模拟支付（修改：调用paySuccess）
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

      // ========== 核心修改：调用paySuccess清空购物车 ==========
      this.paySuccess(this.data.orderId);
      // ======================================================

    }, 2000);
  },

  // 取消支付：返回上一级页面
  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

  // 支付成功后的逻辑（修复：清空后跳商城页面）
  paySuccess(orderId) {
    console.log('开始清空购物车：', { orderId }); // 先打印日志，确认进入函数
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    console.log('当前token：', accessToken); // 打印token，确认有值

    if (!accessToken) {
      console.log('无token，直接跳商城');
      wx.switchTab({url: '/pages/mall/mall'}); // 无token时直接跳商城
      return;
    }

    // 定义清空购物车的通用方法
    const clearCart = (isPrecise = false) => {
      let url = 'http://localhost:8000/app01/cart/clear/';
      if (isPrecise && orderId) {
        url = `http://localhost:8000/app01/cart/clear/${orderId}/`;
      }
      console.log('清空购物车请求URL：', url); // 打印请求URL
      return new Promise((resolve) => {
        wx.request({
          url,
          method: 'POST',
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          success: (res) => {
            console.log(`清空购物车${isPrecise?'精准':'全'}成功：`, res.data);
          },
          fail: (err) => {
            console.error(`清空购物车${isPrecise?'精准':'全'}失败：`, err);
          },
          complete: () => resolve()
        });
      });
    };

    // 先尝试精准清空，失败则全清，最后跳商城
    clearCart(true).finally(() => {
      clearCart(false).finally(() => {
        // ========== 核心修改：跳转到商城页面（tabBar页面用switchTab） ==========
        wx.switchTab({
          url: '/pages/mall/mall'
        });
        // ================================================================
      });
    });
  }

});
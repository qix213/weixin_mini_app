const app = getApp();
Page({
  data: {
    cartList: [],         // 结算商品列表
    totalAll: 0.00,       // 总价
    defaultAddress: null, // 默认收货地址
    loading: true         // 加载状态
  },

  // 页面加载时获取购物车+收货地址
  onLoad() {
    this.getCheckoutData();
  },

  // 下拉刷新重新获取数据
  onPullDownRefresh() {
    this.getCheckoutData(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 回到结算页刷新数据
  onShow() {
    this.getCheckoutData();
  },

  // 统一获取：购物车+收货地址
  getCheckoutData(callback) {
    this.setData({ loading: true });
    app.globalData.token = wx.getStorageSync('token') || '';
    
    // 登录校验
    if (!app.globalData.token) {
      wx.showModal({
        title: '提示',
        content: '请先登录再结算',
        showCancel: false,
        success: () => {
          wx.navigateTo({ url: '/pages/login/login' });
        }
      });
      this.setData({ loading: false });
      return;
    }

    // 获取购物车商品
    this.getCartList();
    // 获取收货地址
    this.getAddressList();
    callback && callback();
  },

  // 获取购物车结算商品
  getCartList() {
    app.request({
      url: '/app01/cart/',
      method: 'GET'
    }).then(res => {
      console.log('购物车数据：', res.data);
      let cartList = res.data.data?.cart_list || [];
      if (!cartList) cartList = [];
      
      // 计算总价
      const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price || 0), 0).toFixed(2);
      
      this.setData({ 
        cartList,
        totalAll
      });
    }).catch(err => {
      console.error('获取购物车失败：', err);
      this.setData({ cartList: [], totalAll: '0.00' });
      wx.showToast({ title: '获取商品失败', icon: 'none' });
    });
  },

  // 获取收货地址
  getAddressList() {
    app.request({
      url: '/app01/address/',
      method: 'GET'
    }).then(res => {
      console.log('地址数据：', res.data);
      const addressList = res.data.data?.address_list || [];
      
      if (addressList.length > 0) {
        this.setData({ defaultAddress: addressList[0] });
      } else {
        this.setData({ defaultAddress: null });
      }
    }).catch(err => {
      console.error('获取地址失败：', err);
      this.setData({ defaultAddress: null });
      wx.showToast({ title: '获取地址失败', icon: 'none' });
    }).finally(() => {
      this.setData({ loading: false });
    });
  },

  // 跳转收货地址页面
  toAddressPage() {
    wx.navigateTo({ url: '/pages/address/address' });
  },

  // 返回购物车页面
  toCart() {
    wx.navigateTo({ url: '/pages/cart/cart' });
  },

  // 核心：提交订单
  submitOrder() {
    const { defaultAddress, cartList, totalAll } = this.data;
    
    // 校验
    if (!defaultAddress) return wx.showToast({ title: '请选择收货地址', icon: 'none' });
    if (cartList.length === 0) return wx.showToast({ title: '暂无结算商品', icon: 'none' });
    if (Number(totalAll) <= 0) return wx.showToast({ title: '订单金额异常', icon: 'none' });

    const orderData = {
      address_id: defaultAddress.id,
      total_price: totalAll,
      goods_list: cartList.map(item => ({ cart_id: item.id, num: item.num }))
    };

    wx.showLoading({ title: '正在下单...', mask: true });

    // 提交订单接口
    app.request({
      url: '/app01/order/add/',
      method: 'POST',
      data: orderData
    }).then(res => {
      console.log('下单结果：', res.data);
      const result = res.data;

      if (result && (result.code === 200 || result.code === '200')) {
        wx.showToast({ title: '下单成功！即将跳转到支付页面', icon: 'success', duration: 2000 });
        
        // 跳转到支付页（商品订单场景）
        setTimeout(() => {
          wx.navigateTo({
            url: `/pages/pay/pay?scene=order&typeName=${encodeURIComponent('商品订单支付')}&totalAll=${totalAll}`
          });
        }, 2000);
      } else {
        wx.showToast({ title: result.msg || '下单失败', icon: 'none' });
      }
    }).catch(err => {
      console.error('下单失败：', err);
      wx.showToast({ title: '网络异常', icon: 'none' });
    }).finally(() => {
      wx.hideLoading();
    });
  }
});
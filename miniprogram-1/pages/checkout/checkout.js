const app = getApp();
Page({
  data: {
    deliveryType: 1,
    defaultAddress: null,
    cartList: [],
    totalAll: '0.00',
    areaList: [],
    selectedStore: null,
    storeShow: false
  },

  onLoad() {
    this.setData({ deliveryType: 1 });
    this.getCart();
    this.getAddress(); // 首次加载仍调用
  },

  // 核心修复：页面每次显示时重新获取地址（包括从地址页返回）
  onShow() {
    // 仅在快递配送模式下刷新地址（自取模式无需地址）
    if (this.data.deliveryType === 1) {
      this.getAddress();
    }
    // 可选：同时刷新购物车（防止购物车数据变动）
    this.getCart();
  },

  switchDeliveryType(e) {
    const t = Number(e.currentTarget.dataset.type);
    if (t === 1) {
      this.setData({
        deliveryType: 1,
        selectedStore: null,
        storeShow: false
      });
      // 切换到快递模式时立即刷新地址
      this.getAddress();
    } else {
      this.setData({
        deliveryType: 2,
        selectedStore: null
      });
    }
  },

  openStore() {
    if (this.data.deliveryType !== 2) return;
    wx.showLoading({ title: '加载中' });
    this.getStore().then(() => {
      wx.hideLoading();
      this.setData({ storeShow: true });
    });
  },

  closeStore() {
    this.setData({ storeShow: false });
  },

  selectStore(e) {
    this.setData({
      selectedStore: e.currentTarget.dataset.store,
      storeShow: false
    });
  },

  getCart() {
    const token = wx.getStorageSync('accessToken');
    app.request({
      url: '/app01/cart/list/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      const list = res.data?.data || [];
      let total = 0;
      const formatCart = list.map(item => {
        const p = Number(item.price || 0);
        const num = Number(item.num || 1);
        total += p * num;
        return { ...item, formatPrice: p.toFixed(2) };
      });
      this.setData({ cartList: formatCart, totalAll: total.toFixed(2) });
    }).catch(err => {
      console.error('获取购物车失败：', err);
      this.setData({ cartList: [], totalAll: '0.00' });
    });
  },

  // 优化：给getAddress添加错误处理和加载提示
  getAddress() {
    const token = wx.getStorageSync('accessToken');
    // 增加加载提示（避免用户感知不到加载）
    wx.showLoading({ title: '加载地址...', mask: false });
    app.request({
      url: '/app01/address/list/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      wx.hideLoading();
      const list = res.data?.data?.address_list || [];
      this.setData({ defaultAddress: list[0] || null });
      // 调试日志：确认返回的最新地址
      // console.log('结算页最新地址：', list[0] || '暂无地址');
    }).catch(err => {
      wx.hideLoading();
      console.error('获取地址失败：', err);
      this.setData({ defaultAddress: null });
      wx.showToast({ title: '加载地址失败', icon: 'none', duration: 1500 });
    });
  },

  getStore() {
    return new Promise((resolve) => {
      const token = wx.getStorageSync('accessToken');
      app.request({
        url: '/app01/area/list/',
        header: { Authorization: `Bearer ${token}` }
      }).then(res => {
        this.setData({ areaList: res.data?.data || [] });
        resolve();
      }).catch(err => {
        console.error('获取门店失败：', err);
        this.setData({ areaList: [] });
        resolve();
      });
    });
  },

  toAddressPage() {
    wx.navigateTo({ url: '/pages/address/address' });
  },

  submitOrder() {
    const { deliveryType, defaultAddress, selectedStore, cartList } = this.data;

    // 前置校验
    if (cartList.length === 0) {
      wx.showToast({ title: '暂无结算商品', icon: 'none' });
      return;
    }
    if (deliveryType === 1 && !defaultAddress) {
      wx.showModal({
        title: '提示',
        content: '请先添加收货地址',
        confirmText: '去添加',
        success: (res) => res.confirm && this.toAddressPage()
      });
      return;
    }
    if (deliveryType === 2 && !selectedStore) {
      wx.showToast({ title: '请选择取货门店', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '创建订单中...', mask: true });
    
    // 总价从字符串转浮点数
    const totalPrice = parseFloat(this.data.totalAll) || 0;
    // 构造商品列表
    const goodsList = cartList.map(item => ({
      cart_id: Number(item.id) || 0,
      num: parseInt(item.num, 10) || 1
    }));
    // 空值处理
    const addressId = deliveryType === 1 ? (defaultAddress ? Number(defaultAddress.id) : null) : null;
    const pickUpStoreId = deliveryType === 2 ? (selectedStore ? Number(selectedStore.id) : null) : null;

    // 构造下单参数
    const orderData = {
      delivery_type: Number(deliveryType),
      address_id: addressId,
      pick_up_store_id: pickUpStoreId,
      total_price: totalPrice,
      goods_list: goodsList
    };

    // console.log('提交订单参数：', JSON.stringify(orderData, null, 2));

    // 调用创建订单接口
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    app.request({
      url: '/app01/order/add/',
      method: 'POST',
      header: {
        'Authorization': `Bearer ${token}`,
        'content-type': 'application/json'
      },
      data: orderData
    }).then(res => {
      wx.hideLoading();
      // console.log('创建订单返回：', res);
      if (res.data.code === 200) {
        const { order_id, total_price } = res.data.data;
        wx.navigateTo({
          url: `/pages/pay/pay?orderId=${order_id}&amount=${total_price}&typeName=商品订单`
        });
      } else {
        wx.showToast({ title: res.data.msg || '创建订单失败', icon: 'none', duration: 3000 });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('创建订单失败：', err);
      wx.showToast({ title: '网络异常，创建订单失败', icon: 'none' });
    });
  }
});
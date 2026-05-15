const app = getApp();
Page({
  data: {
    deliveryType: 1,
    defaultAddress: null,
    cartList: [],
    totalAll: '0.00',      
    areaList: [],
    selectedStore: null,
    storeShow: false,
    userPoints: 0,         
    deductPoint: 0,        
    hasExchangeGoods: false,
    maxDeductPoint: 0,     
    deductMoney: '0.00',   
    actualPayMoney: '0.00',
    isAllPointGoods: false,
    totalPoints: 0         
  },

  useAllPoints() {
    const { maxDeductPoint, userPoints } = this.data;
    const actualMaxDeduct = userPoints > 0 ? Math.min(maxDeductPoint, userPoints) : 0; 
    if (actualMaxDeduct <= 0) {
      wx.showToast({ title: '暂无可抵扣积分（将纯现金支付）', icon: 'none' });
      this.setData({ deductPoint: 0 }, () => this.calcMoney());
      return;
    }
    this.setData({ deductPoint: actualMaxDeduct }, () => {
      this.calcMoney(); 
      wx.showToast({ title: `已选择抵扣${actualMaxDeduct}分`, icon: 'success', duration: 1000 });
    });
  },

isPointGoods(item) {
  const app = getApp();
  const goodsId = item.goods_id || item.id;
  
  // 1. 从全局变量或本地存储中安全读取缓存对象
  let cacheObj = app.globalData.goodsPointCache;
  if (!cacheObj) {
    cacheObj = wx.getStorageSync('goodsPointCache') || {};
    app.globalData.goodsPointCache = cacheObj;
  }
  
  // 2. 获取当前商品的积分标识
  const cacheIsPoint = cacheObj[goodsId];
  const isForcePointGoods = item.price > 0; 
  
  if (cacheIsPoint !== undefined) {
    return cacheIsPoint || isForcePointGoods;
  }

  const pointField = item.can_point_exchange || item.is_point_goods || item.is_exchange || item.exchangeable || false;
  const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
  
  let isPoint = false;
  if (typeof pointField === 'string') {
    isPoint = pointField.toLowerCase() === 'true' || pointField === '1';
  } else if (typeof pointField === 'number') {
    isPoint = pointField === 1;
  } else {
    isPoint = !!pointField;
  }
  return isPoint || isForcePointGoods;
},

  calcPointPrice(price) {
    const priceStr = (price || '0').toString().replace(/[^0-9.]/g, '');
    const priceNum = parseFloat(priceStr) || 0;
    const pointPrice = Math.floor(priceNum * 100);
    return Number(pointPrice);
  },

  onLoad(options) {
    const cartIsAllPoint = options.isAllPointGoods === 'true';
    this.setData({ 
      deliveryType: 1,
      isAllPointGoods: cartIsAllPoint
    });
    this.getCart();
    this.getAddress();
    this.getUserPoints();
  },

  onShow() {
    if (this.data.deliveryType === 1) {
      this.getAddress();
    }
    this.getCart();
    this.getUserPoints();
  },

  calcMoney() {
    const { deductPoint, isAllPointGoods, totalAll, totalPoints, userPoints } = this.data;
    const actualDeductPoints = userPoints > 0 ? Math.min(deductPoint || 0, userPoints) : 0;
    
    if (isAllPointGoods) {
      const totalNeedPoints = totalPoints;
      const finalDeductPoints = Math.min(actualDeductPoints, totalNeedPoints);
      const remainPoints = totalNeedPoints - finalDeductPoints;
      const remainMoney = (remainPoints / 100).toFixed(2);
      
      this.setData({
        deductPoint: finalDeductPoints,
        deductMoney: (finalDeductPoints * 0.01).toFixed(2),
        actualPayMoney: remainMoney
      });
    } else {
      const totalMoney = parseFloat(totalAll) || 0;
      const maxByMoney = Math.floor(totalMoney * 100);
      const finalDeductPoints = userPoints > 0 ? Math.min(actualDeductPoints, maxByMoney) : 0;
      const deductMoney = (finalDeductPoints * 0.01).toFixed(2);
      const actualPayMoney = Math.max(totalMoney - finalDeductPoints * 0.01, 0).toFixed(2);
      
      this.setData({
        deductPoint: finalDeductPoints,
        deductMoney: deductMoney,
        actualPayMoney: actualPayMoney
      });
    }
  },

  getUserPoints() {
    const token = wx.getStorageSync('accessToken');
    app.request({
      url: '/app01/user/points/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      if (res.data?.code === 200) {
        this.setData({ userPoints: res.data.data.points || 0 });
        this.calcMaxDeductPoint();
        this.calcMoney();
      }
    }).catch(err => {
      console.error('获取积分失败：', err);
      this.setData({ userPoints: 0 });
      this.calcMoney();
    });
  },

  calcMaxDeductPoint() {
    const { userPoints, isAllPointGoods, totalAll, totalPoints } = this.data;
    let maxDeductPoint = 0;
    if (isAllPointGoods) {
      maxDeductPoint = userPoints > 0 ? Math.min(totalPoints, userPoints) : 0;
    } else {
      const totalMoney = parseFloat(totalAll) || 0;
      const maxByMoney = Math.floor(totalMoney * 100);
      maxDeductPoint = userPoints > 0 ? Math.min(maxByMoney, userPoints) : 0;
    }

    this.setData({
      maxDeductPoint,
      deductPoint: Math.min(this.data.deductPoint || 0, maxDeductPoint)
    });
    this.calcMoney();
  },

  switchDeliveryType(e) {
    const t = Number(e.currentTarget.dataset.type);
    if (t === 1) {
      this.setData({
        deliveryType: 1,
        selectedStore: null,
        storeShow: false
      });
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
      let totalMoney = 0;
      let totalPoints = 0;
      let hasExchangeGoods = false;
      let isAllPointGoods = list.length > 0 ? true : false; 

      const formatCart = list.map(item => {
        const isPointGoods = this.isPointGoods(item);
        const goodsPrice = item.member_price || item.price || item.goods_price || 0;
        const pointPrice = isPointGoods ? this.calcPointPrice(goodsPrice) : 0;
        const num = Number(item.num || 1);
        
        if (isPointGoods) {
          totalPoints += pointPrice * num;
          hasExchangeGoods = true;
        } else {
          const price = Number(goodsPrice || 0);
          totalMoney += price * num;
          isAllPointGoods = false;
        }

        const formatPrice = isPointGoods 
          ? `${pointPrice} 积分` 
          : Number(goodsPrice || 0).toFixed(2);

        return { 
          ...item, 
          isPointGoods,
          pointPrice,
          formatPrice,
          goodsPrice
        };
      });

      const totalAll = isAllPointGoods 
        ? totalPoints.toString() 
        : totalMoney.toFixed(2);

      this.setData({
        cartList: formatCart,
        totalAll: totalAll,
        totalPoints: totalPoints,
        hasExchangeGoods: hasExchangeGoods,
        isAllPointGoods: isAllPointGoods
      });
      
      this.calcMaxDeductPoint();
      this.calcMoney();
    }).catch(err => {
      console.error('获取购物车失败：', err);
      this.setData({ 
        cartList: [], 
        totalAll: '0.00',
        totalPoints: 0,
        hasExchangeGoods: false,
        isAllPointGoods: false
      });
      this.calcMoney();
    });
  },

  getAddress() {
    const token = wx.getStorageSync('accessToken');
    wx.showLoading({ title: '加载地址...', mask: false });
    app.request({
      url: '/app01/address/list/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      wx.hideLoading();
      const list = res.data?.data?.address_list || [];
      this.setData({ defaultAddress: list[0] || null });
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

  minusPoint() {
    if (this.data.deductPoint > 0) {
      this.setData({ deductPoint: this.data.deductPoint - 1 }, () => {
        this.calcMoney();
      });
    } else {
      wx.showToast({ title: '抵扣积分不能低于0分', icon: 'none' });
    }
  },

  plusPoint() {
    if (this.data.deductPoint < this.data.maxDeductPoint) {
      this.setData({ deductPoint: this.data.deductPoint + 1 }, () => {
        this.calcMoney();
      });
    }
  },

  inputPoint(e) {
    let val = Number(e.detail.value) || 0;
    val = Math.max(0, Math.min(val, this.data.maxDeductPoint));
    this.setData({ deductPoint: val }, () => {
      this.calcMoney();
    });
  },

  // 提交订单：仅创建订单，不做任何积分扣减操作
  submitOrder() {
    const { 
      deliveryType, defaultAddress, selectedStore, cartList, 
      deductPoint, isAllPointGoods, totalAll, actualPayMoney
    } = this.data;
  
    // 基础校验
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
  
    // 仅记录要抵扣的积分，不做任何扣减逻辑
    const finalDeductPoint = this.data.userPoints > 0 ? deductPoint : 0;
    const totalPrice = parseFloat(totalAll) || 0;
    const deductMoney = parseFloat(this.data.deductMoney) || 0;
    const cashPayMoney = parseFloat(actualPayMoney) || 0;
  
    const goodsList = cartList.map(item => ({
      cart_id: Number(item.id) || 0,
      num: parseInt(item.num, 10) || 1,
      is_point_goods: item.isPointGoods,
      point_price: item.pointPrice || 0
    }));
  
    const orderData = {
      delivery_type: Number(deliveryType),
      address_id: deliveryType === 1 ? (defaultAddress ? Number(defaultAddress.id) : null) : null,
      pick_up_store_id: deliveryType === 2 ? (selectedStore ? Number(selectedStore.id) : null) : null,
      total_price: totalPrice,
      deduct_point: finalDeductPoint, // 仅传递，后端只记录不扣减
      deduct_money: deductMoney,
      cash_pay_money: cashPayMoney,
      goods_list: goodsList,
      is_all_point_goods: isAllPointGoods
    };
  
    wx.showLoading({ title: '创建订单中...', mask: true });
    app.request({
      url: '/app01/order/add/',
      method: 'POST',
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('accessToken')}`,
        'content-type': 'application/json'
      },
      data: orderData
    }).then(res => {
      wx.hideLoading();
      if (res.data.code === 200) {
        const { order_id } = res.data.data;
        // 🔥核心修正：跳转支付页传递正确参数
        // totalAll=订单总额，actualAmount=实付金额，deduct_point=积分抵扣数
        wx.navigateTo({
          url: `/pages/pay/pay?orderId=${order_id}&totalAll=${totalPrice.toFixed(2)}&actualAmount=${cashPayMoney.toFixed(2)}&typeName=混合支付订单&deduct_point=${finalDeductPoint}`
        });
      } else {
        console.error('后端返回错误：', res.data);
        wx.showToast({ title: res.data.msg || '创建订单失败', icon: 'none', duration: 3000 });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('请求失败：', err);
      wx.showToast({ title: '网络异常，创建订单失败', icon: 'none' });
    });
  }
});
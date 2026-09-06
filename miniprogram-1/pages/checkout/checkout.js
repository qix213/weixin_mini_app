const app = getApp();

Page({
  data: {
    deliveryType: 1,
    defaultAddress: null,
    cartList: [],
    areaList: [],
    selectedStore: null,
    storeShow: false,
    
    userPoints: 0,
    totalCashPrice: '0.00',
    totalPointPrice: 0,
    hasExchangeGoods: false,
    
    maxDeductPoint: 0,
    deductPoint: 0,
    remainPointMoney: '0.00',
    actualPayMoney: '0.00',
    
    // 🌟 新增：用户星级身份标识
    userType: 1 
  },

  onLoad(options) {
    this.initUserType();
    this.setData({ deliveryType: 1 });
    this.getCart();
    this.getAddress();
    this.getUserPoints();
  },

  onShow() {
    this.initUserType();
    if (this.data.deliveryType === 1) this.getAddress();
    this.getCart();
    this.getUserPoints();
  },

  // 🌟 1. 安全初始化用户等级
  initUserType() {
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    let type = memberInfo.user_type;
    // 确保0星(0)能被正确解析，而不是变成undefined去走兜底
    this.setData({ userType: (type !== undefined && type !== null) ? parseInt(type) : 1 });
  },

  // 🌟 2. 极其强壮的价格提取器：自动剥离嵌套，自动判断等级
  getGoodsCashPrice(item) {
    if (!item) return 0;
    // 兼容后端扁平和嵌套两种结构
    const goodsObj = item.goods || item; 
    const currentLevel = parseInt(this.data.userType);
    
    // 取会员价 (兜底取0)
    const mPrice = Number(goodsObj.member_price || item.member_price || goodsObj.price || item.price || 0);
    // 取零售价 (最关键的一步：如果后端接口里没返回 original_price，只能被迫兜底取会员价)
    const oPrice = Number(goodsObj.original_price || item.original_price || mPrice);
    
    // 0星(<=1)取零售价，星级(>1)取会员价
    return currentLevel <= 1 ? oPrice : mPrice;
  },

  isPointGoods(item) {
    const flags = [item.is_support_point_exchange, item.goods?.is_support_point_exchange];
    for (let flag of flags) {
      if (flag !== undefined && flag !== null) {
        return String(flag) === '1' || String(flag).toLowerCase() === 'true' || flag === true;
      }
    }
    const goodsId = item.goods_id || item.goods?.id || item.id;
    let cacheObj = app.globalData.goodsPointCache || wx.getStorageSync('goodsPointCache') || {};
    if (cacheObj[goodsId] !== undefined) return cacheObj[goodsId];
    return false;
  },

// 双轨制算账模型（带详情打印）
calcMoney() {
  const { deductPoint, totalCashPrice, totalPointPrice, userPoints } = this.data;
  
  const baseCash = parseFloat(totalCashPrice) || 0;
  const needPoints = parseInt(totalPointPrice) || 0;
  
  const actualUsePoints = userPoints > 0 ? Math.min(deductPoint || 0, userPoints) : 0;
  const finalUsePoints = Math.min(actualUsePoints, needPoints);
  
  const shortfallPoints = Math.max(needPoints - finalUsePoints, 0);
  const shortfallMoney = shortfallPoints / 100;
  
  const actualPayMoney = (baseCash + shortfallMoney).toFixed(2);
  
  console.log("===== 【3. calcMoney 最终支付计算】 =====");
  console.log("纯现金商品总计 (baseCash):", baseCash);
  console.log("积分不够转化的现金 (shortfallMoney):", shortfallMoney);
  console.log("【最终实付金额】 (actualPayMoney):", actualPayMoney);
  console.log("======================================");

  this.setData({
    deductPoint: finalUsePoints,
    remainPointMoney: shortfallMoney.toFixed(2),
    actualPayMoney: actualPayMoney
  });
},

getCart() {
  const token = wx.getStorageSync('accessToken');
  app.request({
    url: '/app01/cart/list/',
    header: { Authorization: `Bearer ${token}` }
  }).then(res => {
    const list = res.data?.data || [];
    
    let sumCash = 0;   
    let sumPoints = 0; 
    let hasExchangeGoods = false;
    
    const currentUserType = parseInt(this.data.userType) || 1;

    console.log("\n\n========== 【结算页价格调试 START】 ==========");
    console.log("1. 当前用户身份 (userType):", currentUserType, currentUserType <= 1 ? "(0星，应该取零售价)" : "(星级，应该取会员价)");

    const formatCart = list.map((item, index) => {
      const goodsType = item.goods_type || item.goods?.goods_type || 0; 
      const isPoint = this.isPointGoods(item);
      const num = Number(item.num || 1);
      
      // 🌟 修复并增强取值逻辑：防止嵌套层级找不到
      const memberPrice = Number(item.member_price || item.goods?.member_price || item.price || item.goods?.price || 0);
      const originalPrice = Number(item.original_price || item.goods?.original_price || memberPrice);
      
      const cashPrice = currentUserType <= 1 ? originalPrice : memberPrice;
      
      console.log(`\n--- 商品 ${index + 1}: ${item.goods?.name || '未知商品'} ---`);
      console.log("后端返回的完整 item 对象:", item);
      console.log("解析出的 originalPrice (零售价):", originalPrice);
      console.log("解析出的 memberPrice (会员价):", memberPrice);
      console.log("👉 最终决定使用的单价 (cashPrice):", cashPrice);
      console.log("购买数量 (num):", num);
      
      let showUnit = '¥';
      let showPrice = cashPrice.toFixed(2);
      
      if (isPoint) {
        hasExchangeGoods = true;
        let pointPrice = Number(item.point_price || item.goods?.point_price || 0);
        if (pointPrice <= 0) pointPrice = Math.floor(cashPrice * 100); 
        sumPoints += pointPrice * num;
        showUnit = '积分';
        showPrice = pointPrice; 
        item.isPointGoods = true;
        item.pointPrice = pointPrice;
        console.log(`类型: 积分商品，小计: ${pointPrice * num} 积分`);
      } else {
        sumCash += cashPrice * num;
        item.isPointGoods = false;
        console.log(`类型: 现金商品，小计: ${cashPrice * num} 元`);
      }

      return { ...item, goods_type: goodsType, showUnit, showPrice };
    });

    console.log("\n2. 遍历结束，汇总结果:");
    console.log("所有现金商品总价 (sumCash):", sumCash);
    console.log("========== 【结算页价格调试 END】 ==========\n\n");

    const isOfflineProject = formatCart.some(item => Number(item.goods_type) === 2);

    this.setData({
      cartList: formatCart,
      totalCashPrice: sumCash.toFixed(2),
      totalPointPrice: sumPoints,
      hasExchangeGoods: hasExchangeGoods
    }, () => {
      const maxLimit = Math.min(this.data.totalPointPrice, this.data.userPoints);
      
      if (isOfflineProject) {
        this.setData({
          deliveryType: 2,
          defaultAddress: null,
          maxDeductPoint: maxLimit,
          deductPoint: maxLimit 
        });
      } else {
        this.setData({
          maxDeductPoint: maxLimit,
          deductPoint: maxLimit 
        });
      }
      this.calcMoney();
    });
    
  }).catch(err => {
    console.error('获取购物车失败：', err);
    this.setData({ cartList: [], totalCashPrice: '0.00', totalPointPrice: 0, hasExchangeGoods: false });
    this.calcMoney();
  });
},

  getUserPoints() {
    const token = wx.getStorageSync('accessToken');
    app.request({
      url: '/app01/user/points/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      if (res.data?.code === 200) {
        this.setData({ userPoints: res.data.data.points || 0 });
      }
    });
  },

  clearPoint() { this.setData({ deductPoint: 0 }, () => { this.calcMoney(); wx.showToast({ title: '已清零', icon: 'none', duration: 800 }); }); },
  useAllPoints() { const maxLimit = Math.min(this.data.totalPointPrice, this.data.userPoints); this.setData({ deductPoint: maxLimit }, () => this.calcMoney()); },
  minusPoint() { if (this.data.deductPoint > 0) this.setData({ deductPoint: this.data.deductPoint - 1 }, () => this.calcMoney()); },
  plusPoint() { if (this.data.deductPoint < this.data.maxDeductPoint) this.setData({ deductPoint: this.data.deductPoint + 1 }, () => this.calcMoney()); },
  inputPoint(e) {
    let val = Number(e.detail.value) || 0;
    val = Math.max(0, Math.min(val, this.data.maxDeductPoint));
    this.setData({ deductPoint: val }, () => this.calcMoney());
  },

  switchDeliveryType(e) {
    const t = Number(e.currentTarget.dataset.type);
    const isOfflineProject = this.data.cartList.some(item => Number(item.goods_type) === 2);
    if (isOfflineProject && t === 1) {
      return wx.showToast({ title: '服务项目仅支持到店核销，无法选择快递上门', icon: 'none', duration: 2000 });
    }
    if (t === 1) {
      this.setData({ deliveryType: 1, selectedStore: null, storeShow: false });
      this.getAddress();
    } else {
      this.setData({ deliveryType: 2, selectedStore: null });
    }
  },

  openStore() {
    if (this.data.deliveryType !== 2) return;
    wx.showLoading({ title: '加载中' });
    this.getStore().then(() => { wx.hideLoading(); this.setData({ storeShow: true }); });
  },

  closeStore() { this.setData({ storeShow: false }); },
  selectStore(e) { this.setData({ selectedStore: e.currentTarget.dataset.store, storeShow: false }); },

  getAddress() {
    const token = wx.getStorageSync('accessToken');
    app.request({ url: '/app01/address/list/', header: { Authorization: `Bearer ${token}` } }).then(res => {
      const list = res.data?.data?.address_list || [];
      this.setData({ defaultAddress: list[0] || null });
    });
  },

  getStore() {
    return new Promise((resolve) => {
      const token = wx.getStorageSync('accessToken');
      app.request({ url: '/app01/area/list/', header: { Authorization: `Bearer ${token}` } }).then(res => {
        this.setData({ areaList: res.data?.data || [] });
        resolve();
      });
    });
  },

  toAddressPage() { wx.navigateTo({ url: '/pages/address/address' }); },

  submitOrder() {
    const { deliveryType, defaultAddress, selectedStore, cartList, deductPoint, totalCashPrice, actualPayMoney } = this.data;
    if (cartList.length === 0) return;
  
    const isOfflineProject = cartList.some(item => Number(item.goods_type) === 2);
    if (isOfflineProject && !selectedStore) return wx.showToast({ title: '请选择要核销的服务门店', icon: 'none' });
    if (!isOfflineProject) {
      if (deliveryType === 1 && !defaultAddress) { this.toAddressPage(); return; }
      if (deliveryType === 2 && !selectedStore) return wx.showToast({ title: '请选择自提门店', icon: 'none' });
    }
  
    const goodsList = cartList.map(item => ({ cart_id: Number(item.id) || 0, num: parseInt(item.num, 10) || 1 }));
  
    const orderData = {
      order_type: isOfflineProject ? 2 : 1, 
      delivery_type: isOfflineProject ? 2 : Number(deliveryType), 
      address_id: (deliveryType === 1 && !isOfflineProject) ? Number(defaultAddress.id) : null,
      pick_up_store_id: (isOfflineProject || deliveryType === 2) ? Number(selectedStore.id) : null,
      total_price: parseFloat(totalCashPrice) || 0, 
      deduct_point: deductPoint,
      cash_pay_money: parseFloat(actualPayMoney) || 0,
      goods_list: goodsList
    };
  
    wx.showLoading({ title: '提交中...' });
    app.request({
      url: '/app01/order/add/', 
      method: 'POST',
      header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}`, 'content-type': 'application/json' },
      data: orderData
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res; 
      if (result.code === 200) {
        const orderSn = result.data.order_sn || result.data.id;
        
        // 🌟 终极修复：支付页面上显示的金额，无条件使用后端刚刚算好的订单金额！！！
        // 不再传递前端自己算出来的 actualPayMoney
        let realPayMoney = result.data.actual_pay_money !== undefined ? result.data.actual_pay_money : actualPayMoney;
        
        wx.navigateTo({ 
          url: `/pages/pay/pay?orderId=${orderSn}&actualAmount=${parseFloat(realPayMoney).toFixed(2)}&deduct_point=${deductPoint}&isOfflineProject=${isOfflineProject}` 
        });
      } else {
        wx.showToast({ title: result.msg || '订单提交失败', icon: 'none' });
      }
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常，请重试', icon: 'none' });
    });
  }
});
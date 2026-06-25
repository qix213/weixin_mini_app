const app = getApp();

Page({
  data: {
    deliveryType: 1,
    defaultAddress: null,
    cartList: [],
    areaList: [],
    selectedStore: null,
    storeShow: false,
    
    // ================= 独立资金池 =================
    userPoints: 0,             // 用户拥有的总积分
    totalCashPrice: '0.00',    // 纯现金商品总计（元）
    totalPointPrice: 0,        // 纯积分商品总计（积分）
    
    hasExchangeGoods: false,   // 购物车是否包含积分商品
    
    // ================= 结算双轨模型 =================
    maxDeductPoint: 0,         // 本次最多能用掉多少积分
    deductPoint: 0,            // 用户当前决定使用的积分数
    remainPointMoney: '0.00',  // 积分不够时，积分商品缺口转成需要补齐的现金
    actualPayMoney: '0.00'     // 最终必须支付的总现金
  },

  onLoad(options) {
    this.setData({ deliveryType: 1 });
    this.getCart();
    this.getAddress();
    this.getUserPoints();
  },

  onShow() {
    if (this.data.deliveryType === 1) this.getAddress();
    this.getCart();
    this.getUserPoints();
  },

  // 🌟 修复 1：广谱特征识别，把后端所有可能扔过来的字段全部枚举，确保积分商品绝对不漏判
  isPointGoods(item) {
    // 1. 严格匹配后端定义的 is_support_point_exchange 字段（支持扁平结构和 goods 嵌套结构）
    const flags = [
      item.is_support_point_exchange,
      item.goods?.is_support_point_exchange
    ];

    for (let flag of flags) {
      if (flag !== undefined && flag !== null) {
        return String(flag) === '1' || String(flag).toLowerCase() === 'true' || flag === true;
      }
    }
    
    // 2. 检查本地商品详情页带过来的缓存（作为二级兜底）
    const goodsId = item.goods_id || item.goods?.id || item.id;
    let cacheObj = app.globalData.goodsPointCache || wx.getStorageSync('goodsPointCache') || {};
    if (cacheObj[goodsId] !== undefined) {
      return cacheObj[goodsId];
    }
    
    // 3. 严格兜底：没有明确标记支持积分兑换的，一律视为普通现金商品
    return false;
  },

  // 🌟 修复 2：双轨制算账模型
  calcMoney() {
    const { deductPoint, totalCashPrice, totalPointPrice, userPoints } = this.data;
    
    // 1. 现金部分：现金商品多少钱，基础就付多少钱
    const baseCash = parseFloat(totalCashPrice) || 0;
    
    // 2. 积分部分：积分商品一共需要多少积分
    const needPoints = parseInt(totalPointPrice) || 0;
    
    // 3. 计算实际用掉的积分
    const actualUsePoints = userPoints > 0 ? Math.min(deductPoint || 0, userPoints) : 0;
    const finalUsePoints = Math.min(actualUsePoints, needPoints);
    
    // 4. 【核心业务】积分不够的，用现金结算缺口 (100积分=1元)
    const shortfallPoints = Math.max(needPoints - finalUsePoints, 0);
    const shortfallMoney = shortfallPoints / 100;
    
    // 5. 最终实付现金 = 纯现金商品总价 + 积分不够补的现金
    const actualPayMoney = (baseCash + shortfallMoney).toFixed(2);
    
    this.setData({
      deductPoint: finalUsePoints,
      remainPointMoney: shortfallMoney.toFixed(2),
      actualPayMoney: actualPayMoney
    });
  },

  // 🌟 修复 3：购物车加载成功后，默认直接把积分全部扣满，不让初始显示为0
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
      
      const formatCart = list.map((item, index) => {

        // 执行识别
        const isPoint = this.isPointGoods(item);

        const cashPrice = Number(item.member_price || item.price || item.goods_price || item.goods?.price || 0);
        const num = Number(item.num || 1);
        
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
        } else {
          sumCash += cashPrice * num;
          item.isPointGoods = false;
        }

        return { ...item, showUnit, showPrice };
      });

      this.setData({
        cartList: formatCart,
        totalCashPrice: sumCash.toFixed(2),
        totalPointPrice: sumPoints,
        hasExchangeGoods: hasExchangeGoods
      }, () => {
        const maxLimit = Math.min(this.data.totalPointPrice, this.data.userPoints);
        this.setData({
          maxDeductPoint: maxLimit,
          deductPoint: maxLimit 
        });
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

  clearPoint() {
    this.setData({ deductPoint: 0 }, () => {
      this.calcMoney();
      wx.showToast({ title: '已清零', icon: 'none', duration: 800 });
    });
  },

  useAllPoints() {
    const maxLimit = Math.min(this.data.totalPointPrice, this.data.userPoints);
    this.setData({ deductPoint: maxLimit }, () => this.calcMoney());
  },

  minusPoint() {
    if (this.data.deductPoint > 0) this.setData({ deductPoint: this.data.deductPoint - 1 }, () => this.calcMoney());
  },

  plusPoint() {
    if (this.data.deductPoint < this.data.maxDeductPoint) this.setData({ deductPoint: this.data.deductPoint + 1 }, () => this.calcMoney());
  },

  inputPoint(e) {
    let val = Number(e.detail.value) || 0;
    val = Math.max(0, Math.min(val, this.data.maxDeductPoint));
    this.setData({ deductPoint: val }, () => this.calcMoney());
  },

  switchDeliveryType(e) {
    const t = Number(e.currentTarget.dataset.type);
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

    // ================= 🌟 统一改为 == 2，确保字符串和数字都能完美拦截 =================
    const isOfflineProject = cartList.some(item => item.goods_type == 2 || item.goodsType == 2);

    if (isOfflineProject) {
      // 1. 线下项目不需要发货，直接提取商品 ID 和名称
      const goodsId = cartList[0].goods_id || cartList[0].id;
      const typeName = cartList[0].name || cartList[0].goods_name || '线下项目预约';

      // 2. 绕过传统的订单生成接口，直接跳去 pay.js 走我们的场景 D 支付！
      wx.navigateTo({ 
        url: `/pages/pay/pay?isOfflineProject=true&orderId=${goodsId}&actualAmount=${parseFloat(actualPayMoney).toFixed(2)}&deduct_point=${deductPoint}&typeName=${typeName}` 
      });
      
      return; // 拦截成功，直接 return，不往下走常规订单逻辑
    }


    // ================= 🛒 以下为原有的实体商品常规订单逻辑 =================
    if (deliveryType === 1 && !defaultAddress) { this.toAddressPage(); return; }
    if (deliveryType === 2 && !selectedStore) return;
  
    const goodsList = cartList.map(item => ({
      cart_id: Number(item.id) || 0,
      num: parseInt(item.num, 10) || 1,
      is_point_goods: item.isPointGoods,
      point_price: item.isPointGoods ? item.pointPrice : 0
    }));
  
    const orderData = {
      delivery_type: Number(deliveryType),
      address_id: deliveryType === 1 ? Number(defaultAddress.id) : null,
      pick_up_store_id: deliveryType === 2 ? Number(selectedStore.id) : null,
      total_price: parseFloat(totalCashPrice) || 0, 
      deduct_point: deductPoint,
      cash_pay_money: parseFloat(actualPayMoney) || 0,
      goods_list: goodsList
    };
  
    wx.showLoading({ title: '提交中...' });
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
        wx.navigateTo({ 
          url: `/pages/pay/pay?orderId=${res.data.data.order_id}&actualAmount=${parseFloat(actualPayMoney).toFixed(2)}&deduct_point=${deductPoint}` 
        });
      } else {
        wx.showToast({ title: res.data.msg || '订单提交失败', icon: 'none' });
      }
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常，请重试', icon: 'none' });
    });
  }
});
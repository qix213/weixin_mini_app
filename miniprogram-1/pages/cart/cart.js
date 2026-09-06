import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    cartList: [],        // 购物车商品列表
    loading: true,       // 加载状态
    isLogin: true,       // 当前是否已登录状态（默认先当做true，避免闪烁）
    
    // ================= 🌟 核心拆分双资产池 =================
    totalCashPrice: '0.00',   // 纯现金商品总计（元）
    totalPointPrice: 0,       // 纯积分商品总计（积分）
    
    // 🌟 新增：用户星级身份标识
    userType: 1
  },

  // 🌟 1. 严格对齐后端核心字段，精准识别积分商品
  isPointGoods(goods) {
    if (!goods) return false;
    const flag = goods.is_support_point_exchange;
    return String(flag) === '1' || String(flag).toLowerCase() === 'true' || flag === true;
  },

  calcPointPrice(price) {
    const priceStr = (price || '0').toString().replace(/[^0-9.]/g, '');
    const priceNum = parseFloat(priceStr) || 0;
    return Math.floor(priceNum * 100);
  },

  // 🌟 新增：根据用户星级，动态获取真实的商品单价
  getGoodsCashPrice(goods) {
    if (!goods) return 0;
    const currentUserType = parseInt(this.data.userType) || 1;
    
    const memberPrice = Number(goods.member_price || goods.price || 0);
    const originalPrice = Number(goods.original_price || memberPrice); // 没填零售价兜底拿会员价
    
    // 0星用户取零售价，星级用户取会员价
    return currentUserType <= 1 ? originalPrice : memberPrice;
  },

  onLoad(options) {
    if (options.paid === 'true') {
      const orderId = options.orderId || ''; 
      this.resetCartData(); 
      this.clearPaidCart(orderId).then(() => {
        this.getCartList(); 
      });
      return;
    }
    // onLoad 通常不需要拉取，交由 onShow 统筹
  },

  onShow() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    
    // 🌟 每次显示页面，获取最新的用户身份
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    this.setData({ userType: memberInfo.user_type || 1 });
    
    if (!accessToken) {
      this.setData({ 
        isLogin: false, 
        cartList: [], 
        totalCashPrice: '0.00', 
        totalPointPrice: 0,
        loading: false 
      });
      return; 
    }

    this.setData({ isLogin: true, cartList: [], totalCashPrice: '0.00', totalPointPrice: 0 });
    this.getCartList();
  },

  clearPaidCart(orderId = '') {
    return new Promise((resolve) => {
      const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      if (!accessToken) { resolve(); return; }

      const clearUrl = orderId 
      ? `${app.globalData.baseUrl}/app01/cart/clear/${orderId}/`
      : `${app.globalData.baseUrl}/app01/cart/clear/`;

      wx.request({
        url: clearUrl, method: 'POST',
        header: { 'content-type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
        success: (res) => {
          if (res.data && res.data.code === 200) Toast.success('购物车已清空');
        },
        complete: () => resolve()
      });
    });
  },

  resetCartData() {
    this.setData({ cartList: [], totalCashPrice: '0.00', totalPointPrice: 0, loading: true });
    wx.removeStorageSync('cartList');
  },

  onPullDownRefresh() {
    this.resetCartData(); 
    this.getCartList(() => wx.stopPullDownRefresh());
  },

  // 🌟 2. 获取列表时：双轨独立统计
  getCartList(callback) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      this.setData({ isLogin: false, loading: false });
      callback && callback();
      return;
    }

    const header = {
      'content-type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    };

    this.setData({ loading: true });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/cart/`,
      method: 'GET',
      header: header,
      success: (res) => {
        if (res.statusCode === 401 || (res.data && res.data.detail === "身份认证信息未提供")) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          app.globalData.isLogin = false;
          
          this.setData({ isLogin: false, cartList: [], totalCashPrice: '0.00', totalPointPrice: 0 });
          
          wx.showModal({
            title: '登录过期', content: '请重新登录以查看购物车', showCancel: false,
            success: () => {
              wx.navigateTo({ url: '/pages/login/login' });
            }
          });
          return;
        }

        let cartList = [];
        let sumCash = 0;   
        let sumPoints = 0; 
        
        if (res.data && res.data.code === 200) {
          cartList = res.data.data.cart_list || [];
          
          const formatCartList = cartList.map(item => {
            if (item.goods?.image_url) {
              item.goods.image_url = item.goods.image_url.replace('//media/', '/media/');
            }
            
            const isPointGoods = this.isPointGoods(item.goods);
            
            // 🌟 核心修改：不再写死 member_price，动态取真实价格
            const goodsPrice = this.getGoodsCashPrice(item.goods);
            
            let pointPrice = 0;
            if (isPointGoods) {
              pointPrice = Number(item.goods?.point_price || 0);
              // 积分商品如果没填积分价，自动用现金价折算 (1元=100积分)
              if (pointPrice <= 0) pointPrice = this.calcPointPrice(goodsPrice);
            }
            
            const num = Number(item.num || 1);
            let total_price = 0;
            
            if (isPointGoods) {
              total_price = pointPrice * num;
              sumPoints += total_price;
            } else {
              total_price = goodsPrice * num;
              sumCash += total_price; 
            }
            const currentUserType = parseInt(this.data.userType) || 1;
            const priceLabel = currentUserType <= 1 ? '零售价' : '会员价'
            return {
              ...item,
              isPointGoods: isPointGoods,
              pointPrice: pointPrice,
              total_price: isPointGoods ? total_price.toString() : total_price.toFixed(2),
              show_single_price: isPointGoods ? pointPrice.toString() : goodsPrice.toFixed(2),
              price_label: priceLabel
            };
          });
          cartList = formatCartList;
        }
        
        this.setData({ 
          isLogin: true, 
          cartList, 
          totalCashPrice: sumCash.toFixed(2), 
          totalPointPrice: sumPoints 
        });
      },
      fail: () => {
        this.setData({ cartList: [], totalCashPrice: '0.00', totalPointPrice: 0 });
        wx.showToast({ title: '网络错误', icon: 'none' });
      },
      complete: () => {
        this.setData({ loading: false });
        callback && callback();
      }
    });
  },

  // 🌟 3. 数量增减时：双轨实时重算
  changeNum(e) {
    const { id, type } = e.currentTarget.dataset;
    const num = type === 'plus' ? 1 : -1;
    const that = this;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    
    if (!accessToken) return;

    wx.request({
      url: `${app.globalData.baseUrl}/app01/cart/${id}/`,
      method: 'PUT',
      header: { 'content-type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
      data: { num: num },
      success: (res) => {
        if (res.data && res.data.code === 200) {
          let sumCash = 0;
          let sumPoints = 0;
          
          const cartList = that.data.cartList.map(item => {
            if (item.id === id) item.num = res.data.data.num;
            
            const currentNum = Number(item.num || 1);
            if (item.isPointGoods) {
              const itemTotal = item.pointPrice * currentNum;
              item.total_price = itemTotal.toString();
              sumPoints += itemTotal;
            } else {
              // 🌟 核心修改：数量变动时，也要取真实计算的单价
              const goodsPrice = that.getGoodsCashPrice(item.goods);
              const itemTotal = currentNum * goodsPrice;
              item.total_price = itemTotal.toFixed(2);
              sumCash += itemTotal;
            }
            return item;
          });
          
          that.setData({ 
            cartList, 
            totalCashPrice: sumCash.toFixed(2),
            totalPointPrice: sumPoints
          });
          wx.showToast({ title: type === 'plus' ? '数量+1' : '数量-1', icon: 'success', duration: 800 });
        }
      }
    });
  },

  // 🌟 4. 删除商品时：重新清洗资产池
  deleteCart(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) return;

    wx.showModal({
      title: '提示', content: '确定删除该商品吗？',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: `${app.globalData.baseUrl}/app01/cart/${id}/`, method: 'DELETE',
            header: { 'content-type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
            success: (res) => {
              if (res.data && res.data.code === 200) {
                let sumCash = 0;
                let sumPoints = 0;
                
                const cartList = that.data.cartList.filter(item => item.id !== id).map(item => {
                  const currentNum = Number(item.num || 1);
                  if (item.isPointGoods) {
                    sumPoints += item.pointPrice * currentNum;
                  } else {
                    // 🌟 核心修改：重新计算剩余商品的总价时，取真实计算的单价
                    const goodsPrice = that.getGoodsCashPrice(item.goods);
                    sumCash += currentNum * goodsPrice;
                  }
                  return item;
                });
                
                that.setData({ cartList, totalCashPrice: sumCash.toFixed(2), totalPointPrice: sumPoints });
                wx.showToast({ title: '删除成功', icon: 'success', duration: 800 });
              }
            }
          });
        }
      }
    });
  },

  toMall() { wx.switchTab({ url: '/pages/mall/mall' }); },

  toCheckout() {
    const accessToken = wx.getStorageSync('accessToken');
    if (!accessToken) { 
      wx.navigateTo({ url: '/pages/login/login' }); 
      return; 
    }
    
    const isAllPointGoods = this.data.totalPointPrice > 0 && parseFloat(this.data.totalCashPrice) === 0;
    wx.navigateTo({ 
      url: `/pages/checkout/checkout?fromCart=true&isAllPointGoods=${isAllPointGoods}` 
    });
  },

  goToLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
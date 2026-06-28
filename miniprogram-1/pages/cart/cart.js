import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    cartList: [],        // 购物车商品列表
    loading: true,       // 加载状态
    
    // ================= 🌟 核心拆分双资产池 =================
    totalCashPrice: '0.00',   // 纯现金商品总计（元）
    totalPointPrice: 0        // 纯积分商品总计（积分）
  },

  // 🌟 1. 严格对齐后端核心字段，精准识别积分商品
  isPointGoods(goods) {
    if (!goods) return false;
    const flag = goods.is_support_point_exchange;
    return String(flag) === '1' || String(flag).toLowerCase() === 'true' || flag === true;
  },

  // 计算积分价格
  calcPointPrice(memberPrice) {
    const memberPriceStr = (memberPrice || '0').toString().replace(/[^0-9.]/g, '');
    const memberPriceNum = parseFloat(memberPriceStr) || 0;
    return Math.floor(memberPriceNum * 100);
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
    this.getCartList();
  },

  onShow() {
    this.setData({ cartList: [], totalCashPrice: '0.00', totalPointPrice: 0 });
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
    const header = {
      'content-type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
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
          wx.showModal({
            title: '登录过期', content: '请重新登录', showCancel: false,
            success: () => wx.navigateTo({ url: '/pages/login/login' })
          });
          this.setData({ cartList: [], totalCashPrice: '0.00', totalPointPrice: 0 });
          return;
        }

        let cartList = [];
        let sumCash = 0;   // 现金池
        let sumPoints = 0; // 积分池
        
        if (res.data && res.data.code === 200) {
          cartList = res.data.data.cart_list || [];
          
          const formatCartList = cartList.map(item => {
            if (item.goods?.image_url) {
              item.goods.image_url = item.goods.image_url.replace('//media/', '/media/');
            }
            
            // 精准判定
            const isPointGoods = this.isPointGoods(item.goods);
            const goodsPrice = Number(item.goods?.member_price || 0);
            
            // 积分单价优先获取后端真实数据，没有则前端换算
            let pointPrice = 0;
            if (isPointGoods) {
              pointPrice = Number(item.goods?.point_price || 0);
              if (pointPrice <= 0) pointPrice = this.calcPointPrice(goodsPrice);
            }
            
            const num = Number(item.num || 1);
            let total_price = 0;
            
            if (isPointGoods) {
              total_price = pointPrice * num;
              sumPoints += total_price; // 归入积分池
            } else {
              total_price = goodsPrice * num;
              sumCash += total_price;   // 归入现金池
            }

            return {
              ...item,
              isPointGoods: isPointGoods,
              pointPrice: pointPrice,
              total_price: isPointGoods ? total_price.toString() : total_price.toFixed(2)
            };
          });
          cartList = formatCartList;
        }
        
        this.setData({ 
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
              const itemTotal = currentNum * Number(item.goods.member_price || 0);
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
                    sumCash += currentNum * Number(item.goods.member_price || 0);
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
    if (!accessToken) { wx.navigateTo({ url: '/pages/login/login' }); return; }
    
    // 计算是否全为积分商品传入结算页
    const isAllPointGoods = this.data.totalPointPrice > 0 && parseFloat(this.data.totalCashPrice) === 0;
    wx.navigateTo({ 
      url: `/pages/checkout/checkout?fromCart=true&isAllPointGoods=${isAllPointGoods}` 
    });
  }
});
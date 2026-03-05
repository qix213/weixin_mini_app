import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    cartList: [],    // 购物车商品列表
    totalAll: 0,     // 购物车总价/总积分
    loading: true,   // 加载状态
    isAllPointGoods: false // 是否全为积分商品（用于底部总计显示）
  },

  // 统一判断是否为积分商品（和列表页/详情页逻辑一致）
  isPointGoods(item) {
    const pointField = item.isPointGoods || item.can_point_exchange || item.canPointExchange || false;
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    
    let isPoint = false;
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true';
    } else if (typeof pointField === 'number') {
      isPoint = pointField === 1;
    } else {
      isPoint = !!pointField;
    }
    return isPoint || hasPointPrice;
  },

  // 计算积分价格（和列表页/详情页逻辑一致）
  calcPointPrice(memberPrice) {
    const memberPriceStr = (memberPrice || '0').toString().replace(/[^0-9.]/g, '');
    const memberPriceNum = parseFloat(memberPriceStr) || 0;
    const pointPrice = Math.floor(memberPriceNum * 100);
    return Number(pointPrice);
  },

  // 页面加载时获取购物车数据（优化：接收订单ID，精准清空）
  onLoad(options) {
    // 如果从支付页返回且支付成功
    if (options.paid === 'true') {
      const orderId = options.orderId || ''; // 接收支付页传递的订单ID
      this.resetCartData(); // 强制清空本地数据
      // 核心新增：调用后端清空购物车接口（精准/全清）
      this.clearPaidCart(orderId).then(() => {
        this.getCartList(); // 清空后重新拉取最新数据
      });
      return;
    }
    this.getCartList();
  },

  // 回到页面时刷新购物车（核心修改：先重置再请求）
  onShow() {
    // 关键：每次返回购物车先清空旧数据，避免残留
    this.setData({ cartList: [], totalAll: '0.00', isAllPointGoods: false });
    this.getCartList();
  },

  // 新增：清空已支付的购物车商品（对接后端接口）
  clearPaidCart(orderId = '') {
    return new Promise((resolve) => {
      const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      if (!accessToken) {
        resolve();
        return;
      }

      // 构建请求参数：有订单ID则精准清空，无则全清（根据后端接口调整）
      const clearUrl = orderId 
        ? `http://localhost:8000/app01/cart/clear/${orderId}/` // 精准清空订单对应商品
        : `http://localhost:8000/app01/cart/clear/`; // 全清购物车

      wx.request({
        url: clearUrl,
        method: 'POST',
        header: {
          'content-type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        success: (res) => {
          if (res.data && res.data.code === 200) {
            Toast.success('购物车已清空');
          }
        },
        fail: (err) => {
          console.error('清空购物车失败：', err);
          Toast.fail('清空购物车失败');
        },
        complete: () => {
          resolve();
        }
      });
    });
  },

  // 新增：强制重置购物车数据（支付后专用）
  resetCartData() {
    this.setData({
      cartList: [],
      totalAll: '0.00',
      isAllPointGoods: false,
      loading: true
    });
    // 清除本地购物车缓存（如果有）
    wx.removeStorageSync('cartList');
  },

  // 下拉刷新时重新获取数据
  onPullDownRefresh() {
    this.resetCartData(); // 刷新前先重置
    this.getCartList(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 1. 获取购物车列表（核心优化：适配积分商品+总价计算）
  getCartList(callback) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    const header = {
      'content-type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
    };

    this.setData({ loading: true });

    wx.request({
      url: 'http://localhost:8000/app01/cart/', 
      method: 'GET',
      header: header,
      success: (res) => {
        if (res.statusCode === 401 || (res.data && res.data.detail === "身份认证信息未提供")) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          app.globalData.isLogin = false;
          wx.showModal({
            title: '登录过期',
            content: '您的登录已过期，请重新登录',
            showCancel: false,
            success: () => {
              wx.navigateTo({ url: '/pages/login/login' });
            }
          });
          // 401时强制清零
          this.setData({ cartList: [], totalAll: '0.00', isAllPointGoods: false });
          return;
        }

        // 正常解析数据
        let cartList = [];
        let totalAll = '0.00'; // 初始化为0.00，避免残留
        let isAllPointGoods = true; // 默认全为积分商品，后续校验
        
        if (res.data && res.data.code === 200) {
          cartList = res.data.data.cart_list || [];
          // 格式化数据：适配积分商品
          const formatCartList = cartList.map(item => {
            // 处理商品图片URL
            if (item.goods?.image_url) {
              item.goods.image_url = item.goods.image_url.replace('//media/', '/media/');
            }
            
            // 判断是否为积分商品
            const isPointGoods = this.isPointGoods(item.goods);
            // 计算积分价格
            const pointPrice = isPointGoods ? this.calcPointPrice(item.goods.member_price) : 0;
            // 计算小计：积分商品=积分单价*数量，普通商品=金额单价*数量
            const total_price = isPointGoods 
              ? (pointPrice * item.num).toString() // 积分无小数
              : Number(item.total_price || 0).toFixed(2); // 金额保留2位小数
            
            // 只要有一个不是积分商品，就标记为非全积分
            if (!isPointGoods) {
              isAllPointGoods = false;
            }

            return {
              ...item,
              isPointGoods: isPointGoods, // 标记是否为积分商品
              pointPrice: pointPrice, // 积分单价
              total_price: total_price // 适配后的小计
            };
          });
          cartList = formatCartList;

          // 核心优化：计算总价/总积分
          totalAll = cartList.length > 0 
            ? cartList.reduce((sum, item) => {
                return sum + Number(item.total_price);
              }, 0) 
            : 0;
          
          // 格式化：积分无小数，金额保留2位
          totalAll = isAllPointGoods 
            ? totalAll.toString() 
            : totalAll.toFixed(2);
        }
        
        // 无论是否有数据，都强制更新
        this.setData({ cartList, totalAll, isAllPointGoods });
      },
      fail: (err) => {
        console.error('购物车请求失败：', err);
        // 失败时强制清零
        this.setData({ cartList: [], totalAll: '0.00', isAllPointGoods: false });
        wx.showToast({ title: '网络错误，无法获取购物车', icon: 'none' });
      },
      complete: () => {
        this.setData({ loading: false });
        callback && callback();
      }
    });
  },

  // 2. 增减商品数量（适配积分商品）
  changeNum(e) {
    const { id, type } = e.currentTarget.dataset;
    const num = type === 'plus' ? 1 : -1;
    const that = this;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    const requestUrl = `http://localhost:8000/app01/cart/${id}/`;
    wx.request({
      url: requestUrl,
      method: 'PUT',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      data: { num: num },
      success: (res) => {
        if (res.statusCode === 401) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          wx.showToast({ title: '登录过期，请重新登录', icon: 'none' });
          setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 1500);
          return;
        }

        if (res.data && res.data.code === 200) {
          const cartList = that.data.cartList.map(item => {
            if (item.id === id) {
              item.num = res.data.data.num;
              // 适配：积分商品/普通商品计算小计
              item.total_price = item.isPointGoods 
                ? (item.pointPrice * item.num).toString() // 积分无小数
                : (item.num * Number(item.goods.member_price)).toFixed(2); // 金额保留2位
            }
            return item;
          });
          
          // 重新计算总价/总积分
          let totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0);
          // 格式化总价
          totalAll = that.data.isAllPointGoods 
            ? totalAll.toString() 
            : totalAll.toFixed(2);
          
          that.setData({ cartList, totalAll });
          wx.showToast({ title: type === 'plus' ? '数量+1' : '数量-1', icon: 'success', duration:800 });
        } else {
          wx.showToast({ title: res.data?.msg || '修改数量失败', icon: 'none' });
        }
      },
      fail: (err) => {
        console.error('修改数量请求失败：', err);
        wx.showToast({ title: '修改失败，请检查网络', icon: 'none' });
      }
    });
  },

  // 3. 删除购物车商品（适配积分商品总价）
  deleteCart(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showModal({
      title: '提示',
      content: '确定删除该商品吗？',
      success: (res) => {
        if (res.confirm) {
          const requestUrl = `http://localhost:8000/app01/cart/${id}/`;
          wx.request({
            url: requestUrl,
            method: 'DELETE',
            header: {
              'content-type': 'application/json',
              'Authorization': `Bearer ${accessToken}`
            },
            success: (res) => {
              if (res.statusCode === 401) {
                wx.removeStorageSync('accessToken');
                app.globalData.accessToken = '';
                wx.showToast({ title: '登录过期，请重新登录', icon: 'none' });
                setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 1500);
                return;
              }

              if (res.data && res.data.code === 200) {
                const cartList = that.data.cartList.filter(item => item.id !== id);
                // 重新校验是否全为积分商品
                const isAllPointGoods = cartList.every(item => item.isPointGoods);
                // 重新计算总价/总积分
                let totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0);
                // 格式化总价
                totalAll = isAllPointGoods 
                  ? totalAll.toString() 
                  : totalAll.toFixed(2);
                
                that.setData({ cartList, totalAll, isAllPointGoods });
                wx.showToast({ title: '删除成功', icon: 'success', duration:800 });
              } else {
                wx.showToast({ title: res.data?.msg || '删除失败', icon: 'none' });
              }
            },
            fail: (err) => {
              console.error('删除商品请求失败：', err);
              wx.showToast({ title: '删除失败，请检查网络', icon: 'none' });
            }
          });
        }
      }
    });
  },

  // 4. 跳转到商城页面（无修改）
  toMall() {
    wx.switchTab({ url: '/pages/mall/mall' });
  },

  // 5. 跳转到结算页面（新增：传递页面标识+积分标识）
  toCheckout() {
    const accessToken = wx.getStorageSync('accessToken');
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    // 跳转时携带购物车页面标识+积分标识，便于结算页适配
    wx.navigateTo({ 
      url: `/pages/checkout/checkout?fromCart=true&isAllPointGoods=${this.data.isAllPointGoods}` 
    });
  }
});
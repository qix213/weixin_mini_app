import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    cartList: [],    // 购物车商品列表
    totalAll: 0,     // 购物车总价
    loading: true    // 加载状态
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
    this.setData({ cartList: [], totalAll: '0.00' });
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
          // console.log('清空购物车结果：', res.data);
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

  // 1. 获取购物车列表（核心优化：总价计算+空数据处理）
  getCartList(callback) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    const header = {
      'content-type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
    };

    console.log("===== 购物车请求调试信息 =====");
    // console.log("当前accessToken：", accessToken ? "存在" : "为空");
    // console.log("购物车列表请求头：", header);
    // console.log("请求URL：", 'http://localhost:8000/app01/cart/');

    this.setData({ loading: true });

    wx.request({
      url: 'http://localhost:8000/app01/cart/', 
      method: 'GET',
      header: header,
      success: (res) => {
        // console.log('购物车接口返回：', res);
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
          this.setData({ cartList: [], totalAll: '0.00' });
          return;
        }

        // 正常解析数据
        let cartList = [];
        let totalAll = '0.00'; // 初始化为0.00，避免残留
        if (res.data && res.data.code === 200) {
          cartList = res.data.data.cart_list || [];
          // console.log('解析后的购物车商品数：', cartList.length);
          // 格式化数据
          const formatCartList = cartList.map(item => {
            if (item.goods?.image_url) {
              item.goods.image_url = item.goods.image_url.replace('//media/', '/media/');
            }
            item.total_price = Number(item.total_price || 0).toFixed(2);
            return item;
          });
          cartList = formatCartList;
          // 核心优化：购物车为空时总价直接为0.00
          totalAll = cartList.length > 0 
            ? cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2)
            : '0.00';
        }
        // 无论是否有数据，都强制更新（关键！）
        this.setData({ cartList, totalAll });
      },
      fail: (err) => {
        console.error('购物车请求失败：', err);
        // 失败时强制清零
        this.setData({ cartList: [], totalAll: '0.00' });
        wx.showToast({ title: '网络错误，无法获取购物车', icon: 'none' });
      },
      complete: () => {
        // console.log('购物车请求完成');
        this.setData({ loading: false });
        callback && callback();
      }
    });
  },

  // 2. 增减商品数量（无修改，保留原有逻辑）
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
              item.total_price = (item.num * Number(item.goods.member_price)).toFixed(2);
            }
            return item;
          });
          // 重新计算总价（避免残留）
          const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2);
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

  // 3. 删除购物车商品（无修改，保留原有逻辑）
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
                // 重新计算总价（避免残留）
                const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2);
                that.setData({ cartList, totalAll });
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

  // 5. 跳转到结算页面（新增：传递页面标识）
  toCheckout() {
    const accessToken = wx.getStorageSync('accessToken');
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    // 跳转时携带购物车页面标识，便于结算页返回时识别
    wx.navigateTo({ 
      url: '/pages/checkout/checkout?fromCart=true' 
    });
  }
});
const app = getApp();

Page({
  data: {
    cartList: [],         // 结算商品列表
    totalAll: '0.00',     // 总价（统一为字符串，避免类型不一致）
    defaultAddress: null, // 默认收货地址
    loading: true         // 加载状态
  },

  // 页面加载时获取购物车+收货地址
  onLoad(options) {
    // 接收支付页返回的状态（如支付失败）
    this.setData({ fromPay: options.fromPay || false });
    this.getCheckoutData();
  },

  // 下拉刷新重新获取数据
  onPullDownRefresh() {
    this.getCheckoutData().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 回到结算页刷新数据（优化：避免频繁请求）
  onShow() {
    // 仅当页面从后台返回/支付页返回时刷新
    if (this.data.fromPay || !this.data.cartList.length) {
      this.getCheckoutData();
      this.setData({ fromPay: false }); // 重置状态
    }
  },

  // 统一获取：购物车+收货地址（重构为Promise版，解决加载状态异常）
  getCheckoutData() {
    return new Promise((resolve) => {
      this.setData({ loading: true });
      
      // 核心修复1：统一获取accessToken（替换token）
      const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      app.globalData.accessToken = accessToken; // 同步到全局

      // 登录校验
      if (!accessToken) {
        wx.showModal({
          title: '提示',
          content: '请先登录再结算',
          showCancel: false,
          success: () => {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        });
        this.setData({ loading: false });
        resolve();
        return;
      }

      // 并行请求：购物车 + 收货地址
      Promise.all([
        this.getCartList(), // 购物车数据
        this.getAddressList() // 收货地址
      ]).then(() => {
        resolve();
      }).catch((err) => {
        console.error('结算数据加载失败：', err);
        wx.showToast({ title: '数据加载失败', icon: 'none' });
        resolve();
      }).finally(() => {
        this.setData({ loading: false });
      });
    });
  },

  // 获取购物车结算商品（修复401+数据解析+格式统一）
  getCartList() {
    return new Promise((resolve) => {
      app.request({
        url: '/app01/cart/',
        method: 'GET'
      }).then(res => {
        console.log('结算页购物车数据：', res.data);
        
        // 核心修复2：处理401错误
        if (res.statusCode === 401 || (res.data && res.data.detail === "身份认证信息未提供")) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          wx.showModal({
            title: '登录过期',
            content: '您的登录已过期，请重新登录',
            showCancel: false,
            success: () => {
              wx.navigateTo({ url: '/pages/login/login' });
            }
          });
          this.setData({ cartList: [], totalAll: '0.00' });
          resolve();
          return;
        }

        // 严谨解析数据（多层空值保护）
        let cartList = res.data?.data?.cart_list || [];
        cartList = Array.isArray(cartList) ? cartList : [];
        
        // 格式化商品数据（价格统一为字符串）
        cartList = cartList.map(item => {
          item.total_price = Number(item.total_price || 0).toFixed(2);
          item.goods = item.goods || {}; // 空值保护
          return item;
        });

        // 计算总价（空购物车强制为0.00）
        const totalAll = cartList.length > 0 
          ? cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2)
          : '0.00';
        
        this.setData({ cartList, totalAll });
        resolve();
      }).catch(err => {
        console.error('结算页获取购物车失败：', err);
        this.setData({ cartList: [], totalAll: '0.00' });
        resolve();
      });
    });
  },

  // 获取收货地址（修复401+空值保护+默认地址逻辑）
  getAddressList() {
    return new Promise((resolve) => {
      app.request({
        url: '/app01/address/',
        method: 'GET'
      }).then(res => {
        console.log('结算页地址数据：', res.data);
        
        // 处理401错误
        if (res.statusCode === 401) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          resolve();
          return;
        }

        // 严谨解析地址列表
        let addressList = res.data?.data?.address_list || [];
        addressList = Array.isArray(addressList) ? addressList : [];
        
        // 优先选择默认地址，无默认则选第一个
        let defaultAddress = null;
        if (addressList.length > 0) {
          defaultAddress = addressList.find(item => item.is_default) || addressList[0];
        }
        
        this.setData({ defaultAddress });
        resolve();
      }).catch(err => {
        console.error('结算页获取地址失败：', err);
        this.setData({ defaultAddress: null });
        resolve();
      });
    });
  },

  // 跳转收货地址页面（新增：返回后刷新数据）
  toAddressPage() {
    wx.navigateTo({ 
      url: '/pages/address/address',
      // 地址页返回后刷新结算页数据
      events: {
        addressUpdated: () => {
          this.getAddressList(); // 仅刷新地址
        }
      }
    });
  },

  // 返回购物车页面（优化：用redirectTo避免页面层级过深）
  toCart() {
    wx.redirectTo({ url: '/pages/cart/cart' });
  },

  // 核心：提交订单（修复401+参数校验+支付联动）
  submitOrder() {
    const { defaultAddress, cartList, totalAll } = this.data;
    
    // 1. 基础校验（优化提示）
    if (!defaultAddress) {
      wx.showModal({
        title: '提示',
        content: '请先添加/选择收货地址',
        confirmText: '去添加',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) this.toAddressPage();
        }
      });
      return;
    }
    if (cartList.length === 0) {
      return wx.showToast({ title: '暂无可结算的商品', icon: 'none' });
    }
    if (Number(totalAll) <= 0) {
      return wx.showToast({ title: '订单金额异常，请重新加载', icon: 'none' });
    }

    // 2. 构建订单数据（适配后端格式）
    const orderData = {
      address_id: defaultAddress.id,
      total_price: Number(totalAll), // 后端可能需要数字类型
      goods_list: cartList.map(item => ({
        cart_id: item.id,
        goods_id: item.goods?.id || '', // 补充商品ID，适配后端
        num: Number(item.num) || 1
      }))
    };

    wx.showLoading({ title: '正在下单...', mask: true });

    // 3. 提交订单接口
    app.request({
      url: '/app01/order/add/',
      method: 'POST',
      data: orderData
    }).then(res => {
      console.log('下单结果：', res.data);
      const result = res.data || {};

      // 处理401
      if (res.statusCode === 401) {
        wx.removeStorageSync('accessToken');
        app.globalData.accessToken = '';
        wx.showToast({ title: '登录过期，请重新登录', icon: 'none' });
        setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 1500);
        return;
      }

      // 下单成功
      if (result.code === 200 || result.code === '200') {
        // 记录订单ID（用于支付页）
        const orderId = result.data?.order_id || '';
        wx.showToast({ title: '下单成功！即将跳转到支付页面', icon: 'success', duration: 2000 });
        
        // 跳转到支付页（携带订单ID+总价，便于支付后联动）
        setTimeout(() => {
          wx.navigateTo({
            url: `/pages/pay/pay?scene=order&typeName=${encodeURIComponent('商品订单支付')}&totalAll=${totalAll}&orderId=${orderId}`
          });
        }, 2000);
      } else {
        wx.showToast({ title: result.msg || '下单失败，请重试', icon: 'none' });
      }
    }).catch(err => {
      console.error('下单失败：', err);
      wx.showToast({ title: '网络异常，下单失败', icon: 'none' });
    }).finally(() => {
      wx.hideLoading();
    });
  }
});
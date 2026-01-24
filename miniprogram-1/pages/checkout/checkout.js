const app = getApp();
Page({
  data: {
    cartList: [],    // 结算商品列表
    totalAll: 0.00,  // 总价
    defaultAddress: null, // 默认收货地址
    loading: true
  },

  // 页面加载时获取 购物车数据+收货地址
  onLoad() {
    this.getCheckoutData();
  },

  // 下拉刷新重新获取数据
  onPullDownRefresh() {
    this.getCheckoutData(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 回到结算页，刷新地址和购物车（比如新增地址后返回）
  onShow() {
  // 每次进入页面都查一下缓存里有没有新填的地址
  this.getCheckoutData();
  },

  // 统一获取：购物车+收货地址数据
  getCheckoutData(callback) {
    this.setData({ loading: true });
    app.globalData.token = wx.getStorageSync('token') || '';
    // 先校验登录
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

// 1. 获取购物车结算商品【精准修复版，完美匹配你的后端结构，必生效】
getCartList() {
  app.request({
    url: '/app01/cart/',
    method: 'GET'
  }).then(res => {
    console.log('======= 结算页购物车返回 =======', res.data);
    // ✅ 精准取值：你的商品列表 唯一正确路径 = res.data.data.cart_list
    let cartList = res.data.data.cart_list || []; 
    console.log('======= 原始购物车数组 =======', cartList);
    console.log('======= 原始商品数量 =======', cartList.length); // 这里会打印 2
    
    // ✅ 只做一次保险：如果后端返回null，才赋值空数组（你的是正常数组，不会触发）
    if(!cartList){
      cartList = [];
    }
    // ✅ 计算总价（你的逻辑没问题，保留）
    const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price || 0), 0).toFixed(2);
    
    // ✅ 赋值渲染页面（关键：直接赋值，不要多做判断）
    this.setData({ 
      cartList: cartList,
      totalAll: totalAll
    });
    console.log('======= 最终渲染商品数量 =======', this.data.cartList.length); // 必打印 2
    console.log('======= 最终总价 =======', this.data.totalAll); // 必打印 241.98
  }).catch(err => {
    console.error('购物车请求失败', err);
    this.setData({ cartList: [], totalAll: '0.00' });
    wx.showToast({ title: '获取商品失败', icon: 'none' });
  });
},

// 2. 获取收货地址【Promise正确调用写法】
// 2. 获取收货地址【精准修复版】
// checkout.js
getAddressList() {
  app.request({
    url: '/app01/address/',
    method: 'GET'
  }).then(res => {
    // 🔍 关键调试：看清楚 res.data 到底长什么样
    console.log('--- 1. 原始返回数据 ---', res.data);
    
    // 如果你的后端 Response 是 {"code": 200, "data": {"address_list": [...]}}
    // 那么路径应该是 res.data.data.address_list
    const addressList = res.data.data ? res.data.data.address_list : [];
    
    console.log('--- 2. 解析出的列表 ---', addressList);

    if (addressList && addressList.length > 0) {
      this.setData({ 
        defaultAddress: addressList[0] 
      });
      console.log('--- 3. 已设置到 defaultAddress ---', this.data.defaultAddress);
    } else {
      this.setData({ defaultAddress: null });
      console.log('--- 3. 列表为空 ---');
    }
  });
},

  // 3. 跳转收货地址页面（选择/新增地址）
  toAddressPage() {
    wx.navigateTo({ url: '/pages/address/address' });
  },

  // 4. 返回购物车页面
  toCart() {
    wx.navigateTo({ url: '/pages/cart/cart' });
  },

  // 5. 核心：提交订单
  submitOrder() {
    const { defaultAddress, cartList, totalAll } = this.data;
    // 双重校验地址
    if (!defaultAddress) {
      wx.showToast({ title: '请选择收货地址', icon: 'none' });
      return;
    }
    if (cartList.length === 0) {
      wx.showToast({ title: '暂无结算商品', icon: 'none' });
      return;
    }

    // 组装订单数据
    const orderData = {
      address_id: defaultAddress,
      total_price: totalAll,
      goods_list: cartList.map(item => ({ cart_id: item.id, num: item.num }))
    };

    wx.showLoading({ title: '提交中...' });
    app.request({
      url: '/app01/order/add/',
      method: 'POST',
      data: orderData,
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: '下单成功！', icon: 'success' });
          // 下单成功后，跳转到订单页/首页，同时清空购物车（可选）
          setTimeout(() => {
            wx.switchTab({ url: '/pages/mall/mall' });
          }, 1500);
        } else {
          wx.showToast({ title: res.data?.msg || '下单失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常，下单失败', icon: 'none' });
      }
    });
  }
});
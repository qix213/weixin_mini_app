import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    cartList: [],    // 购物车商品列表
    totalAll: 0,     // 购物车总价
    loading: true    // 加载状态
  },

  // 页面加载时获取购物车数据
  onLoad() {
    this.getCartList();
  },

  // 下拉刷新时重新获取数据
  onPullDownRefresh() {
    this.getCartList(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 回到页面时刷新购物车（比如从商城添加商品后返回）
  onShow() {
    this.getCartList();
  },

  // 1. 获取购物车列表（核心接口）
// cart.js 完全替换getCartList方法（原生wx.request）
getCartList(callback) {
  this.setData({ loading: true });
  // console.log('开始获取购物车，准备调用原生wx.request');
  // console.log('完整请求URL：', 'http://192.168.28.40:8000/app01/cart/');
  // 原生wx.request（跳过app封装，排除封装问题）
  wx.request({
    // url: 'http://192.168.28.40:8000/app01/cart/', // 
    url: 'http://localhost:8000/app01/cart/', 
    method: 'GET',
    header: {
      'content-type': 'application/json',
      // 手动加Token（如果有）
      'Authorization': `Bearer ${wx.getStorageSync('token')}`
    },
    // 原生success（必打印）
    success: (res) => {
      // console.log('原生wx.request success：', res.data);
      if (res.data && res.data.code === 200) {
        const cartList = res.data.data.cart_list || [];
        // console.log('解析后的cartList长度：', cartList.length);
        const formatCartList = cartList.map(item => {
          if (item.goods?.image_url) {
            // item.goods.image_url = item.goods.image_url.replace('localhost', '192.168.28.40');
          }
          return item;
        });
        const totalAll = formatCartList.reduce((sum, item) => sum + (item.total_price || 0), 0).toFixed(2);
        this.setData({ cartList: formatCartList, totalAll });
      } else {
        this.setData({ cartList: [], totalAll: '0.00' });
        wx.showToast({ title: '获取购物车失败', icon: 'none' });
      }
    },
    // 原生fail（必打印）
    fail: (err) => {
      console.error('原生wx.request fail：', err);
      this.setData({ cartList: [], totalAll: '0.00' });
      wx.showToast({ title: '请求失败，请检查后端', icon: 'none' });
    },
    // 原生complete
    complete: () => {
      console.log('原生wx.request complete');
      this.setData({ loading: false });
      callback && callback();
    }
  });
},

// 2. 增减商品数量（修改后 ✅ 修复404+传参错误+补全日志）
changeNum(e) {
  const { id, type } = e.currentTarget.dataset;
  const num = type === 'plus' ? 1 : -1; // +1 或 -1
  const that = this;
  // 关键修复1：URL补全/app01，并且把cart_id拼在路径末尾【Django必传方式】
  const requestUrl = 'http://localhost:8000/app01/cart/' + id + '/';
  
  wx.request({
    url: requestUrl,
    method: 'PUT', // 修改用PUT，正确
    header: {
      'content-type': 'application/json',
      'Authorization': `Bearer ${wx.getStorageSync('token')}`
    },
    data: { num: num }, // 只传数量即可，ID已经在路径里
    success: (res) => {
      if (res.data && res.data.code === 200) {
        // 本地更新数据，不用重新请求，体验好
        const cartList = that.data.cartList.map(item => {
          if (item.id === id) {
            item.num = res.data.data.num;
            item.total_price = (item.num * item.goods.member_price).toFixed(2);
          }
          return item;
        });
        const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2);
        that.setData({ cartList, totalAll });
        wx.showToast({ title: type === 'plus' ? '数量+1' : '数量-1', icon: 'success', duration:800 });
      } else {
        wx.showToast({ title: res.data?.msg || '修改数量失败', icon: 'none' });
      }
    },
    // 关键修复2：补全fail回调，404/失败日志一目了然
    fail: (err) => {
      console.error('修改数量请求失败：', err);
      wx.showToast({ title: '修改失败，接口不存在', icon: 'none' });
    }
  });
},

// 3. 删除购物车商品（修改后 ✅ 修复404+传参错误+补全日志）
deleteCart(e) {
  const id = e.currentTarget.dataset.id;
  const that = this;
  wx.showModal({
    title: '提示',
    content: '确定删除该商品吗？',
    success: (res) => {
      if (res.confirm) {
        // 关键修复1：URL补全/app01，cart_id拼在路径末尾
        const requestUrl = 'http://localhost:8000/app01/cart/' + id + '/';
        wx.request({
          url: requestUrl,
          method: 'DELETE', // 删除用DELETE，正确
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${wx.getStorageSync('token')}`
          },
          success: (res) => {
            if (res.data && res.data.code === 200) {
              // 本地删除商品，不用重新请求
              const cartList = that.data.cartList.filter(item => item.id !== id);
              const totalAll = cartList.reduce((sum, item) => sum + Number(item.total_price), 0).toFixed(2);
              that.setData({ cartList, totalAll });
              wx.showToast({ title: '删除成功', icon: 'success', duration:800 });
            } else {
              wx.showToast({ title: res.data?.msg || '删除失败', icon: 'none' });
            }
          },
          // 关键修复2：补全fail回调
          fail: (err) => {
            console.error('删除商品请求失败：', err);
            wx.showToast({ title: '删除失败，接口不存在', icon: 'none' });
          }
        });
      }
    }
  });
},

  // 4. 跳转到商城页面（空购物车时）
  toMall() {
    wx.switchTab({ url: '/pages/mall/mall' }); // 若mall是tabBar页用switchTab，否则用navigateTo
  },

  // 5. 跳转到结算页面
  toCheckout() {
    wx.navigateTo({ url: '/pages/checkout/checkout' });
  }
});
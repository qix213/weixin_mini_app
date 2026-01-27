const app = getApp();

Page({
  data: {
    orderList: [], // 订单列表数据
    loading: false, // 加载状态
    hasMore: true, // 是否有更多数据
    page: 1, // 当前页码
    pageSize: 10, // 每页条数
    isLogin: false, // 登录状态
    token: '' // 当前有效的 Token
  },

  onShow() {
    console.log('1. 页面 onShow 触发');
    // 同步全局登录状态和 Token
    this.syncGlobalState();
    // 触发订单数据请求
    this.fetchOrders(true); // true 表示刷新数据（重置页码）
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.fetchOrders(true).finally(() => {
      wx.stopPullDownRefresh(); // 停止下拉刷新
    });
  },

  // 上拉加载更多
  onReachBottom() {
    if (!this.data.hasMore || this.data.loading) return;
    this.fetchOrders(false); // false 表示加载更多
  },

  // ========== 核心优化：同步全局状态 + Token 校验 ==========
  // 同步全局登录状态和 Token
  syncGlobalState() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    this.setData({
      isLogin: app.globalData.isLogin || !!token,
      token: token
    });
    console.log('同步全局状态：', {
      isLogin: this.data.isLogin,
      token: token ? '已获取Token' : '无Token'
    });
  },

  // 登录引导（统一方法）
  guideToLogin() {
    wx.showModal({
      title: '提示',
      content: '查看订单记录需要先登录账号',
      confirmText: '去登录',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          // 跳转登录页，携带回跳参数（登录后返回订单列表）
          wx.navigateTo({
            url: `/pages/login/login?redirect=${encodeURIComponent('/pages/order-list/order-list')}`
          });
        }
      }
    });
  },

  // ========== 核心：请求订单列表数据 ==========
  /**
   * 获取订单列表
   * @param {Boolean} isRefresh - 是否刷新（重置页码）
   */
  fetchOrders(isRefresh = false) {
    console.log('2. 进入 fetchOrders 函数');
    // 1. 重置页码（刷新场景）
    if (isRefresh) {
      this.setData({
        page: 1,
        hasMore: true,
        orderList: []
      });
    }

    // 2. Token 校验
    if (!this.data.token) {
      console.log('3. 诊断：因为没有 Token，流程被拦截了');
      // 隐藏加载状态（如果有）
      this.setData({ loading: false });
      // 友好引导登录（而非仅控制台日志）
      this.guideToLogin();
      return Promise.reject('无Token，拦截请求');
    }

    // 3. 已登录，发起请求
    if (this.data.loading) return Promise.resolve();
    this.setData({ loading: true });

    const { page, pageSize } = this.data;
    const url = `${app.globalData.baseUrl}/app01/order/list/`; // 替换为实际订单接口

    return new Promise((resolve, reject) => {
      wx.request({
        url: url,
        method: 'GET',
        header: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.data.token}`
        },
        data: {
          page: page,
          page_size: pageSize
        },
        success: (res) => {
          console.log('4. 订单接口响应：', res.data);
          // 处理接口响应
          if (res.statusCode === 200) {
            const resData = res.data;
            const newOrders = resData.data || [];
            const total = resData.total || 0;
          
            // ========== 新增：预处理商品数组 ==========
            const processedOrders = newOrders.map(order => {
              // 拆分商品名称为数组，兼容英文/中文逗号
              let goodsList = [];
              if (order.goods_names && typeof order.goods_names === 'string') {
                // 先按中文顿号拆分，再按英文逗号兜底（兼容后端可能的分隔符错误）
                goodsList = order.goods_names.split('、').length > 1 
                  ? order.goods_names.split('、') 
                  : order.goods_names.split(',');
              }
              return {
                ...order,
                goodsList: goodsList // 新增goodsList字段，存拆分后的商品数组
              };
            });
            // ========== 预处理结束 ==========
          
            // 拼接/重置订单列表（用预处理后的processedOrders）
            const finalOrders = isRefresh ? processedOrders : [...this.data.orderList, ...processedOrders];
            const hasMore = finalOrders.length < total;
          
            this.setData({
              orderList: finalOrders,
              hasMore: hasMore,
              page: page + 1
            }, () => {
              // 新增日志：打印预处理后的商品数组
              if (finalOrders.length > 0) {
                console.log('✅ 预处理后的goodsList：', finalOrders[0].goodsList);
                console.log('✅ goodsList长度：', finalOrders[0].goodsList.length);
              }
            });
          
            if (finalOrders.length === 0) {
              wx.showToast({ title: '暂无订单记录', icon: 'none' });
            }
            resolve(resData);
          }
          // 处理 Token 过期/无效
          else if (res.statusCode === 401) {
            console.log('5. Token 过期/无效，清除并引导登录');
            // 清除无效 Token
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            app.globalData.isLogin = false;
            this.setData({ token: '', isLogin: false });
            // 提示并引导登录
            wx.showToast({ title: '登录状态失效，请重新登录', icon: 'none' });
            setTimeout(() => {
              this.guideToLogin();
            }, 1500);
            reject('Token 无效');
          } 
          // 其他错误
          else {
            wx.showToast({ title: res.data.msg || '获取订单失败', icon: 'none' });
            reject(res.data);
          }
        },
        fail: (err) => {
          console.error('6. 订单请求失败：', err);
          wx.showToast({ title: '网络异常，无法获取订单', icon: 'none' });
          reject(err);
        },
        complete: () => {
          this.setData({ loading: false });
        }
      });
    });
  },

  // ========== 辅助方法：跳转订单详情 ==========
  goToOrderDetail(e) {
    const orderId = e.currentTarget.dataset.orderid;
    if (!orderId) return;

    // 登录校验（防止 Token 过期后点击）
    if (!this.data.token) {
      this.guideToLogin();
      return;
    }

    wx.navigateTo({
      url: `/pages/order-detail/order-detail?orderId=${orderId}`
    });
  },

  // ========== 辅助方法：刷新订单列表 ==========
  refreshOrderList() {
    this.fetchOrders(true);
  }
});
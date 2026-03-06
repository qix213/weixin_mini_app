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
          wx.navigateTo({
            url: `/pages/login/login?redirect=${encodeURIComponent('/pages/order-list/order-list')}`
          });
        }
      }
    });
  },

  // ========== 新增：复用 checkout 页面的积分商品判断逻辑 ==========
  isPointGoods(item) {
    const app = getApp();
    const goodsId = item.goods_id || item.id || '';
    // 优先从缓存获取积分商品标记（和 checkout 逻辑一致）
    const cacheIsPoint = app.getGoodsPointCache ? app.getGoodsPointCache(goodsId) : undefined;
    // 强制判定：价格>0 视为积分商品（和 checkout 逻辑一致）
    const isForcePointGoods = item.price > 0 || item.goods_price > 0; 
    
    if (cacheIsPoint !== undefined) {
      return cacheIsPoint || isForcePointGoods;
    }

    // 核心判断字段（和 checkout 逻辑完全一致）
    const pointField = item.can_point_exchange || item.is_point_goods || item.is_exchange || item.exchangeable || false;
    // 有积分价格且>0 视为积分商品
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    
    let isPoint = false;
    // 兼容不同类型的 pointField 值
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true' || pointField === '1';
    } else if (typeof pointField === 'number') {
      isPoint = pointField === 1;
    } else {
      isPoint = !!pointField;
    }
    // 最终判断：任意条件满足即为积分商品
    return isPoint || hasPointPrice || isForcePointGoods;
  },

  // ========== 核心：请求订单列表数据 ==========
  fetchOrders(isRefresh = false) {
    console.log('2. 进入 fetchOrders 函数');
    if (isRefresh) {
      this.setData({
        page: 1,
        hasMore: true,
        orderList: []
      });
    }

    if (!this.data.token) {
      console.log('3. 诊断：因为没有 Token，流程被拦截了');
      this.setData({ loading: false });
      this.guideToLogin();
      return Promise.reject('无Token，拦截请求');
    }

    if (this.data.loading) return Promise.resolve();
    this.setData({ loading: true });

    const { page, pageSize } = this.data;
    const url = `${app.globalData.baseUrl}/app01/order/list/`;

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
          if (res.data.data && res.data.data.length > 0) {
            console.log('📌 原始订单数据结构：', res.data.data[0]);
          }
          if (res.statusCode === 200) {
            const resData = res.data;
            const newOrders = resData.data || [];
            const total = resData.total || 0;
          
            // ========== 核心修改：基于 checkout 逻辑判断积分商品 ==========
            const processedOrders = newOrders.map(order => {
              // 拆分商品名称（原有逻辑保留）
              let goodsList = [];
              if (order.goods_names && typeof order.goods_names === 'string') {
                goodsList = order.goods_names.split('、').length > 1 
                  ? order.goods_names.split('、') 
                  : order.goods_names.split(',');
              }

              // 1. 调用 isPointGoods 判断是否为积分商品（兼容订单级字段）
              // 订单数据中可能直接包含积分相关字段，或从 goods 信息判断
              const orderItem = {
                // 映射订单中的商品字段到判断方法所需的字段
                goods_id: order.goods_id || '',
                price: Number(order.total_price) || 0,
                goods_price: Number(order.total_price) || 0,
                can_point_exchange: order.can_point_exchange || false,
                is_point_goods: order.is_point_goods || false,
                is_exchange: order.is_exchange || false,
                exchangeable: order.exchangeable || false,
                pointPrice: order.point_summary?.point_deduct || 0 // 积分抵扣数作为积分价格
              };
              const isPointsExchange = this.isPointGoods(orderItem);

              // 2. 提取积分抵扣数量（从订单的 point_summary 中获取）
              const exchangePoints = parseInt(order.point_summary?.point_deduct || 0);

              return {
                ...order,
                id: order.order_id, 
                goodsList: goodsList,
                isPointsExchange: isPointsExchange, // 标记是否为积分商品
                exchangePoints: exchangePoints // 积分抵扣数量（用于视图显示）
              };
            });
            // ========== 预处理结束 ==========
          
            const finalOrders = isRefresh ? processedOrders : [...this.data.orderList, ...processedOrders];
            const hasMore = finalOrders.length < total;
          
            this.setData({
              orderList: finalOrders,
              hasMore: hasMore,
              page: page + 1
            }, () => {
              if (finalOrders.length > 0) {
                console.log('✅ 预处理后的goodsList：', finalOrders[0].goodsList);
                console.log('✅ goodsList长度：', finalOrders[0].goodsList.length);
                console.log('✅ 是否为积分兑换商品：', finalOrders[0].isPointsExchange);
                console.log('✅ 抵扣积分数量：', finalOrders[0].exchangePoints);
              }
            });
          
            if (finalOrders.length === 0) {
              wx.showToast({ title: '暂无订单记录', icon: 'none' });
            }
            resolve(resData);
          } else if (res.statusCode === 401) {
            console.log('5. Token 过期/无效，清除并引导登录');
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            app.globalData.isLogin = false;
            this.setData({ token: '', isLogin: false });
            wx.showToast({ title: '登录状态失效，请重新登录', icon: 'none' });
            setTimeout(() => {
              this.guideToLogin();
            }, 1500);
            reject('Token 无效');
          } else {
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
    if (!this.data.token) {
      this.guideToLogin();
      return;
    }
    wx.navigateTo({
      url: `/pages/order-detail/order-detail?orderId=${orderId}`
    });
  },

// 订单列表页 order-list.js 中的 goToPay 方法
goToPay(e) {
  console.log('支付跳转参数：', e.currentTarget.dataset);
  // 1. 获取dataset中的所有参数
  const { order: datasetOrder = {}, orderid, ordersn, totalprice, actualpayprice } = e.currentTarget.dataset;
  // 2. 优先从页面data的orderList中匹配完整订单（兜底：防止dataset传递失败）
  const orderList = this.data.orderList || [];
  const matchedOrder = orderList.find(item => item.order_id == orderid) || datasetOrder;

  // 3. 积分商品参数（从匹配到的完整订单中取）
  const isPointGoods = !!matchedOrder.isPointsExchange;
  const exchangePoints = parseInt(matchedOrder.exchangePoints || 0);
  const deductPoint = exchangePoints;

  // 4. 跳转
  wx.navigateTo({
    url: `/pages/pay/pay?orderId=${orderid || ''}&orderSn=${ordersn || ''}&totalAll=${totalprice || '0.00'}&actualAmount=${actualpayprice || '0.00'}&deduct_point=${deductPoint}&isPointGoods=${isPointGoods}&exchangePoints=${exchangePoints}`,
    fail: (err) => {
      console.error('跳转支付页失败：', err);
      wx.showToast({ title: '支付页面跳转失败', icon: 'none' });
    }
  });
},

  handleOrderClick(e) {
    const order = e.currentTarget.dataset.order;
    if (!order) return;
    if (!this.data.token) {
      this.guideToLogin();
      return;
    }
    if (order.status === '待付款') {
      this.goToPay({
        currentTarget: {
          dataset: {
            orderid: order.order_id,
            ordersn: order.order_sn,
            totalprice: order.total_price,
            actualpayprice: order.actual_pay_price
          }
        }
      });
    } else {
      this.goToOrderDetail({
        currentTarget: {
          dataset: {
            orderid: order.order_id
          }
        }
      });
    }
  },

  refreshOrderList() {
    this.fetchOrders(true);
  }
});
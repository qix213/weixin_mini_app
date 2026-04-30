const app = getApp();

Page({
  data: {
    orderList: [], 
    loading: false, 
    hasMore: true, 
    page: 1, 
    pageSize: 10, 
    isLogin: false, 
    token: ''
  },

  timer: null, // 全局定时器

  onShow() {
    this.syncGlobalState();
    this.fetchOrders(true); 
  },

  onHide() {
    this.clearCountdown(); // 页面隐藏时清理定时器
  },

  onUnload() {
    this.clearCountdown(); // 页面卸载时清理定时器
  },

  onPullDownRefresh() {
    this.fetchOrders(true).finally(() => {
      wx.stopPullDownRefresh(); 
    });
  },

  onReachBottom() {
    if (!this.data.hasMore || this.data.loading) return;
    this.fetchOrders(false); 
  },

  syncGlobalState() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    this.setData({
      isLogin: app.globalData.isLogin || !!token,
      token: token
    });
  },

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

  isPointGoods(item) {
    const app = getApp();
    const goodsId = item.goods_id || item.id || '';
    const cacheIsPoint = app.getGoodsPointCache ? app.getGoodsPointCache(goodsId) : undefined;
    const isForcePointGoods = item.price > 0 || item.goods_price > 0; 
    
    if (cacheIsPoint !== undefined) {
      return cacheIsPoint || isForcePointGoods;
    }
    const pointField = item.can_point_exchange || item.is_point_goods || item.is_exchange || item.exchangeable || false;
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    
    let isPoint = false;
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true' || pointField === '1';
    } else if (typeof pointField === 'number') {
      isPoint = pointField === 1;
    } else {
      isPoint = !!pointField;
    }
    return isPoint || hasPointPrice || isForcePointGoods;
  },

  fetchOrders(isRefresh = false) {
    if (isRefresh) {
      this.setData({ page: 1, hasMore: true, orderList: [] });
      this.clearCountdown();
    }

    if (!this.data.token) {
      this.setData({ loading: false });
      this.guideToLogin();
      return Promise.reject('无Token');
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
        data: { page: page, page_size: pageSize },
        success: (res) => {
          if (res.statusCode === 200) {
            const resData = res.data;
            const newOrders = resData.data || [];
            const total = resData.total || 0;
            const now = Date.now();
          
            const processedOrders = newOrders.map(order => {
              let goodsList = [];
              if (order.goods_names && typeof order.goods_names === 'string') {
                goodsList = order.goods_names.split('、').length > 1 
                  ? order.goods_names.split('、') 
                  : order.goods_names.split(',');
              }

              const orderItem = {
                goods_id: order.goods_id || '',
                price: Number(order.total_price) || 0,
                goods_price: Number(order.total_price) || 0,
                can_point_exchange: order.can_point_exchange || false,
                is_point_goods: order.is_point_goods || false,
                is_exchange: order.is_exchange || false,
                exchangeable: order.exchangeable || false,
                pointPrice: order.point_summary?.point_deduct || 0 
              };
              
              const isPointsExchange = this.isPointGoods(orderItem);
              const exchangePoints = parseInt(order.point_summary?.point_deduct || 0);

              // 💥 修复版核心倒计时计算逻辑
              let expireTimeMs = 0;
              let isExpired = false; // 超时标记

              if (order.status === '待付款') {
                const timeStr = order.create_time || order.add_time || order.created_at || '';
                if (timeStr) {
                  // 1. 原汁原味解析，完美保留时区 (如带 T 或 Z 的时间)
                  let parsedTime = new Date(timeStr).getTime();
                  // 2. 如果解析失败，说明是 iOS 遇到纯本地时间字符串，进行降级转换
                  if (isNaN(parsedTime)) {
                    parsedTime = new Date(timeStr.replace(/-/g, '/')).getTime();
                  }

                  if (!isNaN(parsedTime) && parsedTime > 0) {
                    expireTimeMs = parsedTime + 15 * 60 * 1000;
                    // 【防闪烁核心】：如果拉取回来时就已经超时，直接做标记
                    if (now >= expireTimeMs) {
                      isExpired = true;
                    }
                  }
                }
              }

              // 如果已超时，直接返回 null 踢掉它
              if (isExpired) return null; 

              return {
                ...order,
                id: order.order_id, 
                goodsList: goodsList,
                isPointsExchange: isPointsExchange, 
                exchangePoints: exchangePoints,
                expireTimeMs: expireTimeMs,
                countdownText: '' 
              };
            }).filter(o => o !== null); // ⚡️ 渲染前直接把过期订单过滤掉！
          
            const finalOrders = isRefresh ? processedOrders : [...this.data.orderList, ...processedOrders];
            
            this.setData({
              orderList: finalOrders,
              hasMore: finalOrders.length < total,
              page: page + 1
            }, () => {
              this.startCountdown(); // 页面渲染完了，再安心重启倒计时
            });
          
            if (finalOrders.length === 0) {
              wx.showToast({ title: '暂无订单记录', icon: 'none' });
            }
            resolve(resData);
          } else if (res.statusCode === 401) {
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            app.globalData.isLogin = false;
            this.setData({ token: '', isLogin: false });
            wx.showToast({ title: '登录状态失效', icon: 'none' });
            setTimeout(() => { this.guideToLogin(); }, 1500);
            reject('Token 无效');
          } else {
            wx.showToast({ title: res.data.msg || '获取订单失败', icon: 'none' });
            reject(res.data);
          }
        },
        fail: (err) => {
          wx.showToast({ title: '网络异常', icon: 'none' });
          reject(err);
        },
        complete: () => {
          this.setData({ loading: false });
        }
      });
    });
  },

  // ========== 💥 核心：倒计时管理器 ==========
  startCountdown() {
    this.clearCountdown();
    this.timer = setInterval(() => {
      const now = Date.now();
      let hasChanges = false;
      let needRemove = false;

      const updatedList = this.data.orderList.map(order => {
        if (order.status === '待付款' && order.expireTimeMs > 0) {
          const remain = order.expireTimeMs - now;
          if (remain <= 0) {
            // 时间到了，从屏幕上剔除
            needRemove = true;
            return null; 
          } else {
            // 计算分秒
            const mins = Math.floor(remain / 1000 / 60).toString().padStart(2, '0');
            const secs = Math.floor((remain / 1000) % 60).toString().padStart(2, '0');
            const newText = `${mins}:${secs}`;
            if (order.countdownText !== newText) {
              order.countdownText = newText;
              hasChanges = true;
            }
          }
        }
        return order;
      });

      if (needRemove) {
        // 过滤掉超时的订单 (自动删除)
        const filteredList = updatedList.filter(o => o !== null);
        this.setData({ orderList: filteredList });
      } else if (hasChanges) {
        this.setData({ orderList: updatedList });
      }
    }, 1000);
  },

  clearCountdown() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  goToOrderDetail(e) {
    const orderId = e.currentTarget.dataset.orderid;
    if (!orderId) return;
    wx.navigateTo({ url: `/pages/order-detail/order-detail?orderId=${orderId}` });
  },

  goToPay(e) {
    const { orderid, ordersn, totalprice, actualpayprice } = e.currentTarget.dataset;
    const orderList = this.data.orderList || [];
    const matchedOrder = orderList.find(item => item.order_id == orderid) || {};
    
    const isPointGoods = !!matchedOrder.isPointsExchange;
    const exchangePoints = parseInt(matchedOrder.exchangePoints || 0);

    wx.navigateTo({
      url: `/pages/pay/pay?orderId=${orderid || ''}&orderSn=${ordersn || ''}&totalAll=${totalprice || '0.00'}&actualAmount=${actualpayprice || '0.00'}&deduct_point=${exchangePoints}&isPointGoods=${isPointGoods}&exchangePoints=${exchangePoints}`
    });
  },

  handleOrderClick(e) {
    const order = e.currentTarget.dataset.order;
    if (!order) return;
    this.goToOrderDetail({ currentTarget: { dataset: { orderid: order.order_id } } });
  }
});
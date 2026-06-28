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
  handleDeleteOrder(e) {
    const orderSn = e.currentTarget.dataset.ordersn;
    if (!orderSn) return;

    // 1. 弹出官方确认弹窗，增强交互安全性
    wx.showModal({
      title: '提示',
      content: '确定要删除这笔订单记录吗？删除后将无法找回。',
      confirmColor: '#EF4444', // 将确定按钮改为警告红
      success: (res) => {
        if (res.confirm) {
          this.executeDeleteRequest(orderSn);
        }
      }
    });
  },

  executeDeleteRequest(orderSn) {
    wx.showLoading({
      title: '正在删除...',
      mask: true
    });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/order/delete/`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.data.token}`
      },
      data: {
        order_sn: orderSn
      },
      success: (res) => {
        wx.hideLoading();

        if (res.data && res.data.code === 200) {
          wx.showToast({
            title: '订单已删除',
            icon: 'success'
          });

          // 2. 🌟 高级无感局部刷新：不需要重新请求服务器，直接在前端过滤掉被删除的单子
          const updatedList = this.data.orderList.filter(item => item.order_sn !== orderSn);

          this.setData({
            orderList: updatedList
          });

          // 如果列表删空了，可以弹个提示或者让页面显示空状态
          if (updatedList.length === 0) {
            wx.showToast({
              title: '暂无订单记录',
              icon: 'none'
            });
          }
        } else {
          wx.showToast({
            title: res.data.msg || '删除失败，请重试',
            icon: 'none'
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({
          title: '网络异常，删除失败',
          icon: 'none'
        });
      }
    });
  },
  isPointGoods(item) {
    const app = getApp();
    const goodsId = item.goods_id || item.id || '';

    // 1. 优先查缓存
    if (app.getGoodsPointCache) {
      const cacheIsPoint = app.getGoodsPointCache(goodsId);
      if (cacheIsPoint !== undefined) return cacheIsPoint;
    }

    // 2. 正常判断（彻底删掉那个坑人的 price > 0 逻辑）
    const pointField = item.can_point_exchange || item.is_point_goods || item.is_exchange || item.exchangeable;
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;

    let isPoint = false;
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true' || pointField === '1';
    } else {
      isPoint = !!pointField;
    }

    return isPoint || hasPointPrice;
  },

  fetchOrders(isRefresh = false) {
    if (isRefresh) {
      this.setData({
        page: 1,
        hasMore: true,
        orderList: []
      });
      this.clearCountdown();
    }

    if (!this.data.token) {
      this.setData({
        loading: false
      });
      this.guideToLogin();
      return Promise.reject('无Token');
    }

    if (this.data.loading) return Promise.resolve();
    this.setData({
      loading: true
    });

    const {
      page,
      pageSize
    } = this.data;
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
          if (res.statusCode === 200) {
            const resData = res.data;
            const newOrders = resData.data || [];
            const total = resData.total || 0;
            const now = Date.now();

            const processedOrders = newOrders.map(order => {
              let goodsList = [];
              if (order.goods_names && typeof order.goods_names === 'string') {
                goodsList = order.goods_names.split('、').length > 1 ?
                  order.goods_names.split('、') :
                  order.goods_names.split(',');
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
              let expireTimeMs = 0;
              // 🌟 核心：使用 status_code === 0 精准判断
              if (order.status_code === 0) {
                const timeStr = order.create_time || order.add_time || order.created_at || '';
                if (timeStr) {
                  let parsedTime = new Date(timeStr).getTime();
                  if (isNaN(parsedTime)) {
                    parsedTime = new Date(timeStr.replace(/-/g, '/')).getTime();
                  }

                  if (!isNaN(parsedTime) && parsedTime > 0) {
                    // 后端是 15 分钟超时，前端对齐 15 分钟
                    expireTimeMs = parsedTime + 15 * 60 * 1000;

                    // 如果拉取列表时就已经超时了，直接强行把它变成已取消
                    if (now >= expireTimeMs) {
                      order.status_code = 4;
                      order.status = '已取消';
                    }
                  }
                }
              }

              // 🌟 核心：不要 return null 删除了，直接原样返回
              return {
                ...order,
                id: order.order_id,
                goodsList: goodsList,
                isPointsExchange: isPointsExchange,
                exchangePoints: exchangePoints,
                expireTimeMs: expireTimeMs,
                countdownText: ''
              };
            });
            const finalOrders = isRefresh ? processedOrders : [...this.data.orderList, ...processedOrders];

            this.setData({
              orderList: finalOrders,
              hasMore: finalOrders.length < total,
              page: page + 1
            }, () => {
              this.startCountdown();
            });

            if (finalOrders.length === 0) {
              wx.showToast({
                title: '暂无订单记录',
                icon: 'none'
              });
            }
            resolve(resData);
          } else if (res.statusCode === 401) {
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            app.globalData.isLogin = false;
            this.setData({
              token: '',
              isLogin: false
            });
            wx.showToast({
              title: '登录状态失效',
              icon: 'none'
            });
            setTimeout(() => {
              this.guideToLogin();
            }, 1500);
            reject('Token 无效');
          } else {
            wx.showToast({
              title: res.data.msg || '获取订单失败',
              icon: 'none'
            });
            reject(res.data);
          }
        },
        fail: (err) => {
          wx.showToast({
            title: '网络异常',
            icon: 'none'
          });
          reject(err);
        },
        complete: () => {
          this.setData({
            loading: false
          });
        }
      });
    });
  },
// ====== 在 order-list.js 中加入 ======

handleReactivateAndPay(e) {
  const orderSn = e.currentTarget.dataset.ordersn;
  if (!orderSn) return;

  wx.showLoading({ title: '核实库存中...', mask: true });

  wx.request({
    url: `${app.globalData.baseUrl}/app01/order/reactivate/`,
    method: 'POST',
    header: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.data.token}`
    },
    data: { order_sn: orderSn },
    success: (res) => {
      wx.hideLoading();
      if (res.data && res.data.code === 200) {
        // 1. 恢复成功，直接调用原本的去支付逻辑跳转到收银台
        this.goToPay(e);
      } else {
        // 可能是因为库存不足等原因恢复失败，弹窗提示
        wx.showModal({
          title: '无法重新支付',
          content: res.data.msg || '商品发生变动，请重新下单',
          showCancel: false,
          confirmColor: '#2563EB'
        });
      }
    },
    fail: () => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常，请重试', icon: 'none' });
    }
  });
},
  startCountdown() {
    this.clearCountdown();
    this.timer = setInterval(() => {
      const now = Date.now();
      let hasChanges = false;

      const updatedList = this.data.orderList.map(order => {
        // 🌟 核心判断：只有 status_code === 0 才需要倒计时
        if (order.status_code === 0 && order.expireTimeMs > 0) {
          const remain = order.expireTimeMs - now;
          
          if (remain <= 0) {
            // 🌟 体验优化：时间到了不删除，直接原地变更为已取消！
            order.status_code = 4;
            order.status = '已取消';
            order.countdownText = '';
            hasChanges = true;
          } else {
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

      // 只要有变化，就直接更新页面
      if (hasChanges) {
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
    wx.navigateTo({
      url: `/pages/order-detail/order-detail?orderId=${orderId}`
    });
  },

  goToPay(e) {
    const {
      orderid,
      ordersn,
      totalprice,
      actualpayprice
    } = e.currentTarget.dataset;
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
    this.goToOrderDetail({
      currentTarget: {
        dataset: {
          orderid: order.order_id
        }
      }
    });
  },

  // ========== 🔥 新增：跳转物流详情页 ==========
  goToLogistics(e) {
    const orderSn = e.currentTarget.dataset.ordersn;
    if (!orderSn) {
      wx.showToast({
        title: '物流单号异常',
        icon: 'none'
      });
      return;
    }
    // 假设你的物流页面路径为 /pages/logistics/logistics （如有不同请自行修改路径）
    wx.navigateTo({
      url: `/pages/order-workbench/logistics?order_sn=${orderSn}`
    });
  }
});
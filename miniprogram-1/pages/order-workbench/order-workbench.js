Page({
  data: {
    loading: true,
    orderStatusTabs: [
      { key: 'all', name: '全部订单' },
      { key: 'pending', name: '待发货' },
      { key: 'shipped', name: '已发货' },
      { key: 'completed', name: '已完成' },
      { key: 'cancelled', name: '已取消' }
    ],
    activeTab: 'all',
    activeTabName: '全部订单',
    allOrders: [],
    filteredOrders: [],
    statusMap: { 0: '未付款', 1: '待发货', 2: '已发货', 3: '已完成', 4: '已取消' },
    currentLevel: 0
  },

  onLoad(options) {
    this.setData({
      activeTabName: this.data.orderStatusTabs[0].name,
      currentLevel: options.currentLevel || 0
    });
  },

  onShow() {
    if (!this.data.loading) {
      this.setData({ loading: true });
    }
    this.fetchOrderList().catch(err => {
      console.error("刷新列表失败:", err);
    });
  },

  /**
   * 核心修复：适配后端全新的扁平化订单列表架构
   */
  fetchOrderList() {
    return new Promise((resolve, reject) => {
      const app = getApp();
      const header = app.getRequestHeader ? app.getRequestHeader() : { 'Content-Type': 'application/json' };

      const requestData = { 
        current_level: this.data.currentLevel,
        sync_logistics: 1 
      };

      wx.request({
        url: `${app.globalData.baseUrl}/app01/member/sub-consume/`,
        method: "GET",
        header: header,
        data: requestData,
        success: (res) => {
          if (res.data?.code === 200) {
            let allOrders = [];
            // 🌟 核心破局点：现在的 res.data.data 直接就是订单数组，不需要再解析外层会员结构
            const rawOrders = res.data.data || [];
            
            rawOrders.forEach((order) => {
              // 直接从订单字典里提取内嵌的买家昵称
              const memberNickname = order.buyer_info?.nickname || '未知会员';
              let formatted = this.formatOrderData(order, memberNickname);
              allOrders.push(formatted);
            });

            // 过滤未付款记录
            const validOrders = allOrders.filter(o => o.status !== 0);
            
            // 批量追踪物流轨迹
            this.fetchExpressList(validOrders).then(() => {
              const cleanedOrders = validOrders.map(order => {
                let currentStatus = Number(order.status);
                const hasLogistics = order.expressList && order.expressList.length > 0;
                
                // 强制纠正分类 Tab 映射
                if (currentStatus === 4) {
                  order.statusKey = 'cancelled';
                } else {
                  order.statusKey = this.getStatusKeyByCode(currentStatus);
                }

                // =========================================================
                // 🌟 工作台按钮显隐状态机分流
                // =========================================================
                if (order.isPickUp) {
                  // A 轨：到店自取业务线
                  order.showConfirmReadyBtn = (currentStatus === 1); 
                  order.showConfirmReceiptBtn = (currentStatus === 2); 
                  order.showModifyBtn = false; // 自取单屏蔽修改收货地址
                  order.showCancelBtn = (currentStatus === 1 || currentStatus === 2);
                  order.showPreOrderBtn = false;
                  order.showWaitCollectBtn = false;
                  order.showLogisticsBtn = false;
                } else {
                  // B 轨：普通快递物流业务线
                  order.showConfirmReadyBtn = false;
                  order.showConfirmReceiptBtn = (currentStatus === 2);
                  order.showPreOrderBtn = (currentStatus === 1 && !hasLogistics);
                  order.showWaitCollectBtn = (currentStatus === 1 && hasLogistics);
                  order.showModifyBtn = (currentStatus === 1);
                  order.showCancelBtn = (currentStatus === 1);
                  order.showLogisticsBtn = (currentStatus > 1 || hasLogistics);
                }

                return order;
              });

              // 智能计算并刷新当前 Tab 下的订单子集
              let targetTab = this.data.activeTab;
              this.setData({
                loading: false,
                allOrders: cleanedOrders,
                filteredOrders: targetTab === 'all' 
                  ? cleanedOrders 
                  : cleanedOrders.filter(o => o.statusKey === targetTab)
              });
              resolve();
            });
          } else {
            this.setData({ loading: false });
            resolve();
          }
        },
        fail: (err) => {
          this.setData({ loading: false });
          reject(err);
        }
      });
    });
  },

  fetchExpressList(orders) {
    return new Promise((resolve) => {
      const app = getApp();
      const header = app.getRequestHeader ? app.getRequestHeader() : { 'Content-Type': 'application/json' };
      const orderSns = [...new Set(orders.map(o => o.orderSn).filter(Boolean))];

      if (orderSns.length === 0) {
        orders.forEach(order => {
          order.expressList = [];
          order.latestExpress = {};
        });
        resolve();
        return;
      }

      wx.request({
        url: `${app.globalData.baseUrl}/app01/express/list/`,
        method: 'GET',
        header: header,
        data: { order_sns: orderSns.join(','), format: 'json' },
        success: (res) => {
          if (res.data && res.data.code === 200) {
            const expressList = res.data.data || [];
            const expressMap = {};

            expressList.forEach((express) => {
              const orderSn = express.order_sn || '';
              if (!orderSn) return;

              if (!expressMap[orderSn]) expressMap[orderSn] = [];
              expressMap[orderSn].push({
                logisticsNo: express.logistics_no || '未知运单号',
                logisticsCompany: express.logistics_company || '未知物流公司',
                logisticsTime: express.logistics_time || '未知时间',
                acceptAddress: express.accept_address || '未知地点',
                logisticsStatusName: express.logistics_status_name || '未知状态',
                courierName: express.courier_name || '未知派件人',
                courierPhone: express.courier_phone || '未知电话'
              });
            });

            orders.forEach((order) => {
              const orderSn = order.orderSn;
              order.expressList = expressMap[orderSn] || [];
              order.latestExpress = order.expressList[0] || {};
            });
          } else {
            orders.forEach(order => { order.expressList = []; order.latestExpress = {}; });
          }
          resolve();
        },
        fail: () => {
          orders.forEach(order => { order.expressList = []; order.latestExpress = {}; });
          resolve();
        }
      });
    });
  },

  /**
   * 核心重塑：完美消解单品对象数组与大老板端平铺文本字段的冲突
   */
  formatOrderData(order, memberNickname) {
    const orderSn = order.order_sn || `order_${Math.random().toString(36).substr(2,8)}`;
    let status = this.safeToNumber(order.status || 0); 
    
    const deliveryType = order.delivery_type || 1;
    const isPickUp = Number(deliveryType) === 2;

    let statusName = order.status_name || this.data.statusMap[status] || '未知状态';
    
    let statusKey = 'all';
    if (status === 1) statusKey = 'pending';
    else if (status === 2) statusKey = 'shipped';
    else if (status === 3) statusKey = 'completed';
    else if (status === 4) statusKey = 'cancelled';

    // 动态向下兼容解析商品列表
    let formattedGoodsList = [];
    if (order.goods_list && order.goods_list.length > 0) {
      formattedGoodsList = order.goods_list.map(g => ({
        goodsName: g.goods_name || '未知商品',
        num: this.safeToNumber(g.num || 1),
        price: this.safeToNumber(g.price || 0).toFixed(2),
        totalPrice: this.safeToNumber(g.total_price || 0).toFixed(2)
      }));
    } else if (order.goods_names) {
      // 🌟 高级包装：将大老板端的平铺字符串虚拟封装为 WXML 支持的 wx:for 结构
      formattedGoodsList = [{
        goodsName: order.goods_names, 
        num: this.safeToNumber(order.goods_count || 1),
        price: this.safeToNumber(order.actual_pay_money || order.total_price || 0).toFixed(2),
        totalPrice: this.safeToNumber(order.actual_pay_money || order.total_price || 0).toFixed(2)
      }];
    }

    return {
      id: order.id || orderSn,
      orderSn: orderSn,
      status: status,
      statusName: statusName,
      statusKey: statusKey,
      isPickUp: isPickUp,     
      totalPrice: this.safeToNumber(order.actual_pay_money || order.total_price || 0).toFixed(2),
      createTime: order.create_time || '未知时间',
      pickUpStoreName: order.pick_up_store_name || '', 
      goodsList: formattedGoodsList,
      memberNickname: order.buyer_info ? order.buyer_info.nickname : (memberNickname || '未知买家'),
      memberPhone: order.buyer_info ? order.buyer_info.phone : '',
      expressList: [],
      latestExpress: {},
      trackExpanded: false,
      expanded: false
    };
  },

  getStatusKeyByCode(s) {
    const map = { 1: 'pending', 2: 'shipped', 3: 'completed', 4: 'cancelled' };
    return map[s] || 'all';
  },

  onTabChange(e) {
    const key = e.currentTarget.dataset.key;
    const tab = this.data.orderStatusTabs.find(t => t.key === key);
    this.setData({
      activeTab: key,
      activeTabName: tab?.name || '全部订单',
      filteredOrders: key === 'all' ? this.data.allOrders : this.data.allOrders.filter(o => o.statusKey === key)
    });
  },

  toggleOrderExpand(e) {
    const index = e.currentTarget.dataset.index;
    let list = [...this.data.filteredOrders];
    list[index].expanded = !list[index].expanded;
    this.setData({ filteredOrders: list });
  },

  toggleTrackExpand(e) {
    const index = e.currentTarget.dataset.index;
    let list = [...this.data.filteredOrders];
    list[index].trackExpanded = !list[index].trackExpanded;
    this.setData({ filteredOrders: list });
  },

  safeToNumber(v) {
    const n = parseFloat(v); 
    return isNaN(n) ? 0 : n;
  },

  onPullDownRefresh() {
    this.setData({ loading: true });
    this.fetchOrderList().finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  handleConfirmReady(e) {
    const orderSn = e.currentTarget.dataset.sn;
    wx.showModal({
      title: '备货确认',
      content: `确定订单 ${orderSn} 已备货完成，通知客户提货吗？`,
      success: (modalRes) => {
        if (modalRes.confirm) {
          wx.showLoading({ title: '正在提交状态...', mask: true });
          const app = getApp();
          const header = app.getRequestHeader ? app.getRequestHeader() : { 'Content-Type': 'application/json' };
          
          wx.request({
            url: `${app.globalData.baseUrl}/app01/order/confirm_ready/`, 
            method: 'POST',
            header: header,
            data: { order_sn: orderSn },
            success: (res) => {
              wx.hideLoading();
              if (res.data?.code === 200) {
                wx.showToast({ title: '已变更为待取货', icon: 'success' });
                this.fetchOrderList().catch(err => console.error(err));
              } else {
                wx.showToast({ title: res.data?.msg || '操作失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络异常，请重试', icon: 'none' });
            }
          });
        }
      }
    });
  },

  goToPreOrder(e) {
    const orderSn = e.currentTarget.dataset.sn;
    const order = this.data.allOrders.find(o => o.orderSn === orderSn);
    if (order && order.status !== 1) {
      wx.showToast({ title: '该订单已处理，无法重复预约', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: `/pages/order-workbench/preOrder?order_sn=${orderSn}` });
  },

  goToModifyOrder(e) {
    const orderSn = e.currentTarget.dataset.sn;
    wx.navigateTo({ url: `/pages/order-workbench/modify?order_sn=${orderSn}` });
  },

  goToCancelOrder(e) {
    const orderSn = e.currentTarget.dataset.sn;
    wx.navigateTo({ url: `/pages/order-workbench/cancel?order_sn=${orderSn}` });
  },

  goToLogistics(e) {
    const orderSn = e.currentTarget.dataset.sn;
    wx.navigateTo({ url: `/pages/order-workbench/logistics?order_sn=${orderSn}` });
  }
});
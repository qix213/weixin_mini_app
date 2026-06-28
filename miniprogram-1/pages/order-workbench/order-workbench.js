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
    // onLoad 里就不调用获取列表了，交给 onShow 去做，防止请求两次
  },
  onShow() {
    if (!this.data.loading) {
      this.setData({ loading: true });
    }
    
    this.fetchOrderList().catch(err => {
      console.error("刷新列表失败:", err);
    });
  },

  fetchOrderList() {
    return new Promise((resolve, reject) => {
      const app = getApp();
      const header = app.getRequestHeader ? app.getRequestHeader() : { 'Content-Type': 'application/json' };
  
      const requestData = { 
        current_level: this.data.currentLevel,
        sync_logistics: 1  // 强制写死1
      };
  
      wx.request({
        url: `${app.globalData.baseUrl}/app01/member/sub-consume/`,
        method: "GET",
        header: header,
        data: requestData,
        success: (res) => {
          if (res.data?.code === 200) {
            let allOrders = [];
            const rawOrderData = res.data.data || [];
            
            rawOrderData.forEach((memberItem) => {
              const memberNickname = memberItem.member_info?.nickname || '未知会员';
              const memberOrders = memberItem.orders || [];
  
              memberOrders.forEach((order) => {
                let formatted = this.formatOrderData(order, memberNickname);
                allOrders.push(formatted);
              });
            });
  
            const validOrders = allOrders.filter(o => o.status !== 0);
            
            this.fetchExpressList(validOrders).then(() => {
              const cleanedOrders = validOrders.map(order => {
                // 现在前端 100% 信任后端传来的 currentStatus！
                let currentStatus = Number(order.status);
                const hasLogistics = order.expressList && order.expressList.length > 0;
                
                // 1. 确定 Tab 分类
                if (currentStatus === 4) {
                  order.statusKey = 'cancelled';
                } else {
                  order.statusKey = this.getStatusKeyByCode(currentStatus);
                }

                // =========================================================
                // 🌟 2. 按钮显隐终极逻辑 (精准判断，绝不冲突)
                // =========================================================
                
                // 【预约下单】：仅在后端说是待发货 (1)，且完全没有物流单号时显示
                order.showPreOrderBtn = (currentStatus === 1 && !hasLogistics);
                
                // 【等待揽收】：后端说是待发货 (1)，但已经有单号了 (预约成功，等小哥上门)
                order.showWaitCollectBtn = (currentStatus === 1 && hasLogistics);
                
                order.showModifyBtn = (currentStatus === 1);
                order.showCancelBtn = (currentStatus === 1);
                
                // 【物流查询】：只要状态是已发货(2)及以上，或者虽然待发货但已经有了运单号，都可以查
                order.showLogisticsBtn = (currentStatus > 1 || hasLogistics);

                return order;
              });
  
              this.setData({
                loading: false,
                allOrders: cleanedOrders,
                filteredOrders: this.data.activeTab === 'all' 
                  ? cleanedOrders 
                  : cleanedOrders.filter(o => o.statusKey === this.data.activeTab)
              });
              resolve();
            });
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
      const header = app.getRequestHeader ? app.getRequestHeader() : {
        'Content-Type': 'application/json'
      };

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
              const formattedExpress = {
                logisticsNo: express.logistics_no || '未知运单号',
                logisticsCompany: express.logistics_company || '未知物流公司',
                logisticsTime: express.logistics_time || '未知时间',
                acceptAddress: express.accept_address || '未知地点',
                logisticsStatusName: express.logistics_status_name || '未知状态',
                courierName: express.courier_name || '未知派件人',
                courierPhone: express.courier_phone || '未知电话'
              };
              expressMap[orderSn].push(formattedExpress);
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
        fail: (err) => {
          orders.forEach(order => { order.expressList = []; order.latestExpress = {}; });
          resolve();
        }
      });
    });
  },

  formatOrderData(order, memberNickname) {
    const orderSn = order.order_sn || `order_${Math.random().toString(36).substr(2,8)}`;
    
    // 🌟 核心还原：因为是 sub-consume 接口，确实就是传的 status，而不是 status_code！
    let status = this.safeToNumber(order.status || 0); 
    
    // 优先判断已取消状态，禁止被物流状态覆盖
    let statusKey;
    if (status === 4) {
      statusKey = 'cancelled';
    } else {
      statusKey = this.getStatusKeyByCode(status);
      const logisticsStatus = order.latest_express?.logistics_status_name || '';
      if (logisticsStatus.indexOf('已签收') !== -1 || logisticsStatus === '已完成') {
        statusKey = 'completed';
      }
    }

    return {
      id: orderSn,
      orderSn: orderSn,
      status: status,
      statusName: order.status_name || this.data.statusMap[status],
      statusKey: statusKey,
      totalPrice: this.safeToNumber(order.total_price || 0).toFixed(2),
      createTime: order.create_time || '未知时间',
      expressList: [],
      latestExpress: {},
      trackExpanded: false,
      expanded: false,
      goodsList: (order.goods_list||[]).map(g=>({
        goodsName: g.goods_name||'未知商品',
        num: this.safeToNumber(g.num||1),
        price: this.safeToNumber(g.price||0).toFixed(2),
        totalPrice: this.safeToNumber(g.total_price||0).toFixed(2)
      })),
      memberNickname: memberNickname
    };
  },

  getStatusKeyByCode(s) {
    const map = {1:'pending',2:'shipped',3:'completed',4:'cancelled'};
    return map[s]||'all';
  },

  onTabChange(e) {
    const key = e.currentTarget.dataset.key;
    const tab = this.data.orderStatusTabs.find(t=>t.key===key);
    this.setData({
      activeTab: key,
      activeTabName: tab?.name||'全部订单',
      filteredOrders: key==='all' ? this.data.allOrders : this.data.allOrders.filter(o=>o.statusKey===key)
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

  formatDate(str) {
    if(!str) return '未知时间';
    try { return str.replace(' ','T'); } catch(e){ return str; }
  },

  onPullDownRefresh() {
    this.setData({loading:true});
    this.fetchOrderList().finally(()=>{
      wx.stopPullDownRefresh();
    });
  },

  goToPreOrder(e) {
    const orderSn = e.currentTarget.dataset.sn;
    // 1. 查找到当前点击的订单数据
    const order = this.data.allOrders.find(o => o.orderSn === orderSn);
    // 2. 状态拦截：只有 "待发货" (status === 1) 的订单才能预约下单
    if (order && order.status !== 1) {
      wx.showToast({ 
        title: '该订单已处理，无法重复预约', 
        icon: 'none' 
      });
      return;
    }
    // 3. 状态通过，正常跳转
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
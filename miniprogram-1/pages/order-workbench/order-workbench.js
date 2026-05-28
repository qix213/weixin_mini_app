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
    this.fetchOrderList().then(() => {
    }).catch(err => {
    });
  },

  fetchOrderList() {
    return new Promise((resolve, reject) => {
      const app = getApp();
      const header = app.getRequestHeader ? app.getRequestHeader() : { 'Content-Type': 'application/json' };
  
      // ✅ 强制定义参数，打印前端传参（关键调试）
      const requestData = { 
        current_level: this.data.currentLevel,
        sync_logistics: 1  // 强制写死1
      };
      console.log("【前端传参】sync_logistics =", requestData.sync_logistics); // 打印验证
  
      wx.request({
        url: `${app.globalData.baseUrl}/app01/member/sub-consume/`,
        method: "GET",
        header: header,
        data: requestData, // 用强制定义的参数
        success: (res) => {
          if (res.data?.code === 200) {
            let allOrders = [];
            const rawOrderData = res.data.data || [];
            
            console.log("✅ 后端传回【已同步物流】的订单列表：", rawOrderData);
  
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
                if (order.status === 4) {
                  order.statusKey = 'cancelled';
                  return order;
                }
                const logisStatus = order.latestExpress?.logisticsStatusName || '';
                if (logisStatus.indexOf('签收') !== -1 || logisStatus.indexOf('完成') !== -1) {
                  order.statusKey = 'completed';
                }
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
    let status = this.safeToNumber(order.status || 0);
    
    // ✅ 核心修复：优先判断已取消状态，禁止被物流状态覆盖
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
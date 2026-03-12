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
  
      wx.request({
        url: `${app.globalData.baseUrl}/app01/member/sub-consume/`,
        method: 'GET',
        header: header,
        data: { current_level: this.data.currentLevel },
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
  
            // 这里的 filteredOrders 是初始过滤（排除未付款）
            const validOrders = allOrders.filter(o => o.status !== 0);
  
            // 🔥 关键点：物流信息获取后的二次清洗
            this.fetchExpressList(validOrders).then(() => {
              
              // 对所有订单进行状态二次校对
              const cleanedOrders = validOrders.map(order => {
                const logisStatus = order.latestExpress?.logisticsStatusName || '';
                // 只要物流包含“签收”或“已完成”，强制把 Tab 分类改为 completed
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
              if (!orderSn) {
                return;
              }

              if (!expressMap[orderSn]) {
                expressMap[orderSn] = [];
              }

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
            orders.forEach(order => {
              order.expressList = [];
              order.latestExpress = {};
            });
          }
          resolve();
        },
        fail: (err) => {
          orders.forEach(order => {
            order.expressList = [];
            order.latestExpress = {};
          });
          resolve();
        }
      });
    });
  },

  formatOrderData(order, memberNickname) {
    const orderSn = order.order_sn || `order_${Math.random().toString(36).substr(2,8)}`;
    let status = this.safeToNumber(order.status || 0);
    
    // 获取物流状态名称（用于精准分类）
    const logisticsStatus = order.latest_express?.logistics_status_name || '';
    
    let statusKey = this.getStatusKeyByCode(status);
    
    // 🔥 核心修正：如果物流显示“已签收”，强制分类到“已完成”
    if (logisticsStatus.indexOf('已签收') !== -1 || logisticsStatus === '已完成') {
      statusKey = 'completed';
    }

    return {
      id: orderSn,
      orderSn: orderSn,
      status: status,
      statusName: order.status_name || this.data.statusMap[status],
      statusKey: statusKey, // 使用修正后的 key
      totalPrice: this.safeToNumber(order.total_price || 0).toFixed(2), // 统一保留两位小数
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

  // 新增：物流轨迹展开/收起方法（修复点击无反应）
  toggleTrackExpand(e) {
    const index = e.currentTarget.dataset.index;
    let list = [...this.data.filteredOrders];
    list[index].trackExpanded = !list[index].trackExpanded;
    this.setData({ filteredOrders: list });
  },

  safeToNumber(v) {
    const n = parseFloat(v); 
    const result = isNaN(n)?0:n;
    return result;
  },

  formatDate(str) {
    if(!str) return '未知时间';
    try {
      const formatted = str.replace(' ','T');
      return formatted;
    }catch(e){
      return str;
    }
  },

  onPullDownRefresh() {
    this.setData({loading:true});
    this.fetchOrderList().finally(()=>{
      wx.stopPullDownRefresh();
    });
  }
});
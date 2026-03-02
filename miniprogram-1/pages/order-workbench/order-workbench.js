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
    this.fetchOrderList();
  },

fetchOrderList() {
  return new Promise((resolve, reject) => {
    const app = getApp();
    const header = app.getRequestHeader ? app.getRequestHeader() : {
      'Content-Type': 'application/json'
    };

    wx.request({
      url: app.globalData.baseUrl + '/app01/member/sub-consume/',
      method: 'GET',
      header: header,
      data: { current_level: this.data.currentLevel },
      success: (res) => {
        this.setData({ loading: false });
        if (res.data.code === 200) {
          let allOrders = [];
          (res.data.data || []).forEach(memberItem => {
            const memberInfo = memberItem.member_info || {};
            const memberNickname = memberInfo.nickname || '未知会员';
            (memberItem.orders || []).forEach(order => {
              // 🔥 关键：打印单个订单的原始数据，看收货人字段名
              console.log('订单原始数据：', order);
              // 重点看 order 里的收货人相关字段，比如 consignee、receiver、name、phone 等
              
              let formatted = this.formatOrderData(order, memberNickname);
              formatted.expanded = false;
              allOrders.push(formatted);
            });
          });
          const filteredOrders = allOrders.filter(o => o.status !== 0);
          this.setData({
            allOrders: filteredOrders,
            filteredOrders: filteredOrders
          });
          resolve();
        } else {
          wx.showToast({ title: '获取订单失败', icon: 'none' });
          reject();
        }
      },
      fail: (err) => {
        this.setData({ loading: false });
        wx.showToast({ title: '网络错误', icon: 'none' });
        reject(err);
      }
    });
  });
},

formatOrderData(order, memberNickname) {
  const orderSn = order.order_sn || `order_${Math.random().toString(36).substr(2,8)}`;
  const status = this.safeToNumber(order.status || 0);
  
  // 🔥 解析后端返回的收货信息（4/5级用户能拿到真实值）
  const receiverName = order.receiver_name || '未知收货人';
  const receiverPhone = order.receiver_phone || '未知电话';
  const receiverAddress = order.receiver_address || '未知地址';

  return {
    id: orderSn,
    orderSn: orderSn,
    status: status,
    statusName: order.status_name || this.data.statusMap[status],
    statusKey: this.getStatusKeyByCode(status),
    totalPrice: this.safeToNumber(order.total_price || 0),
    createTime: this.formatDate(order.create_time || ''),
    // 修复后的收货人信息
    receiverName: receiverName,
    receiverPhone: receiverPhone,
    receiverAddress: receiverAddress,
    // 商品信息
    goodsList: (order.goods_list||[]).map(g=>({
      goodsName: g.goods_name||g.name||'未知商品',
      num: this.safeToNumber(g.num||g.quantity||1),
      price: this.safeToNumber(g.price||0),
      totalPrice: this.safeToNumber(g.total_price||g.amount||0)
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

  // 🔥 终极修复：点击展开/收起（绝对生效）
  toggleOrderExpand(e) {
    const index = e.currentTarget.dataset.index;
    let list = this.data.filteredOrders;
    // 取当前订单，翻转展开状态
    list[index].expanded = !list[index].expanded;
    this.setData({
      filteredOrders: list
    });
  },

  safeToNumber(v) {
    const n = parseFloat(v); return isNaN(n)?0:n;
  },

  formatDate(str) {
    if(!str) return '未知时间';
    try {
      return str.replace(' ','T');
    }catch(e){return str;}
  },

  onPullDownRefresh() {
    this.setData({loading:true});
    this.fetchOrderList().finally(()=>{
      wx.stopPullDownRefresh();
    });
  }
});
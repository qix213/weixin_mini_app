const app = getApp();
Page({
  data: {
    loading: true,
    isSubmitting: false,
    order_sn: '',
    orderInfo: {},
    jdRealTimeStatus: '',
    statusText: '',
    statusDesc: '',
    statusClass: '',
    disableBtn: true,
    btnText: ''
  },

  onLoad(options) {
    if (options.order_sn) {
      this.setData({ order_sn: options.order_sn });
      this.queryJdTrace();
    }
  },

  // 查询京东实时轨迹
  queryJdTrace() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd/trace/query/`,
      data: { order_sn: that.data.order_sn },
      success(res) {
        if (res.data.code === 200) {
          const realStatus = res.data.latest_status || "运输中";
          that.setData({ jdRealTimeStatus: realStatus });
          that.getDetail();
        }
      }
    })
  },

  // 加载订单详情
  getDetail() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/order/detail/`,
      header: app.getRequestHeader(),
      data: { order_sn: that.data.order_sn },
      success(res) {
        if (res.data.code === 200) {
          that.setData({ orderInfo: res.data.data, loading: false });
          that.initStatus();
        }
      }
    })
  },

  // ✅【修复完成】正常状态文案，无强制取消
  initStatus() {
    const realStatus = this.data.jdRealTimeStatus;
    const orderStatus = this.data.orderInfo.status;

    let statusText, statusDesc, statusClass, disableBtn, btnText;

    // ============== 待揽收 / 揽收中：正常取消 ==============
    if (realStatus.includes('揽收')) {
      statusText = realStatus; // 显示：揽收中
      statusDesc = '可取消订单，快递员将不会上门取件';
      statusClass = 'ing';
      disableBtn = false;
      btnText = '确认取消订单'; // 正常文案，无强制
    }
    // 已妥投：禁用
    else if (realStatus.includes('妥投')) {
      statusText = realStatus;
      statusDesc = '已签收，无法操作';
      statusClass = 'finish';
      disableBtn = true;
      btnText = '无法操作';
    }
    // 已取消
    else if (orderStatus === 4) {
      statusText = '已取消';
      statusDesc = '订单已取消完成';
      statusClass = 'cancel';
      disableBtn = true;
      btnText = '已取消';
    }
    // 其他运输状态：正常取消
    else {
      statusText = realStatus;
      statusDesc = '可取消订单';
      statusClass = 'ing';
      disableBtn = false;
      btnText = '确认取消订单';
    }

    this.setData({ statusText, statusDesc, statusClass, disableBtn, btnText });
  },

  // 确认取消（弹窗文案同步正常化）
  confirmCancel() {
    wx.showModal({
      title: '确认取消',
      content: '确定取消该订单吗？取消后快递员将不会上门取件',
      confirmColor: '#ff4d4f',
      success: res => res.confirm && this.doCancel()
    })
  },

  // 执行取消
  doCancel() {
    const that = this;
    that.setData({ isSubmitting: true });
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd-logistics/cancel/`,
      method: 'POST',
      data: { order_sn: that.data.order_sn },
      success(res) {
        if (res.data.code === 200) {
          wx.showToast({ title: '取消成功', icon: 'success' });
          setTimeout(() => {
            that.queryJdTrace();
            const pages = getCurrentPages();
            pages.length > 1 && pages[pages.length-2].onPullDownRefresh();
          }, 1500);
        } else {
          wx.showToast({ title: res.data.msg, icon: 'error' });
        }
      },
      complete: () => that.setData({ isSubmitting: false })
    })
  }
});
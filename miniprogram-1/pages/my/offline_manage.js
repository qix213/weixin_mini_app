import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    activeTab: 'customers',
    subActiveTab: 'pending',
    groupedCustomers: [],
    activeNames: [],
    showTimePicker: false,
    currentDate: new Date().getTime(),
    minDate: new Date().getTime(),
    bookTempData: {},
    allRecords: []
  },

  onLoad() {
    this.fetchGroupedAssets();
    this.fetchRecords();
  },

  onMainTabChange(e) {
    const tabName = e.detail.name;
    this.setData({ activeTab: tabName });
    if (tabName === 'records') {
      this.fetchRecords();
    } else {
      this.fetchGroupedAssets();
    }
  },

  onSubTabChange(e) {
    this.setData({ subActiveTab: e.detail.name });
  },

  fetchRecords() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/offline_services/`, 
      header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
      success: (res) => {
        const records = res.data.data || res.data.results || res.data || [];
        this.setData({ allRecords: records });
      }
    });
  },

  onCollapseChange(event) {
    this.setData({ activeNames: event.detail });
  },

  fetchGroupedAssets() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/offline_services/query_assets/`,
      header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
      success: (res) => {
        const assets = res.data.data || [];
        const groupMap = {};
        
        assets.forEach(item => {
          const mid = item.member_id; 
          if (!groupMap[mid]) {
            groupMap[mid] = {
              user_id: mid,
              nickname: item.customer_nickname, 
              projects: []
            };
          }
          groupMap[mid].projects.push(item);
        });

        this.setData({ groupedCustomers: Object.values(groupMap) });
      }
    });
  },

  openTimePicker(e) {
    this.setData({ 
      showTimePicker: true, 
      bookTempData: {
        uid: e.currentTarget.dataset.uid,
        pid: e.currentTarget.dataset.pid
      }
    });
  },

  closeTimePicker() {
    this.setData({ showTimePicker: false });
  },

  onPickerChange(e) {
    this.setData({ currentDate: e.detail });
  },
  previewReviewImage(e) {
    const current = e.currentTarget.dataset.current; // 当前点击的那张图
    const urls = e.currentTarget.dataset.urls;       // 这一组评价里所有的图
    
    if (!urls || urls.length === 0) return;
    
    wx.previewImage({
      current: current, // 当前显示图片的 http 链接
      urls: urls        // 需要预览的图片 http 链接列表
    });
  },

  onCollapseChange(event) {
    this.setData({ activeNames: event.detail });
  },
  onPickerConfirm() {
    const timestamp = this.data.currentDate; 
    const date = new Date(timestamp);
    const timeStr = `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    
    Toast.loading({ message: '预约中...', forbidClick: true });
    const token = wx.getStorageSync('accessToken');

    wx.request({
      url: `${app.globalData.baseUrl}/app01/offline_services/book_appointment/`,
      method: 'POST',
      header: { 
        'Authorization': `Bearer ${token}`,
        'content-type': 'application/json'
      },
      data: {
        customer_id: this.data.bookTempData.uid,
        project_id: this.data.bookTempData.pid,
        appointment_time: timeStr
      },
      success: (res) => {
        if (res.data.code === 200) {
          Toast.success('预约成功');
          this.setData({ 
            showTimePicker: false,
            activeTab: 'records',
            subActiveTab: 'pending'
          });
          this.fetchRecords();
          this.fetchGroupedAssets();
        } else {
          Toast.fail(res.data.msg || '预约失败');
        }
      },
      fail: () => {
        Toast.fail('网络异常');
      }
    });
  }
});
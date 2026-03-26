// 顶部获取全局App实例
const app = getApp();

Page({
  data: {
    searchValue: '',
    categoryList: ['全部视频', '蓝朋友', '蓝明星', '护肤私教', 'MINI-studio 主理人', 'Ta创+'],
    activeTab: 0,
    levelMap: { 0: undefined, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5 },
    videoList: [],
    loading: false,       
    finished: false,      
    page: 1,              
    pageSize: 10,
    userLevel: 1,
    userLevelName: ''
  },

  onLoad() {
    console.log('=== 进入onLoad ===');
    if (!this.checkLoginStatus()) return;

    const userInfo = wx.getStorageSync('userInfo') || {};
    const levelNameMap = { 1: "蓝朋友", 2: "蓝明星", 3: "护肤私教", 4: "MINI-studio 主理人", 5: "Ta创+" };
    this.setData({
      userLevel: userInfo.user_type || 1,
      userLevelName: userInfo.user_type_name || levelNameMap[userInfo.user_type] || ''
    });
  },

  onShow() {
    console.log('=== 进入onShow，强制触发加载 ===');
    this.onTabChange({ currentTarget: { dataset: { index: 0 } } });
  },

  checkLoginStatus() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    console.log('=== 登录态校验 ===', {
      tokenExist: !!accessToken,
      tokenValue: accessToken || '无'
    });
    if (!accessToken) {
      wx.showModal({
        title: '请先登录',
        content: '访问商学院需要先登录账号',
        showCancel: false,
        success: () => wx.navigateTo({ url: '/pages/login/login' })
      });
      return false;
    }
    return true;
  },

  onTabChange(e) {
    const index = e.currentTarget.dataset.index;
    console.log(`=== 切换到【${this.data.categoryList[index]}】===`);
    this.setData({
      activeTab: index,
      page: 1,
      videoList: [],
      finished: false
    }, () => {
      this.getVideoList();
    });
  },

  getVideoList() {
    console.log('=== 进入getVideoList ===');
    const { page, pageSize, activeTab } = this.data;
    const requiredLevel = this.data.levelMap[activeTab];
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;

    this.setData({ loading: true });

    const requestData = { page, page_size: pageSize };
    if (activeTab !== 0 && requiredLevel !== undefined) {
      requestData.required_level = requiredLevel;
    }

    console.log('=== 发送请求 ===', {
      url: `${app.globalData.baseUrl}/app01/video_courses/`,
      header: { 'Authorization': `Bearer ${accessToken}` },
      data: requestData
    });

    wx.request({
      // 🔥 全局配置地址
      url: `${app.globalData.baseUrl}/app01/video_courses/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      data: requestData,
      success: (res) => {
        console.log('=== 后端原始返回 ===', {
          statusCode: res.statusCode,
          header: res.header,
          data: res.data
        });

        const newList = res.data?.results || res.data?.data || (Array.isArray(res.data) ? res.data : []);
        this.setData({
          videoList: newList,
          finished: newList.length < pageSize
        });

        wx.showToast({
          title: newList.length > 0 ? `加载到${newList.length}条课程` : '后端返回空数据',
          icon: 'none',
          duration: 3000
        });
      },
      fail: (err) => {
        console.error('=== 请求失败 ===', err);
        wx.showToast({ title: `请求失败：${err.errMsg}`, icon: 'none' });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  toVideoPlay(e) {
    const videoId = e.currentTarget.dataset.id;
    const videoItem = this.data.videoList.find(item => item.id === videoId);
    if (!videoItem) {
      wx.showToast({ title: '视频不存在', icon: 'none' });
      return;
    }

    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    wx.request({
      // 🔥 全局配置地址
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/check_permission/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      success: (res) => {
        if (res.data?.has_permission) {
          wx.navigateTo({
            url: `/pages/school/play?id=${videoId}&videoUrl=${encodeURIComponent(res.data.video_url)}`
          });
          this.updatePlayCount(videoId);
        } else {
          wx.showModal({
            title: '很抱歉',
            content: `需要${videoItem.required_level_name}以上会员等级才能够观看`,
            showCancel: false,
            confirmText: '我知道了'
          });
        }
      },
      fail: (err) => {
        console.error('权限校验失败：', err);
        wx.showToast({ title: '校验失败，请重试', icon: 'none' });
      }
    });
  },

  updatePlayCount(videoId) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    wx.request({
      // 🔥 全局配置地址
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/add_play_count/`,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      fail: (err) => {
        console.error('播放次数更新失败：', err);
      }
    });
  },

  toCourseStudy() {
    this.setData({ activeTab: 0, page: 1, videoList: [], finished: false });
    this.getVideoList();
  },

  toCheckInList() { wx.navigateTo({ url: '/pages/school/check-in' }); },
  toExam() { wx.navigateTo({ url: '/pages/school/exam' }); },
  toCertification() { wx.navigateTo({ url: '/pages/school/certification' }); },

  onSearchChange(e) { this.setData({ searchValue: e.detail.value }); },
  clearSearch() {
    this.setData({ searchValue: '', page: 1, videoList: [], finished: false });
    this.getVideoList();
  },
  onSearch() {
    this.setData({ page: 1, videoList: [], finished: false });
    this.getVideoList();
  }
});
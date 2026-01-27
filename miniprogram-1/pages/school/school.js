const app = getApp(); // 新增：获取全局app实例，用于获取Token

Page({
  data: {
    // 搜索相关
    searchValue: '',
    // 分类列表（对应后端course_type）
    categoryList: ['全部课程', '皮肤学', '四维三阶问题肌', '五维筋膜', '品牌篇', '产品篇', '家居解决方案'],
    activeTab: 0,
    categoryMap: {
      0: '', // 全部
      1: 1,  // 皮肤学
      2: 2,  // 四维三阶问题肌
      3: 3,  // 五维筋膜
      4: 4,  // 品牌篇
      5: 5,  // 产品篇
      6: 6   // 家居解决方案
    },
    // 视频列表
    videoList: [],
    loading: false,       // 加载状态
    finished: false,      // 是否无更多数据
    page: 1,              // 分页页码
    pageSize: 10          // 每页条数
  },

  onLoad() {
    // 页面加载时检查登录状态，未登录提示
    this.checkLoginStatus();
    // 加载初始视频列表
    this.getVideoList();
  },

  // 新增：检查登录状态（未登录提示并可选跳转）
  checkLoginStatus() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showModal({
        title: '提示',
        content: '查看课程需要先登录',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        }
      });
    }
  },

  // 原生下拉刷新
  onPullDownRefresh() {
    // 重置数据
    this.setData({
      page: 1,
      videoList: [],
      finished: false
    });
    this.getVideoList(() => {
      wx.stopPullDownRefresh(); // 停止下拉刷新动画
    });
  },

  // 原生上拉加载
  onReachBottom() {
    // 若正在加载或已无更多数据，不触发
    if (this.data.loading || this.data.finished) return;
    // 页码+1，加载更多
    this.setData({ page: this.data.page + 1 });
    this.getVideoList();
  },

  // 搜索框输入变化
  onSearchChange(e) {
    this.setData({ searchValue: e.detail.value });
  },

  // 清空搜索框
  clearSearch() {
    this.setData({ searchValue: '' });
    // 清空后重新加载全部数据
    this.setData({
      page: 1,
      videoList: [],
      finished: false
    });
    this.getVideoList();
  },

  // 执行搜索
  onSearch() {
    this.setData({
      page: 1,
      videoList: [],
      finished: false
    });
    this.getVideoList();
  },

  // 分类标签切换（强化参数传递）
  onTabChange(e) {
    const index = e.currentTarget.dataset.index;
    const categoryId = this.data.categoryMap[index];
    console.log('切换分类：', this.data.categoryList[index], '分类ID：', categoryId); // 打印分类ID，便于调试
    this.setData({
      activeTab: index,
      page: 1,
      videoList: [],
      finished: false
    });
    
    // 强制触发请求，确保参数传递
    this.getVideoList();
  },

  // 获取视频列表（核心修复：携带Token+处理401+优化解析）
  getVideoList(callback) {
    const { page, pageSize, activeTab, searchValue } = this.data;
    const categoryId = this.data.categoryMap[activeTab];
    // 1. 获取Token（统一来源）
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    // 2. 构建请求头（携带Token，空值保护）
    const header = {
      'content-type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
    };

    // 打印请求参数，便于调试
    console.log("===== 视频列表请求调试 =====");
    console.log("Token是否存在：", accessToken ? "是" : "否");
    console.log("请求头：", header);
    console.log("请求参数：", {
      page,
      page_size: pageSize,
      category: categoryId,
      search: searchValue.trim()
    });

    this.setData({ loading: true });

    wx.request({
      url: 'http://localhost:8000/app01/video_categories/',
      method: 'GET',
      header: header, // 核心：携带Token
      data: {
        page,
        page_size: pageSize,
        category: categoryId,
        search: searchValue.trim()
      },
      timeout: 5000,
      success: (res) => {
        console.log('视频列表返回：', res.data); // 打印原始数据，确认格式
        
        // 核心：处理401错误（Token过期/无效）
        if (res.statusCode === 401 || (res.data && res.data.detail === "身份认证信息未提供")) {
          // 清除无效Token，重置登录状态
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          app.globalData.isLogin = false;
          // 提示并跳转登录
          wx.showModal({
            title: '登录过期',
            content: '您的登录已过期，请重新登录',
            showCancel: false,
            success: () => {
              wx.navigateTo({ url: '/pages/login/login' });
            }
          });
          this.setData({ videoList: [], finished: true });
          return;
        }

        // ========== 优化：适配多种后端返回格式 ==========
        let newList = [];
        // 格式1：自定义返回（code=200 + data字段）
        if (res.data && res.data.code === 200) {
          // 兼容分页数据（results）或直接列表
          newList = res.data.data.results || res.data.data || [];
        }
        // 格式2：DRF默认分页返回（有results字段）
        else if (res.data && res.data.results) {
          newList = res.data.results;
        }
        // 格式3：直接返回列表（无分页）
        else if (Array.isArray(res.data)) {
          newList = res.data;
        }

        // 更新列表数据
        if (Array.isArray(newList)) {
          this.setData({
            videoList: [...this.data.videoList, ...newList],
            // 分页判断：返回数据少于每页条数，说明无更多
            finished: newList.length < pageSize
          });
        } else {
          wx.showToast({
            title: '课程数据格式错误',
            icon: 'none'
          });
        }
      },
      fail: (err) => {
        console.error('视频列表请求失败：', err);
        wx.showToast({
          title: '网络错误，无法加载课程',
          icon: 'none'
        });
        this.setData({ finished: true }); // 加载失败，标记无更多
      },
      complete: () => {
        this.setData({ loading: false });
        callback && callback();
      }
    });
  },

  // 跳转视频播放页（修复URL错误+携带Token）
  toVideoPlay(e) {
    const videoId = e.currentTarget.dataset.id;
    if (!videoId) {
      wx.showToast({ title: '无效的视频ID', icon: 'none' });
      return;
    }

    // 1. 检查登录状态
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }

    // 2. 修复URL错误：localhost后补充:8000
    wx.request({
      url: `http://localhost:8000/app01/video_categories/${videoId}/add_play_count/`,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      fail: (err) => {
        console.error('增加播放次数失败：', err);
      }
    });

    // 3. 跳转播放页
    wx.navigateTo({
      url: `/pages/school/play?id=${videoId}`,
      fail: (err) => {
        console.error('跳转视频播放页失败：', err);
        wx.showToast({ title: '播放页不存在', icon: 'none' });
      }
    });
  },

  // 跳转课程学习页（同视频播放）
  toStudy(e) {
    this.toVideoPlay(e);
  },

  // 跳转打卡列表页（检查登录）
  toCheckInList() {
    if (!this.checkLoginStatusQuick()) return;
    wx.navigateTo({ url: '/pages/school/check-in' });
  },

  // 跳转考核页（检查登录）
  toExam() {
    if (!this.checkLoginStatusQuick()) return;
    wx.navigateTo({ url: '/pages/school/exam' });
  },

  // 跳转线下认证页（检查登录）
  toCertification() {
    if (!this.checkLoginStatusQuick()) return;
    wx.navigateTo({ url: '/pages/school/certification' });
  },

  // 新增：快速检查登录状态（无弹窗，返回布尔值）
  checkLoginStatusQuick() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      wx.navigateTo({ url: '/pages/login/login' });
      return false;
    }
    return true;
  }
});
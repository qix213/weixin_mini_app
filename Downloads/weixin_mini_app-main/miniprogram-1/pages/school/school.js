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
    // 页面加载时获取初始视频列表
    this.getVideoList();
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
  // console.log('切换分类：', this.data.categoryList[index], '分类ID：', categoryId); // 打印分类ID，便于调试
  this.setData({
    activeTab: index,
    page: 1,
    videoList: [],
    finished: false
  });
  
  // 强制触发请求，确保参数传递
  this.getVideoList();
},

  // 获取视频列表（对接后端接口）
getVideoList(callback) {
  const { page, pageSize, activeTab, searchValue } = this.data;
  const categoryId = this.data.categoryMap[activeTab];
  // 打印请求参数，确认分类ID是否正确传递
  // console.log('请求参数：', {
  //   page,
  //   page_size: pageSize,
  //   category: categoryId,
  //   search: searchValue.trim()
  // });

  this.setData({ loading: true });

  wx.request({
    url: 'http://localhost:8000/app01/video_categories/',
    method: 'GET',
    data: {
      page,
      page_size: pageSize,
      category: categoryId,
      search: searchValue.trim()
    },
    timeout: 5000,
    success: (res) => {
      console.log('视频列表返回：', res.data); // 打印原始数据，确认格式
      
      // ========== 核心修改：适配两种后端返回格式 ==========
      let newList = [];
      // 格式1：DRF默认分页返回（有results字段）
      if (res.data.results) {
        newList = res.data.results;
      }
      // 格式2：自定义返回（code=200 + data字段）
      else if (res.data.code === 200 && res.data.data) {
        newList = res.data.data;
      }
      // 格式3：直接返回列表（无分页）
      else if (Array.isArray(res.data)) {
        newList = res.data;
      }

      // 有数据则更新列表，无数据才提示失败
      if (newList.length >= 0) { // 即使空列表也不提示失败
        this.setData({
          videoList: [...this.data.videoList, ...newList],
          finished: newList.length < pageSize
        });
      } else {
        wx.showToast({
          title: '课程加载失败',
          icon: 'none'
        });
      }
    },
    fail: (err) => {
      console.error('请求失败：', err);
      wx.showToast({
        title: '网络错误，无法加载课程',
        icon: 'none'
      });
    },
    complete: () => {
      this.setData({ loading: false });
      callback && callback();
    }
  });
},
  // 跳转视频播放页
  toVideoPlay(e) {
    const videoId = e.currentTarget.dataset.id;
    // 增加播放次数
    wx.request({
      url: `http://localhost/app01/video_categories/${videoId}/add_play_count/`,
      method: 'POST'
    });
    // 跳转播放页
    wx.navigateTo({
      url: `/pages/school/play?id=${videoId}`
    });
  },

  // 跳转课程学习页（同视频播放）
  toStudy(e) {
    this.toVideoPlay(e);
  },

  // 跳转打卡列表页
  toCheckInList() {
    wx.navigateTo({ url: '/pages/school/check-in' });
  },

  // 跳转考核页
  toExam() {
    wx.navigateTo({ url: '/pages/school/exam' });
  },

  // 跳转线下认证页
  toCertification() {
    wx.navigateTo({ url: '/pages/school/certification' });
  }
});
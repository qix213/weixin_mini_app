const app = getApp();

Page({
  data: {
    searchValue: '',
    
    // 菜单状态
    activeMenu: 'brand',     // brand, course, exam, cert
    isCourseExpanded: false, // 课程菜单折叠状态
    activeSubCategory: '',  // 当前选中的课程子分类
    
    // 动态分类与数据
    allVideoData: [],        // 缓存所有数据
    courseCategories: [],    // 动态课程分类
    videoList: [],           // 当前右侧显示的视频
    currentCategoryVideos: [], // 缓存当前选中分类下的完整视频列表
    currentPage: 1,            // 当前页码
    pageSize: 8,               // 每次滚动到底部，渲染几个视频？
    loading: false,       
    finished: false
  },

  onLoad() {
    if (!this.checkLoginStatus()) return;
    this.getVideoList();
  },

  onShow() {
    if (this.data.videoList.length === 0) {
      this.getVideoList();
    }
  },

  checkLoginStatus() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
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

  // 智能补全视频域名
  formatVideoUrl(url) {
    if (!url) return '';
    let finalUrl = url.trim().split('#')[0];
    if (!finalUrl.startsWith('http')) {
      if (!finalUrl.startsWith('/')) finalUrl = '/' + finalUrl;
      finalUrl = `https://video.lansik2026.com${finalUrl}`;
    }
    return finalUrl;
  },

  // 获取视频列表
  getVideoList() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    this.setData({ loading: true });

    wx.request({
      // 强行索要 1000 条，打破分页
      url: `${app.globalData.baseUrl}/app01/video_courses/?limit=1000&page_size=1000`,
      method: 'GET',
      header: { 'Authorization': `Bearer ${accessToken}` },
      success: (res) => {

        let results = [];
        if (Array.isArray(res.data)) {
          results = res.data;
        } else {
          results = res.data?.results || res.data?.data || [];
        }

        // 前端强制排序
        results.sort((a, b) => {
          const orderA = a.sort_order !== undefined && a.sort_order !== null ? a.sort_order : 999;
          const orderB = b.sort_order !== undefined && b.sort_order !== null ? b.sort_order : 999;
          return orderA - orderB; 
        });

        // 提取分类
        const allCats = [...new Set(results.map(v => v.category))];
        const courseCats = allCats.filter(c => c !== '品牌溯源' && c);

        const formattedResults = results.map(v => ({
          ...v,
          fullVideoUrl: this.formatVideoUrl(v.video_url) 
        }));

        this.setData({
          allVideoData: formattedResults,
          courseCategories: courseCats,
          loading: false
        });

        // 默认加载品牌溯源
        this.filterVideos(this.data.activeSubCategory || '品牌溯源');
      },
      fail: (err) => {
        console.error('获取视频列表接口报错:', err);
        this.setData({ loading: false });
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  },

  // 分页过滤逻辑
  filterVideos(categoryName) {
    const filtered = this.data.allVideoData.filter(v => v.category === categoryName);
    
    this.setData({
      currentCategoryVideos: filtered,
      currentPage: 1,
      videoList: filtered.slice(0, this.data.pageSize), 
      finished: filtered.length <= this.data.pageSize
    });
  },

  // 左侧主菜单点击
  handleMainMenuClick(e) {
    const menuId = e.currentTarget.dataset.id;
    
    if (menuId === 'course') {
      const willExpand = !this.data.isCourseExpanded;
      this.setData({ isCourseExpanded: willExpand });

      if (willExpand && this.data.courseCategories.length > 0) {
        this.handleSubCategoryClick({ currentTarget: { dataset: { name: this.data.courseCategories[0] } } });
      }
    } else if (menuId === 'brand') {
      this.setData({ activeMenu: 'brand', isCourseExpanded: false, activeSubCategory: '' });
      this.filterVideos('品牌溯源');
    } else if (menuId === 'exam') {
      wx.navigateTo({ url: '/pages/school/exam' });
    } else if (menuId === 'cert') {
      wx.navigateTo({ url: '/pages/school/certification' });
    }
  },

  // 子分类点击
  handleSubCategoryClick(e) {
    const subName = e.currentTarget.dataset.name;
    this.setData({ activeMenu: 'course', activeSubCategory: subName });
    this.filterVideos(subName);
  },

  // 播放视频
  toVideoPlay(e) {
    const videoId = e.currentTarget.dataset.id;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/check_permission/`,
      method: 'GET',
      header: { 'Authorization': `Bearer ${accessToken}` },
      success: (res) => {
        if (res.data?.has_permission && res.data?.video_url) {
          wx.navigateTo({
            url: `/pages/school/play?id=${videoId}&videoUrl=${encodeURIComponent(res.data.video_url)}`
          });
          this.updatePlayCount(videoId);
        } else {
          wx.showToast({ title: '获取权限失败', icon: 'none' });
        }
      }
    });
  },

  updatePlayCount(videoId) {
    const token = wx.getStorageSync('accessToken');
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/add_play_count/`,
      method: 'POST',
      header: { 'Authorization': `Bearer ${token}` }
    });
  },

  // 滑动到底部加载更多
  loadMoreVideos() {
    if (this.data.finished || this.data.loading) return;

    const nextPage = this.data.currentPage + 1;
    const currentTotal = this.data.currentCategoryVideos.length;
    const nextShowCount = nextPage * this.data.pageSize;

    this.setData({
      currentPage: nextPage,
      videoList: this.data.currentCategoryVideos.slice(0, nextShowCount),
      finished: nextShowCount >= currentTotal
    });
  },

  onSearchChange(e) { this.setData({ searchValue: e.detail.value }); },
  
  onSearch() {
    const kw = this.data.searchValue.toLowerCase();
    if (!kw) return;
    
    const filtered = this.data.allVideoData.filter(v => v.title.toLowerCase().includes(kw));
    this.setData({ 
      currentCategoryVideos: filtered,
      currentPage: 1,
      videoList: filtered.slice(0, this.data.pageSize),
      finished: filtered.length <= this.data.pageSize
    });
  },
  
  clearSearch() {
    this.setData({ searchValue: '' });
    this.filterVideos(this.data.activeSubCategory || '品牌溯源');
  }
});
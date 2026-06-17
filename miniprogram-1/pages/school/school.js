const app = getApp();

Page({
  data: {
    searchValue: '',
    
    // 菜单状态
    activeMenu: 'brand',     // brand, course, exam, cert
    isCourseExpanded: false, // 课程菜单折叠状态
    activeSubCategory: '',  // 当前选中的课程子分类
    
    // 动态分类与数据
    allVideoData: [],        // 🌟 核心：缓存所有数据，不再反复请求
    courseCategories: [],    // 动态课程分类
    videoList: [],           // 当前右侧显示的视频
    
    loading: false,       
    finished: false
  },

  onLoad() {
    if (!this.checkLoginStatus()) return;
    this.getVideoList();
  },

  onShow() {
    // 页面展示时如果没数据则加载
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

// 🌟 新增：智能补全视频域名（与 play.js 保持一致）
formatVideoUrl(url) {
  if (!url) return '';
  let finalUrl = url.trim().split('#')[0];
  if (!finalUrl.startsWith('http')) {
    if (!finalUrl.startsWith('/')) finalUrl = '/' + finalUrl;
    finalUrl = `https://video.lansik2026.com${finalUrl}`;
  }
  return finalUrl;
},

// 🌟 修改：一次性获取所有视频，并在前端解析出完整的视频 URL
getVideoList() {
  const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
  this.setData({ loading: true });

  wx.request({
    url: `${app.globalData.baseUrl}/app01/video_courses/`,
    method: 'GET',
    header: { 'Authorization': `Bearer ${accessToken}` },
    success: (res) => {
      const results = res.data?.results || res.data?.data || [];
      
      // 动态提取分类
      const allCats = [...new Set(results.map(v => v.category))];
      const courseCats = allCats.filter(c => c !== '品牌溯源' && c);

      // 🔥 核心修改：遍历数据，提前为列表页生成好视频的完整播放链接
      const formattedResults = results.map(v => ({
        ...v,
        // 假设后端的序列化器里有返回 video_url 字段
        fullVideoUrl: this.formatVideoUrl(v.video_url) 
      }));

      this.setData({
        allVideoData: formattedResults,
        courseCategories: courseCats,
        loading: false
      });

      // 默认加载品牌溯源
      this.filterVideos('品牌溯源');
    },
    fail: () => {
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  });
},
  // 🌟 2. 核心：前端过滤（不仅快，而且永远不会出现“所有分类混在一起”）
  filterVideos(categoryName) {
    const filtered = this.data.allVideoData.filter(v => v.category === categoryName);
    this.setData({
      videoList: filtered,
      finished: true // 前端过滤后即代表已加载全部
    });
  },

  // 🌟 3. 左侧主菜单点击逻辑
  handleMainMenuClick(e) {
    const menuId = e.currentTarget.dataset.id;
    
    if (menuId === 'course') {
      const willExpand = !this.data.isCourseExpanded;
      this.setData({ isCourseExpanded: willExpand });

      // 🔥 自动加载逻辑：展开课程菜单时，如果没选子分类，自动选中第一个
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

  // 🌟 4. 子分类点击逻辑
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

  onSearchChange(e) { this.setData({ searchValue: e.detail.value }); },
  onSearch() {
    const kw = this.data.searchValue.toLowerCase();
    const filtered = this.data.allVideoData.filter(v => v.title.toLowerCase().includes(kw));
    this.setData({ videoList: filtered });
  },
  clearSearch() {
    this.setData({ searchValue: '' });
    this.filterVideos(this.data.activeSubCategory || '品牌溯源');
  }
});
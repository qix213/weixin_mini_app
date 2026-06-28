// 顶部获取全局App实例
const app = getApp();

Page({
  data: {
    videoId: '',
    videoUrl: '',
    coverUrl: '',
    videoTitle: '',
    duration: '',
    playCount: 0,
    durationSeconds: 0,
    currentTime: 0,
    lastReportedTime: -3,
    isPlaying: false,
    canGetPoint: false,
    hasPermission: false, // 只要登录成功即为 true，用于渲染 WXML
    videoLoaded: false,
    isPlayIconHidden: false,
    finishReported: false
  },

  // 智能补全专属视频域名
  formatVideoUrl(url) {
    if (!url) return '';
    let finalUrl = url.trim().split('#')[0];
    if (!finalUrl.startsWith('http')) {
      if (!finalUrl.startsWith('/')) finalUrl = '/' + finalUrl;
      finalUrl = `https://video.lansik2026.com${finalUrl}`;
    }
    return finalUrl;
  },

  togglePlay() {
    if (!this.data.videoLoaded) {
      wx.showToast({ title: '视频还在加载中', icon: 'none' });
      return;
    }
    if (this.data.isPlaying) {
      this.videoContext.pause();
      this.setData({ isPlayIconHidden: false });
    } else {
      this.videoContext.play();
      this.setData({ isPlayIconHidden: true });
    }
  },

  onTimeUpdate(e) {
    const currentTime = Math.floor(e.detail.currentTime);
    const durationSeconds = this.data.durationSeconds;
    this.setData({ currentTime });

    if (this.data.isPlaying && Math.abs(currentTime - this.data.lastReportedTime) >= 3) {
      this.watchProgress(currentTime);
    }

    if (durationSeconds > 0 && !this.data.finishReported) {
      const progress = currentTime / durationSeconds;
      if (progress >= 0.99) {
        console.log(`【兜底触发】进度${(progress*100).toFixed(2)}%，调用watchFinish`);
        this.watchFinish();
      }
    }
  },

  onSeeked(e) {
    const currentTime = Math.floor(e.detail.currentTime);
    console.log('拖拽完成，定位到：', currentTime);
    if (currentTime < 1 && this.data.currentTime > 1) {
      this.videoContext.seek(this.data.currentTime);
      wx.showToast({ title: '进度定位中...', icon: 'none' });
    }
    this.watchProgress(this.data.currentTime);
  },

  onLoadedData(e) {
    if (e.detail.duration) {
      this.setData({ durationSeconds: Math.floor(e.detail.duration) });
    }
    this.setData({ 
      videoLoaded: true,
      isPlaying: false,
      isPlayIconHidden: false
    });
    wx.showToast({ title: '视频加载完成，点击播放开始观看', icon: 'none', duration: 2000 });
  },

  onFullScreenChange(e) {
    const tip = e.detail.fullScreen ? '进入全屏' : '退出全屏';
    wx.showToast({ title: tip, icon: 'none', duration: 1000 });
  },

  onReady() {
    this.videoContext = wx.createVideoContext('myVideo');
    this.videoContext.pause();
  },

  onLoad(options) {
    const videoId = options.id;
    const videoUrl = options.videoUrl ? decodeURIComponent(options.videoUrl) : '';
    
    if (!videoId) {
      wx.showToast({ title: '视频ID缺失', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
      return;
    }

    this.setData({ videoId });

    // 🌟 仅保留登录校验，移除所有等级映射判断
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showModal({
        title: '请先登录',
        content: '观看视频需要先登录账号',
        showCancel: false,
        confirmText: '去登录',
        success: () => wx.navigateBack()
      });
      return;
    }

    this.initVideoData(videoId, videoUrl);
  },

  // 🌟 初始化数据流：获取链接 -> 增加播放量 -> 取详情 -> 开始记录
  initVideoData(videoId, fallbackUrl) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;

    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/check_permission/`,
      method: 'GET',
      header: { 'Authorization': `Bearer ${accessToken}` },
      success: (res) => {
        // 直接读取后端拼接好的 URL
        const rawUrl = this.formatVideoUrl(res.data?.video_url || fallbackUrl);
        
        this.setData({
          hasPermission: true, // 登录即放行
          videoUrl: rawUrl
        });

        this.addPlayCount(videoId, () => {
          this.getVideoDetail(videoId);
          this.watchStart();
        });
      },
      fail: () => {
        wx.showToast({ title: '获取视频失败，请重试', icon: 'none' });
        setTimeout(() => wx.navigateBack(), 1500);
      }
    });
  },

  addPlayCount(videoId, callback) {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/add_play_count/`,
      method: 'POST',
      header: this.getHeader(),
      success: (res) => {
        if (res.data.code === 200) {
          this.setData({ playCount: res.data.play_count });
        }
      },
      complete: () => callback && callback()
    });
  },

  getVideoDetail(videoId) {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/`,
      method: 'GET',
      header: this.getHeader(),
      success: (res) => {
        if (!res.data) return;

        let coverUrl = res.data.cover_url || '';
        coverUrl = coverUrl ? this.formatVideoUrl(coverUrl) : '/images/default-cover.png';

        this.setData({
          coverUrl: coverUrl,
          videoTitle: res.data.title || '未知课程',
          duration: res.data.duration || '未知时长',
          playCount: res.data.play_count || 0,
          durationSeconds: res.data.duration_seconds || 0
        });
      }
    });
  },

  toCheckIn() {
    if (!this.data.hasPermission) return;
    wx.navigateTo({
      url: `/pages/school/check-in-form?courseId=${this.data.videoId}&courseTitle=${encodeURIComponent(this.data.videoTitle)}`
    });
  },

  toExam() {
    if (!this.data.hasPermission) return;
    // 🌟 移除依据等级动态跳转考核的逻辑，统一传递默认类型或直接传递标题
    wx.navigateTo({
      url: `/pages/school/exam?courseTitle=${encodeURIComponent(this.data.videoTitle)}`
    });
  },

  goBack() {
    wx.navigateBack();
  },

  getHeader() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    return {
      'content-type': 'application/json',
      'Authorization': accessToken ? `Bearer ${accessToken}` : ''
    };
  },

  watchStart() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${this.data.videoId}/watch_start/`,
      method: 'POST',
      header: this.getHeader()
    });
  },

  watchProgress(currentTime) {
    if (!this.data.hasPermission || !currentTime) return;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${this.data.videoId}/watch_progress/`,
      method: 'POST',
      header: this.getHeader(),
      data: { current_time: currentTime },
      success: res => {
        if (res.data?.invalid) {
          wx.showToast({ title: res.data.msg, icon: 'none' });
          this.videoContext.pause();
        } else {
          this.setData({ lastReportedTime: currentTime });
        }
      }
    });
  },

  watchFinish() {
    if (this.data.finishReported) return;
    
    wx.request({
      url: `${app.globalData.baseUrl}/app01/video_courses/${this.data.videoId}/watch_finish/`,
      method: 'POST',
      header: this.getHeader(),
      data: { video_duration: this.data.durationSeconds },
      success: res => {
        this.setData({ finishReported: true });
        wx.showToast({ 
          title: res.data.msg, 
          icon: res.data.code === 200 ? 'success' : 'none' 
        });
        if (res.data.code === 200) {
          this.setData({ canGetPoint: true });
        }
      }
    });
  },

  onPlay() {
    this.setData({ 
      isPlaying: true,
      isPlayIconHidden: true 
    });
  },

  onPause() {
    this.setData({ 
      isPlaying: false,
      isPlayIconHidden: false 
    });
    this.watchProgress(this.data.currentTime);
  },

  onEnded() {
    this.onPause();
    this.watchFinish();
  },

  onVideoError(e) {
    console.error('视频播放错误：', e.detail);
    wx.showModal({
      title: '有点小问题呢',
      content: '您的网络状态不佳，请检查网络配置后重试。',
      showCancel: false,
      confirmText: '我知道了'
    });
  },

  onUnload() {
    this.setData({ isPlaying: false });
    this.videoContext?.pause();
  },

  onHide() {
    this.onPause();
  },

  onShow() {
    this.setData({ isPlaying: false });
    this.videoContext?.pause();
  }
});
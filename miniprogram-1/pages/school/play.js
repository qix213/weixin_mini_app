// 顶部获取全局App实例
const app = getApp();

Page({
  data: {
    videoId: '',
    videoUrl: '',
    coverUrl: '',
    videoTitle: '',
    requiredLevelName: '',
    requiredLevel: 1,
    userLevel: 1,
    userLevelName: '',
    duration: '',
    playCount: 0,
    durationSeconds: 0,
    currentTime: 0,
    lastReportedTime: -3,
    isPlaying: false,
    canGetPoint: false,
    hasPermission: false,
    videoLoaded: false,
    isPlayIconHidden: false,
    finishReported: false
  },

  formatVideoUrl(url) {
    if (!url || !url.startsWith('http')) return '';
    return url.split('#')[0].trim();
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
    console.log('全屏状态变化：', e.detail.fullScreen);
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
      wx.navigateBack();
      return;
    }

    this.setData({ videoId });

    const userInfo = wx.getStorageSync('userInfo') || {};
    const userType = userInfo.user_type || 1;
    const levelNameMap = {
      1: "蓝朋友", 2: "蓝明星", 3: "护肤私教", 4: "MINI-studio 主理人", 5: "Ta创+"
    };
    this.setData({
      userLevel: userType,
      userLevelName: userInfo.user_type_name || levelNameMap[userType] || "未知等级"
    });

    console.log('加载视频详情，ID：', videoId);
    
    this.checkPlayPermission(videoId, (hasPermission, videoUrlFromCheck, requiredLevelName) => {
      if (!hasPermission) {
        wx.showModal({
          title: '权限不足',
          content: `很抱歉，观看该视频需要升级到${requiredLevelName || '未知等级'}及以上会员等级`,
          showCancel: false,
          confirmText: '返回',
          success: () => wx.navigateBack()
        });
        return;
      }

      // 🔥 全局配置拼接代理接口
      const rawUrl = this.formatVideoUrl(videoUrlFromCheck || videoUrl);
      const proxyUrl = `${app.globalData.baseUrl}/app01/video_proxy/?url=${encodeURIComponent(rawUrl)}`;
      this.setData({
        hasPermission: true,
        videoUrl: proxyUrl,
        requiredLevelName: requiredLevelName || ''
      });

      this.addPlayCount(videoId, () => {
        this.getVideoDetail(videoId);
        this.watchStart();
      });
    });
  },

  checkPlayPermission(videoId, callback) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      callback(false, '', '未知等级');
      return;
    }

    wx.request({
      // 🔥 全局配置
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/check_permission/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      timeout: 5000,
      success: (res) => {
        console.log('权限校验返回：', res.data);
        const requiredLevelName = res.data?.required_level_name || '';
        callback(res.data?.has_permission || false, res.data?.video_url || '', requiredLevelName);
      },
      fail: (err) => {
        console.error('权限校验失败：', err);
        wx.showToast({ title: '权限校验失败，请重试', icon: 'none' });
        callback(false, '', '未知等级');
      }
    });
  },

  addPlayCount(videoId, callback) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    if (!accessToken) {
      callback && callback();
      return;
    }

    wx.request({
      // 🔥 全局配置
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/add_play_count/`,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      timeout: 5000,
      success: (res) => {
        console.log('播放次数更新结果：', res.data);
        if (res.data.code === 200) {
          this.setData({ playCount: res.data.play_count });
        }
      },
      fail: (err) => console.error('播放次数更新失败：', err),
      complete: () => callback && callback()
    });
  },

  getVideoDetail(videoId) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken || '';
    if (!accessToken) return;

    wx.request({
      // 🔥 全局配置
      url: `${app.globalData.baseUrl}/app01/video_courses/${videoId}/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      timeout: 5000,
      success: (res) => {
        console.log('视频详情返回：', res.data);
        if (!res.data) {
          wx.showToast({ title: '视频详情加载失败', icon: 'none' });
          return;
        }

        let coverUrl = res.data.cover_url || '';
        coverUrl = coverUrl ? this.formatVideoUrl(coverUrl) : '/images/default-cover.png';

        this.setData({
          coverUrl: coverUrl,
          videoTitle: res.data.title || '未知课程',
          requiredLevelName: this.data.requiredLevelName || res.data.required_level_name || '未知等级',
          requiredLevel: res.data.required_level || 1,
          duration: res.data.duration || '未知时长',
          playCount: res.data.play_count || 0,
          durationSeconds: res.data.duration_seconds || 0
        });
      },
      fail: () => wx.showToast({ title: '网络错误，无法加载视频', icon: 'none' })
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
    const levelMap = {
      '蓝明星': 2,
      '护肤私教': 3,
      'MINI-studio 主理人': 4,
      'Ta创+': 5
    };
    const courseType = levelMap[this.data.requiredLevelName] || 1;
    wx.navigateTo({
      url: `/pages/school/exam?courseType=${courseType}&courseTitle=${encodeURIComponent(this.data.videoTitle)}`
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
      // 🔥 全局配置
      url: `${app.globalData.baseUrl}/app01/video_courses/${this.data.videoId}/watch_start/`,
      method: 'POST',
      header: this.getHeader(),
      success: res => console.log('开始播放记录成功'),
      fail: err => console.error('开始播放记录失败：', err)
    });
  },

  watchProgress(currentTime) {
    if (!this.data.hasPermission || !currentTime) return;
    wx.request({
      // 🔥 全局配置
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
      },
      fail: err => console.error('进度上报失败：', err)
    });
  },

  watchFinish() {
    if (this.data.finishReported) return;
    
    wx.request({
      // 🔥 全局配置
      url: `${app.globalData.baseUrl}/app01/video_courses/${this.data.videoId}/watch_finish/`,
      method: 'POST',
      header: this.getHeader(),
      data: {
        video_duration: this.data.durationSeconds
      },
      success: res => {
        console.log('watchFinish接口返回：', res.data);
        this.setData({ finishReported: true });
        wx.showToast({ 
          title: res.data.msg, 
          icon: res.data.code === 200 ? 'success' : 'none' 
        });
        if (res.data.code === 200) {
          this.setData({ canGetPoint: true });
        }
      },
      fail: err => console.error('播放完成领奖失败：', err)
    });
  },

  onPlay() {
    this.setData({ 
      isPlaying: true,
      isPlayIconHidden: true 
    });
    console.log('视频开始播放，声音已开启');
  },

  onPause() {
    this.setData({ 
      isPlaying: false,
      isPlayIconHidden: false 
    });
    this.watchProgress(this.data.currentTime);
    console.log('视频暂停播放');
  },

  onEnded() {
    console.log('【事件触发】视频播放完成，调用watchFinish');
    this.onPause();
    this.watchFinish();
  },

  onVideoError(e) {
    console.error('视频播放错误：', e.detail);
    const errMsg = e.detail.errMsg || '未知错误';
    let tip = '视频加载失败，请检查：1. Django代理接口是否启动；2. 原始视频URL是否可访问';
    if (errMsg.includes('url not in domain list')) {
      tip = '请在微信开发者工具勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」';
    } else if (errMsg.includes('invalid format')) {
      tip = '视频格式错误，请确保为H.264+AAC编码的MP4格式';
    }
    wx.showModal({
      title: '视频播放错误',
      content: tip,
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
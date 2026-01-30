Page({
  data: {
    videoId: '',
    videoUrl: '',       // 视频播放地址（必须是完整HTTP地址）
    coverUrl: '',       // 封面地址
    videoTitle: '',
    requiredLevelName: '', // 视频所需最低会员等级名称
    requiredLevel: 1,    // 视频所需最低会员等级（数字）
    userLevel: 1,        // 当前用户会员等级
    userLevelName: '',   // 当前用户会员等级名称（移除默认值，避免误导）
    duration: '',
    playCount: 0,
    currentTime: 0,
    hasPermission: false // 是否有权限观看该视频
  },

  // 监听进度更新，记录当前时间
  onTimeUpdate(e) {
    this.setData({
      currentTime: e.detail.currentTime  // 实时记录播放进度
    });
  },

  // 监听拖拽完成，确认定位
  onSeeked(e) {
    console.log('拖拽完成，定位到：', e.detail.currentTime);
    // 若拖拽后跳回0，手动定位到记录的进度（兜底）
    if (e.detail.currentTime < 1 && this.data.currentTime > 1) {
      this.videoContext.seek(this.data.currentTime);
      wx.showToast({ title: '进度定位中...', icon: 'none' });
    }
  },

  onReady() {
    // 获取视频上下文，用于手动定位
    this.videoContext = wx.createVideoContext('myVideo');
  },

  onLoad(options) {
    const videoId = options.id;
    const videoUrl = options.videoUrl ? decodeURIComponent(options.videoUrl) : '';
    if (!videoId) {
      wx.showToast({ title: '视频ID缺失', icon: 'none' });
      wx.navigateBack();
      return;
    }

    // 1. 获取当前用户会员等级（从缓存/全局变量）
    const userInfo = wx.getStorageSync('userInfo') || {};
    const userType = userInfo.user_type || 1;
    // 新增：根据user_type自动映射等级名称（兜底逻辑）
    const levelNameMap = {
      1: "蓝朋友",
      2: "蓝明星",
      3: "护肤私教",
      4: "MINI-studio 主理人",
      5: "Ta创+"
    };
    // 优先用缓存的user_type_name，没有则自动映射
    const userLevelName = userInfo.user_type_name || levelNameMap[userType] || "未知等级";
    this.setData({
      videoId,
      userLevel: userType,
      userLevelName: userLevelName // 确保等级名称有值
    });

    console.log('加载视频详情，ID：', videoId);
    
    // 2. 先校验播放权限（防止直接通过URL访问播放页）
    this.checkPlayPermission(videoId, (hasPermission, videoUrlFromCheck, requiredLevelName) => {
      if (!hasPermission) {
        // 无权限：直接使用接口返回的等级名称，不依赖本地字段
        const levelName = requiredLevelName || '未知等级';
        wx.showModal({
          title: '权限不足',
          content: `很抱歉，观看该视频需要升级到${levelName}及以上会员等级`,
          showCancel: false,
          confirmText: '返回',
          success: () => {
            wx.navigateBack();
          }
        });
        return;
      }

      // 有权限：更新状态并加载视频
      this.setData({
        hasPermission: true,
        videoUrl: videoUrlFromCheck || videoUrl,
        requiredLevelName: requiredLevelName || '' // 提前赋值正确等级
      });

      // 3. 增加播放次数（确保次数更新）
      this.addPlayCount(videoId, () => {
        // 4. 次数更新后，请求视频详情
        this.getVideoDetail(videoId);
      });
    });
  },

  // 播放权限二次校验（核心优化：返回等级名称）
  checkPlayPermission(videoId, callback) {
    const accessToken = wx.getStorageSync('accessToken') || getApp().globalData.accessToken;
    wx.request({
      url: `http://localhost:8000/app01/video_courses/${videoId}/check_permission/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      success: (res) => {
        console.log('权限校验返回：', res.data); // 新增日志，方便排查
        const requiredLevelName = res.data?.required_level_name || '';
        if (res.data && res.data.has_permission) {
          // 有权限：返回true + 视频地址 + 等级名称
          callback(true, res.data.video_url, requiredLevelName);
        } else {
          // 无权限：返回false + 空地址 + 等级名称
          callback(false, '', requiredLevelName);
        }
      },
      fail: (err) => {
        console.error('权限校验失败：', err);
        wx.showToast({ title: '权限校验失败，请重试', icon: 'none' });
        callback(false, '', '未知等级'); // 兜底返回
      }
    });
  },

  // 单独封装增加播放次数的方法
  addPlayCount(videoId, callback) {
    const accessToken = wx.getStorageSync('accessToken') || getApp().globalData.accessToken;
    wx.request({
      url: `http://localhost:8000/app01/video_courses/${videoId}/add_play_count/`,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      success: (res) => {
        console.log('播放次数更新结果：', res.data);
        if (res.data.code === 200) {
          this.setData({ playCount: res.data.play_count });
        }
      },
      fail: (err) => {
        console.error('播放次数更新失败：', err);
      },
      complete: () => {
        callback && callback();
      }
    });
  },

  // 监听全屏状态变化
  onFullScreenChange(e) {
    console.log('全屏状态变化：', e.detail.fullScreen);
    if (e.detail.fullScreen) {
      wx.showToast({ title: '进入全屏', icon: 'none', duration: 1000 });
    } else {
      wx.showToast({ title: '退出全屏', icon: 'none', duration: 1000 });
    }
  },

  // 视频播放错误处理
  onVideoError(e) {
    console.error('视频渲染错误：', e.detail);
    wx.showToast({
      title: `视频播放错误：${e.detail.errMsg}`,
      icon: 'none',
      duration: 3000
    });
  },

  // 获取视频详情（优化等级默认值）
  getVideoDetail(videoId) {
    const accessToken = wx.getStorageSync('accessToken') || getApp().globalData.accessToken;
    wx.request({
      url: `http://localhost:8000/app01/video_courses/${videoId}/`,
      method: 'GET',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      success: (res) => {
        console.log('视频详情返回：', res.data);
        if (res.data) {
          // 校验视频地址是否有效
          const videoUrl = res.data.video_url;
          if (!videoUrl || !videoUrl.startsWith('http')) {
            wx.showToast({ title: '视频地址无效', icon: 'none' });
            return;
          }

          // 优化：优先使用已有的等级名称，无则用接口返回值，默认值改为未知等级
          const requiredLevelName = this.data.requiredLevelName || res.data.required_level_name || '未知等级';
          
          this.setData({
            videoUrl: this.data.videoUrl || videoUrl,
            coverUrl: res.data.cover_url || '',
            videoTitle: res.data.title || '未知课程',
            requiredLevelName: requiredLevelName, // 确保等级名称准确
            requiredLevel: res.data.required_level || 1,
            duration: res.data.duration || '未知时长',
            playCount: res.data.play_count || 0
          });
        } else {
          wx.showToast({ title: '视频详情加载失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.showToast({ title: '网络错误，无法加载视频', icon: 'none' });
      }
    });
  },

  // 跳转打卡页（可选）
  toCheckIn() {
    if (!this.data.hasPermission) return;
    wx.navigateTo({
      url: `/pages/school/check-in-form?courseId=${this.data.videoId}&courseTitle=${encodeURIComponent(this.data.videoTitle)}`
    });
  },

  // 跳转考核页（优化：适配会员等级逻辑）
  toExam() {
    if (!this.data.hasPermission) return;
    
    let courseType = 1;
    if (this.data.requiredLevelName === '蓝明星') courseType = 2;
    else if (this.data.requiredLevelName === '护肤私教') courseType = 3;
    else if (this.data.requiredLevelName === 'MINI-studio 主理人') courseType = 4;
    else if (this.data.requiredLevelName === 'Ta创+') courseType = 5;

    wx.navigateTo({
      url: `/pages/school/exam?courseType=${courseType}&courseTitle=${encodeURIComponent(this.data.videoTitle)}`
    });
  },

  // 返回上一页
  goBack() {
    wx.navigateBack();
  }
});
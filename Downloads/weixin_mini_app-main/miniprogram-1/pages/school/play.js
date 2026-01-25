Page({
  data: {
    videoId: '',
    videoUrl: '',       // 视频播放地址（必须是完整HTTP地址）
    coverUrl: '',       // 封面地址
    videoTitle: '',
    categoryName: '',
    duration: '',
    playCount: 0,
    currentTime: 0
  },
  // 新增：监听进度更新，记录当前时间
  onTimeUpdate(e) {
    this.setData({
      currentTime: e.detail.currentTime  // 实时记录播放进度
    });
  },

  // 新增：监听拖拽完成，确认定位
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
    if (!videoId) {
        wx.showToast({ title: '视频ID缺失', icon: 'none' });
        wx.navigateBack();
        return;
    }

    this.setData({ videoId });
    console.log('加载视频详情，ID：', videoId);
    
    // 1. 先调用「增加播放次数」接口（确保次数更新）
    this.addPlayCount(videoId, () => {
        // 2. 次数更新后，再请求视频详情
        this.getVideoDetail(videoId);
    });
},

// 新增：单独封装增加播放次数的方法
addPlayCount(videoId, callback) {
  wx.request({
      url: `http://localhost:8000/app01/video_categories/${videoId}/add_play_count/`,
      method: 'POST',
      success: (res) => {
          console.log('播放次数更新结果：', res.data);
          if (res.data.code === 200) {
              // 记录最新播放次数（供局部更新用）
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
// 新增：监听全屏状态变化
onFullScreenChange(e) {
    console.log('全屏状态变化：', e.detail.fullScreen); // true=全屏，false=退出
    if (e.detail.fullScreen) {
        wx.showToast({ title: '进入全屏', icon: 'none', duration: 1000 });
    } else {
        wx.showToast({ title: '退出全屏', icon: 'none', duration: 1000 });
    }
},
onVideoError(e) {
  console.error('视频渲染错误：', e.detail);
  // 错误码说明：
  // 10001: 视频格式不支持 | 10002: 视频解码失败 | 10003: 视频网络错误
  wx.showToast({
    title: `视频播放错误：${e.detail.errMsg}`,
    icon: 'none',
    duration: 3000
  });
},
  // 获取视频详情（关键：确保video_url是完整可访问地址）
  getVideoDetail(videoId) {
    wx.request({
      url: `http://localhost:8000/app01/video_categories/${videoId}/`,
      method: 'GET',
      success: (res) => {
        console.log('视频详情返回：', res.data);
        if (res.data) {
          // 校验视频地址是否有效
          const videoUrl = res.data.video_url;
          if (!videoUrl || !videoUrl.startsWith('http')) {
            wx.showToast({
              title: '视频地址无效',
              icon: 'none'
            });
            return;
          }

          this.setData({
            videoUrl: videoUrl,
            coverUrl: res.data.cover_url || '',
            videoTitle: res.data.title || '未知课程',
            categoryName: res.data.category_name || '未知分类',
            duration: res.data.duration || '未知时长',
            playCount: res.data.play_count || 0
          });
        } else {
          wx.showToast({
            title: '视频详情加载失败',
            icon: 'none'
          });
        }
      },
      fail: () => {
        wx.showToast({
          title: '网络错误，无法加载视频',
          icon: 'none'
        });
      }
    });
  },

  // 跳转打卡页（可选）
  toCheckIn() {
    wx.navigateTo({
      url: `/pages/school/check-in-form?courseId=${this.data.videoId}&courseTitle=${this.data.videoTitle}`
    });
  },

  // 跳转考核页（可选）
  toExam() {
    let courseType = 1;
    if (this.data.categoryName === '四维三阶问题肌') courseType = 2;
    else if (this.data.categoryName === '五维筋膜') courseType = 3;
    else if (this.data.categoryName === '品牌篇') courseType = 4;
    else if (this.data.categoryName === '产品篇') courseType = 5;
    else if (this.data.categoryName === '家居解决方案') courseType = 6;

    wx.navigateTo({
      url: `/pages/school/exam?courseType=${courseType}`
    });
  }
});
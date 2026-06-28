import Toast from '@vant/weapp/toast/toast';
import Dialog from '@vant/weapp/dialog/dialog';
const app = getApp();

Page({
  data: {
    activeTab: 'assets',
    subActiveTab: 'pending',
    assetsList: [],
    pendingList: [],
    completedList: [],
    images: [],
    
    // 评价相关
    showReview: false,
    currentRecordId: null,
    reviewForm: {
      rating: 5,
      content: ''
    }
  },

  onLoad() {
    this.fetchAssets();
    this.fetchRecords();
  },

  onMainTabChange(e) {
    this.setData({ activeTab: e.detail.name });
  },

  onSubTabChange(e) {
    this.setData({ subActiveTab: e.detail.name });
  },

  // 1. 获取我的资产列表
  fetchAssets() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/offline_services/query_assets/`,
      header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
      success: (res) => {
        this.setData({ assetsList: res.data.data || [] });
      }
    });
  },

  // 2. 获取服务记录并分类 (待处理 status:0,1 / 已完成 status:2)
  fetchRecords() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/offline_services/`,
      header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
      success: (res) => {
        const records = res.data.data || res.data.results || res.data || [];
        const pending = records.filter(item => item.status === 0 || item.status === 1);
        const completed = records.filter(item => item.status === 2);
        this.setData({ 
          pendingList: pending,
          completedList: completed
        });
      }
    });
  },

  // 🌟 3. 客户确认核销
  confirmService(e) {
    const recordId = e.currentTarget.dataset.id;
    Dialog.confirm({
      title: '确认核销',
      message: '确定您已完成本次服务体验吗？确认后将扣除1次项目次数。',
      confirmButtonColor: '#94A48C'
    }).then(() => {
      Toast.loading({ message: '核销中...', forbidClick: true });
      wx.request({
        url: `${app.globalData.baseUrl}/app01/offline_services/${recordId}/confirm_service/`,
        method: 'POST',
        header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
        success: (res) => {
          if (res.data.code === 200) {
            Toast.clear(); // 清除 loading
            // 刷新列表和资产
            this.fetchRecords();
            this.fetchAssets();
            
            // 🌟 自动唤起评价弹窗，并重置表单（0星代表没选）
            this.setData({
              showReview: true,
              currentRecordId: recordId,
              reviewForm: { rating: 0, content: '', images: [] }
            });
          } else {
            Toast.fail(res.data.msg || '核销失败');
          }
        }
      });
    }).catch(() => {});
  },
  // 🌟 新增：客户点击自己上传的评价图片，全屏放大预览
  previewReviewImage(e) {
    const current = e.currentTarget.dataset.current; // 当前点的哪张
    const urls = e.currentTarget.dataset.urls;       // 这一组所有的图
    
    if (!urls || urls.length === 0) return;
    
    wx.previewImage({
      current: current, 
      urls: urls        
    });
  },
  afterReadImage(event) {
    const { file } = event.detail;
    Toast.loading({ message: '处理上传中...', forbidClick: true });

    // 封装上传核心
    const executeUpload = (finalFilePath) => {
      // 🌟 核心优化：上传前检查最终文件的体积大小
      wx.getFileInfo({
        filePath: finalFilePath,
        success: (infoRes) => {
          const fileSizeMB = infoRes.size / 1024 / 1024;
          console.log(`【前端检测】最终准备上传的文件大小为: ${fileSizeMB.toFixed(2)} MB`);

          // 如果文件依然大于 2MB（可以根据服务器承受能力调整）
          if (fileSizeMB > 15) {
            Toast.fail('照片超过18MB，请重新截屏或压缩后再试');
            return;
          }

          // 体积达标，正式发起请求
          wx.uploadFile({
            url: `${app.globalData.baseUrl}/app01/offline_services/upload_image/`,
            filePath: finalFilePath,
            name: 'file', 
            header: { 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
            success: (res) => {
              if (res.statusCode !== 200) {
                Toast.fail(`后端报错: ${res.statusCode}`);
                return;
              }
              try {
                const data = JSON.parse(res.data);
                if (data.code === 200) {
                  Toast.clear();
                  const { images = [] } = this.data.reviewForm;
                  images.push({ url: data.data.url }); 
                  this.setData({ 'reviewForm.images': images });
                } else {
                  Toast.fail(data.msg || '上传失败');
                }
              } catch (e) {
                Toast.fail('接口返回格式异常');
              }
            },
            fail: () => Toast.fail('网络或接口异常')
          });
        },
        fail: () => {
          // 获取文件信息失败时，直接尝试上传
          executeUpload直接执行(finalFilePath);
        }
      });
    };

    // 调用微信原生压缩引擎
    wx.compressImage({
      src: file.url,
      quality: 40, // 🌟 如果 70 依然大，可以考虑下调到 50 或 60，画质在手机屏上几乎无损
      success: (compressRes) => {
        executeUpload(compressRes.tempFilePath);
      },
      fail: (err) => {
        console.warn("图片压缩失败，降级原图检测", err);
        executeUpload(file.url);
      }
    });
  },

  // 🌟 核心新增：删除已选图片
  deleteImage(event) {
    const { index } = event.detail;
    const { images } = this.data.reviewForm;
    images.splice(index, 1);
    this.setData({ 'reviewForm.images': images });
  },

  onRateChange(e) { this.setData({ 'reviewForm.rating': e.detail }); },
  onReviewContentChange(e) { this.setData({ 'reviewForm.content': e.detail }); },
  closeReviewPopup() { this.setData({ showReview: false }); },
  // 🌟 4. 评价相关交互
  openReviewPopup(e) {
    this.setData({
      showReview: true,
      currentRecordId: e.currentTarget.dataset.id,
      reviewForm: { rating: 5, content: '', images: [] } 
    });
  },

  closeReviewPopup() {
    this.setData({ showReview: false });
  },

  onRateChange(e) {
    this.setData({ 'reviewForm.rating': e.detail });
  },

  onReviewContentChange(e) {
    this.setData({ 'reviewForm.content': e.detail });
  },

// 🌟 核心修改 2：提交评价（过滤掉未填写的项）
submitReview() {
  const recordId = this.data.currentRecordId;
  const { rating, content, images } = this.data.reviewForm;

  // 构建动态 payload (因为都是非必填，没填就不传)
  const payload = {};
  if (rating > 0) payload.rating = rating;
  if (content.trim()) payload.review_content = content;
  if (images.length > 0) payload.review_images = images.map(img => img.url); // 只提取 URL 数组传给后端

  // 如果用户什么都没填就点了提交，其实就等于“暂不评价”，直接关弹窗即可
  if (Object.keys(payload).length === 0) {
    this.closeReviewPopup();
    return;
  }

  Toast.loading({ message: '提交中...', forbidClick: true });
  wx.request({
    url: `${app.globalData.baseUrl}/app01/offline_services/${recordId}/submit_review/`,
    method: 'POST',
    header: { 
      'Authorization': `Bearer ${wx.getStorageSync('accessToken')}`,
      'content-type': 'application/json'
    },
    data: payload,
    success: (res) => {
      if (res.data.code === 200) {
        Toast.success('感谢您的反馈！');
        this.setData({ showReview: false });
        this.fetchRecords(); // 刷新列表，显示出刚写的评价
      } else {
        Toast.fail(res.data.msg || '提交失败');
      }
    }
  });
}
});
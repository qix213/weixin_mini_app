import api from '../../config/settings'
const app = getApp();

Page({
  data: {
    banner_list: [{ img: '' }], // 轮播图列表
    notice: 'xxx产品正在7折促销~', // 公告
    isLogin: false, // 登录状态标识
    fixed_images: [], // 固定图片列表
    content: '', // 公告内容
    userInfo: {}, // 用户信息（需包含nickname字段）
    loading: true // 加载状态
  },

  onLoad() {
    this.loadHomeData().finally(() => {
      this.setData({ loading: false });
    });
  },

  loadHomeData() {
    return Promise.all([
      this.fetchBannerData(), 
      this.fetchFixedImages()
    ]);
  },

  // 获取轮播图数据（保持原有修复逻辑）
  fetchBannerData() {
    return new Promise((resolve) => {
      wx.request({
        url: api.banner,
        method: 'GET',
        header: {
          'Content-Type': 'application/json'
        },
        success: (res) => {
          let bannerList = this.data.banner_list;
          let notice = this.data.notice;
          let content = this.data.content;

          const resCode = res.data?.code;
          const resBanner = res.data?.banner || {};
          const resNotice = res.data?.notice || {};

          if (resCode === 200) {
            bannerList = resBanner.results || resBanner || bannerList;
            notice = resNotice?.title || notice;
            content = resNotice?.content || content;
          } else if (res.data?.banner) {
            bannerList = resBanner.results || resBanner || bannerList;
            notice = resNotice?.title || notice;
            content = resNotice?.content || content;
          }

          bannerList = Array.isArray(bannerList) ? bannerList : this.data.banner_list;
          this.setData({
            banner_list: bannerList,
            notice,
            content
          });
          resolve();
        },
        fail: (error) => {
          console.error('轮播图/公告获取失败：', error);
          resolve();
        }
      });
    });
  },

  // 获取固定图片数据（保持原有修复逻辑）
  fetchFixedImages() {
    return new Promise((resolve) => {
      wx.request({
        url: api.base + '/app01/index_annonce/',
        method: 'GET',
        header: {
          'Content-Type': 'application/json'
        },
        success: (res) => {
          let fixedImages = [];
          if (res.data && res.data.code === 200) {
            const rawImages = res.data.fixed_images || [];
            fixedImages = rawImages.map(item => ({
              img: item?.img_url?.startsWith('http') ? item.img_url : `${api.base}${item?.img_url || item?.img || ''}`,
              id: item?.id || '',
              title: item?.title || ''
            }));
          } else if (res.data) {
            const rawImages = res.data.fixed_images || [];
            fixedImages = rawImages.map(item => ({
              img: item?.img_url?.startsWith('http') ? item.img_url : `${api.base}${item?.img_url || item?.img || ''}`,
              id: item?.id || ''
            }));
          }
          fixedImages = Array.isArray(fixedImages) ? fixedImages : [];
          this.setData({ fixed_images: fixedImages });
          resolve();
        },
        fail: (error) => {
          console.error('固定图片获取失败：', error);
          this.setData({ fixed_images: [] });
          resolve();
        }
      });
    });
  },

  handleClick01(event) {
    const imgId = event.currentTarget.dataset.id;
    if (imgId) {
      console.log('点击固定图片：', imgId);
    }
  },

  // 关键优化：页面显示时强制同步登录状态（确保切回页面立即更新）
  onShow() {
    this.syncGlobalUserState();
    // 额外触发一次渲染更新（防止状态同步但未渲染）
    this.setData({
      isLogin: app.globalData.isLogin || false,
      userInfo: app.globalData.userInfo || {}
    });
  },

  // 优化用户状态同步逻辑（增加日志+兜底）
  syncGlobalUserState() {
    const globalIsLogin = app.globalData.isLogin || false;
    const globalUserInfo = app.globalData.userInfo || {};
    // 兜底用户昵称（避免空值）
    globalUserInfo.nickname = globalUserInfo.nickname || globalUserInfo.username || globalUserInfo.name || '';
    
    console.log('当前全局登录状态：', globalIsLogin, '用户信息：', globalUserInfo);
    
    if (this.data.isLogin !== globalIsLogin || JSON.stringify(this.data.userInfo) !== JSON.stringify(globalUserInfo)) {
      this.setData({
        isLogin: globalIsLogin,
        userInfo: globalUserInfo
      });
      console.log('页面状态已更新：', this.data.isLogin, this.data.userInfo);
    }
  },

  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login'
    });
  },

  goToRegister() {
    wx.navigateTo({
      url: '/pages/register/register'
    });
  }
});
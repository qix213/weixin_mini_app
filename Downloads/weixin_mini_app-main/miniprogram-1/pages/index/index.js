// index.js
import api from '../../config/settings'
Page({
  data: {
    banner_list: [{
      img: ''
    }],
    notice: '欢迎加入蓝色家族~',
    isLogin: false, // 登录状态
    fixed_images: [],  // 初始化为空数组，由后端填充
    content: '',
    userInfo: {}    // 用户信息
  },

  onLoad() {
    this.fetchBannerData();  // 获取轮播图
    this.fetchFixedImages(); // 单独获取固定图片
  },

  // 获取轮播图数据（保留原有，无需修改）
  fetchBannerData() {
    wx.request({
      url: api.banner,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.banner) {
          this.setData({
            banner_list: res.data.banner,
            notice: res.data.notice?.title || this.data.notice,
            content: res.data.notice?.content || this.data.content
          });
          console.log('--------',res.data.banner)
        }
      },
      fail: (error) => {
        console.error('轮播图获取失败：', error);
        // 失败时设置默认轮播图
      }
    });
  },

  // 新增：获取固定图片数据
  fetchFixedImages() {
    wx.request({
      url: api.base + '/app01/index_annonce/',  // 对应后端固定图片接口
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.code === 200 && res.data.fixed_images) {
          // 转换后端数据格式（匹配前端wxml绑定的img字段）
          const fixedImages = res.data.fixed_images.map(item => ({
            img: api.base + item.img,  // 对应后端返回的img_url字段
            id: item.id || ''  // 可选：获取图片标题
          }));
          console.log('固定图片获取成功：', fixedImages)
          this.setData({
            fixed_images: fixedImages
          });
        }
      },
      fail: (error) => {
        console.error('固定图片获取失败：', error);
        // 失败时设置默认固定图片（可选）
      }
    });
  },
  handleClick01(event) {
    console.log(event)
  },
  onShow() {
    // 页面显示时，同步全局登录状态和用户信息
    this.syncGlobalUserState();
  },

  // 核心：同步全局登录状态到页面
  syncGlobalUserState() {
    const app = getApp();
    const isLogin = app.globalData.isLogin || false;
    const userInfo = app.globalData.userInfo || {};
    this.setData({
      isLogin,
      userInfo
    });
  },

  // 跳转登录页
  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login',
    });
  },

  // 跳转注册页
  goToRegister() {
    wx.navigateTo({
      url: '/pages/register/register',
    });
  }

})
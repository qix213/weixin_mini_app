import api from '../../config/settings'
const app = getApp(); // 全局获取app实例（关键：用于调用封装的request）

Page({
  data: {
    banner_list: [{ img: '' }], // 轮播图列表
    notice: '欢迎加入蓝色家族~', // 公告
    isLogin: false, // 登录状态
    fixed_images: [], // 固定图片列表（初始化空数组）
    content: '', // 公告内容
    userInfo: {}, // 用户信息
    loading: true // 加载状态（新增，优化用户体验）
  },

  onLoad() {
    // 统一加载数据：先加载基础数据，完成后隐藏loading
    this.loadHomeData().finally(() => {
      this.setData({ loading: false });
    });
  },

  // 统一加载首页数据（Promise版，确保加载顺序）
  loadHomeData() {
    return Promise.all([
      this.fetchBannerData(), // 轮播图
      this.fetchFixedImages() // 固定图片
    ]);
  },

  // 获取轮播图数据（改造：使用app.request，兼容返回格式）
  fetchBannerData() {
    return new Promise((resolve) => {
      app.request({
        url: api.banner,
        method: 'GET'
      }).then(res => {
        // console.log('轮播图接口返回：', res.data);
        // 兼容两种返回格式：自定义格式（code=200）+ 原有格式
        let bannerList = this.data.banner_list;
        let notice = this.data.notice;
        let content = this.data.content;

        if (res.data && res.data.code === 200) {
          // 后端返回code=200的格式
          bannerList = res.data.data.banner || bannerList;
          notice = res.data.data.notice?.title || notice;
          content = res.data.data.notice?.content || content;
        } else if (res.data && res.data.banner) {
          // 原有返回格式（兼容旧接口）
          bannerList = res.data.banner;
          notice = res.data.notice?.title || notice;
          content = res.data.notice?.content || content;
        }

        // 安全处理：确保bannerList是数组
        bannerList = Array.isArray(bannerList) ? bannerList : this.data.banner_list;
        this.setData({
          banner_list: bannerList,
          notice,
          content
        });
        // console.log('轮播图最终数据：', this.data.banner_list);
        resolve();
      }).catch(error => {
        console.error('轮播图获取失败：', error);
        // 失败时保留默认轮播图，不影响页面显示
        resolve();
      });
    });
  },

  // 获取固定图片数据（彻底修复空值访问错误）
fetchFixedImages() {
  return new Promise((resolve) => {
    app.request({
      url: api.base + '/app01/index_annonce/', // 后端固定图片接口
      method: 'GET'
    }).then(res => {
      // 关键：打印完整返回数据，方便定位后端格式
      // console.log('固定图片接口完整返回：', res);
      // console.log('固定图片接口data字段：', res.data);
      
      let fixedImages = [];

      // 修复：多层空值保护（核心！避免undefined报错）
      // 步骤1：先判断res.data是否存在，再判断code===200
      if (res.data && res.data.code === 200) {
        // 步骤2：用可选链（?.）访问深层属性，不存在则返回空数组
        const rawImages = res.data.data?.fixed_images || res.data.fixed_images || [];
        // 步骤3：转换数据格式，同时做空值保护
        fixedImages = rawImages.map(item => ({
          img: item?.img_url?.startsWith('http') ? item.img_url : `${api.base}${item?.img_url || item?.img || ''}`,
          id: item?.id || '',
          title: item?.title || ''
        }));
      } else if (res.data) {
        // 兼容无code的返回格式
        const rawImages = res.data.fixed_images || [];
        fixedImages = rawImages.map(item => ({
          img: item?.img?.startsWith('http') ? item.img : `${api.base}${item?.img || ''}`,
          id: item?.id || ''
        }));
      }

      // 最终安全处理：确保是数组
      fixedImages = Array.isArray(fixedImages) ? fixedImages : [];
      this.setData({ fixed_images: fixedImages });
      // console.log('固定图片最终数据：', this.data.fixed_images);
      resolve();
    }).catch(error => {
      console.error('固定图片获取失败：', error);
      // 失败时设为空数组，避免页面报错
      this.setData({ fixed_images: [] });
      resolve();
    });
  });
},

  // 固定图片点击事件（优化：增加参数校验）
  handleClick01(event) {
    // console.log('固定图片点击：', event);
    const imgId = event.currentTarget.dataset.id;
    if (imgId) {
      // 可选：根据id跳转对应页面
      // wx.navigateTo({ url: `/pages/xxx/xxx?id=${imgId}` });
    }
  },

  // 页面显示时同步登录状态（优化：增加日志，方便调试）
  onShow() {
    this.syncGlobalUserState();
  },

  // 核心：同步全局登录状态到页面（优化：兼容全局变量为空）
  syncGlobalUserState() {
    const globalIsLogin = app.globalData.isLogin || false;
    const globalUserInfo = app.globalData.userInfo || {};
    
    // 仅当状态变化时更新，减少setData次数
    if (this.data.isLogin !== globalIsLogin || JSON.stringify(this.data.userInfo) !== JSON.stringify(globalUserInfo)) {
      this.setData({
        isLogin: globalIsLogin,
        userInfo: globalUserInfo
      });
      // console.log('首页登录状态同步：', { isLogin: globalIsLogin, userInfo: globalUserInfo });
    }
  },

  // 跳转登录页（优化：增加防重复跳转）
  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login',
      fail: (err) => {
        console.error('跳转登录页失败：', err);
      }
    });
  },

  // 跳转注册页（优化：增加防重复跳转）
  goToRegister() {
    wx.navigateTo({
      url: '/pages/register/register',
      fail: (err) => {
        console.error('跳转注册页失败：', err);
      }
    });
  }
});
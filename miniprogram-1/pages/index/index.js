import api from '../../config/settings'
const app = getApp();

Page({
  data: {
    banner_list: [{ img: '' }], 
    notice: 'xxx产品正在7折促销~', 
    isLogin: false, 
    fixed_images: [], 
    star_goods: [], 
    content: '', 
    userInfo: {}, 
    loading: true, 
    memberInfo: {}, 
    isAdminMember: false 
  },

  onLoad() {
    // 1. 初始化时同步基础状态
    this.syncGlobalUserState();
    
    // 2. 加载首页数据
    this.loadHomeData().finally(() => {
      this.setData({ loading: false });
    });
  },

  onShow() {
    this.syncGlobalUserState();
    // 如果已登录，拉取最新会员信息同步 nickname
    if (this.data.isLogin) {
      this.getMemberInfo();
    }
  },

  // 基础状态同步
  syncGlobalUserState() {
    const isLogin = app.globalData.isLogin;
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    const userType = Number(memberInfo.user_type || 0);
    
    this.setData({
      isLogin: isLogin,
      userInfo: memberInfo,
      memberInfo: memberInfo,
      isAdminMember: isLogin && [4, 5].includes(userType)
    });
  },

  // ========== 核心优化：使用封装的 app.request ==========

  /**
   * 拉取会员信息
   * 自动带上 Authorization 头，无需手动拼 header
   */
  getMemberInfo() {
    app.request({
      url: '/app01/member/info/', // 这里的路径会自动拼在 baseUrl 后面
      method: 'GET'
    }).then(res => {
      if (res.data.code === 200) {
        const memberInfo = res.data.data;
        app.globalData.memberInfo = memberInfo;
        wx.setStorageSync('memberInfo', memberInfo);

        const userType = Number(memberInfo.user_type || 0);
        this.setData({
          userInfo: memberInfo,
          memberInfo: memberInfo,
          isAdminMember: [4, 5].includes(userType)
        });
        console.log('✅ 会员信息同步成功');
      }
    }).catch(err => {
      console.error('❌ 会员信息同步失败：', err);
    });
  },

  loadHomeData() {
    // 并行加载所有数据
    return Promise.all([
      this.fetchBannerData(), 
      this.fetchFixedImages(),
      this.fetchStarGoods()
    ]);
  },

  /**
   * 获取明星产品
   */
  fetchStarGoods() {
    return app.request({
      url: '/app01/goods/',
      method: 'GET'
    }).then(res => {
      if (res.data && res.data.code === 200) {
        const allGoods = res.data.data.results || [];
        const starGoods = allGoods.filter(item => item.is_star).map(item => ({
          id: item.id,
          name: item.name,
          // 🌟 这里的 api.base 必须确保是 https://www.lansik2026.com
          image: item.image_url?.startsWith('http') ? item.image_url : `${app.globalData.baseUrl}${item.image_url || ''}`,
          price: item.member_price || item.price,
          original_price: item.original_price
        }));
        this.setData({ star_goods: starGoods });
      }
    }).catch(err => {
      console.error('❌ 获取明星产品失败：', err);
    });
  },

  /**
   * 获取轮播图及公告
   */
  fetchBannerData() {
    return app.request({
      url: api.banner
    }).then(res => {
      const resData = res.data;
      console.log('🐞 轮播图接口返回原始数据：', resData);

      if (resData.code === 100) {
        // 🌟 核心修改点：这里要取 resData.banner.results
        const bannerArray = resData.banner?.results || (Array.isArray(resData.banner) ? resData.banner : []);
        
        this.setData({ 
          banner_list: bannerArray, 
          notice: resData.notice?.title || this.data.notice,
          content: resData.notice?.content || ''
        });
        
        console.log('✅ 轮播图列表已更新为数组:', bannerArray);
      }
    }).catch(err => {
      console.error('❌ 获取轮播图失败：', err);
    });
  },
  /**
   * 获取首页宣传图
   */
  fetchFixedImages() {
    return app.request({
      url: '/app01/index_annonce/'
    }).then(res => {
      if (res.data && res.data.code === 200) {
        const rawImages = res.data.fixed_images || [];
        const fixedImages = rawImages.map(item => ({
          img: item?.img_url?.startsWith('http') ? item.img_url : `${app.globalData.baseUrl}${item?.img_url || item?.img || ''}`,
          id: item?.id || '',
          title: item?.title || ''
        }));
        this.setData({ fixed_images: fixedImages });
      }
    }).catch(err => {
      console.error('❌ 获取固定图失败：', err);
    });
  },

  // ========== 路由跳转保持不变 ==========
  goToOrderList() {
    if (!this.data.isAdminMember) {
      wx.showToast({ title: '暂无订单管理权限', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: '/pages/order-workbench/order-workbench' });
  },

  goToGoodsDetail(event) {
    const goodsId = event.currentTarget.dataset.goodsid;
    if (goodsId) wx.navigateTo({ url: `/pages/mall/detail?goods_id=${goodsId}` });
  },

  handleClick01(event) {
    const imgId = event.currentTarget.dataset.id;
    if (imgId) console.log('点击固定图片：', imgId);
  },

  goToLogin() { wx.navigateTo({ url: '/pages/login/login' }); },
  goToRegister() { wx.navigateTo({ url: '/pages/register/register' }); }
});
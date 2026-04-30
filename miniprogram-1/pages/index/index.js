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
    // 1. 初始化时先同步基础状态
    this.syncGlobalUserState();
    
    // 2. 根据状态加载对应数据
    if (this.data.isAdminMember) {
      this.fetchStarGoods().finally(() => {
        this.setData({ loading: false });
      });
    } else {
      this.loadHomeData().finally(() => {
        this.setData({ loading: false });
      });
    }
  },

  // 页面显示时触发
  onShow() {
    this.syncGlobalUserState();
    // 关键优化：如果已登录，主动去后台拉取最新的会员信息（包含nickname）
    if (this.data.isLogin) {
      this.getMemberInfo();
    }
  },

  // 基础同步：从全局或缓存读取状态
  syncGlobalUserState() {
    const cacheIsLogin = app.globalData.isLogin || wx.getStorageSync('isLogin') || false;
    let currentMemberInfo = app.globalData.memberInfo;
    
    if (!currentMemberInfo || Object.keys(currentMemberInfo).length === 0) {
      currentMemberInfo = wx.getStorageSync('memberInfo') || {};
    }

    const userType = Number(currentMemberInfo.user_type || 0);
    const isAdminMember = cacheIsLogin && [4, 5].includes(userType);

    this.setData({
      isLogin: cacheIsLogin,
      userInfo: currentMemberInfo,
      memberInfo: currentMemberInfo,
      isAdminMember: isAdminMember
    });
  },

  // ========== 新增：核心优化，直接请求会员信息 ==========
  getMemberInfo() {
    // 兼容取请求头的方法（参考了你 mine.js 的写法）
    const header = typeof app.getRequestHeader === 'function' 
      ? app.getRequestHeader() 
      : { 'Authorization': 'Bearer ' + (app.globalData.accessToken || wx.getStorageSync('accessToken')) };

    wx.request({
      url: api.base + '/app01/member/info/', // 或者 app.globalData.baseUrl + '/app01/member/info/'
      method: 'GET',
      header: header,
      success: (res) => {
        if (res.data.code === 200) {
          const memberInfo = res.data.data;
          
          // 1. 同步到全局变量
          app.globalData.memberInfo = memberInfo;
          // 2. 同步到本地缓存（关键！给其他页面用）
          wx.setStorageSync('memberInfo', memberInfo);

          // 3. 重新计算是否是管理员
          const userType = Number(memberInfo.user_type || 0);
          const isAdminMember = [4, 5].includes(userType);

          // 4. 更新页面数据，渲染出 nickname
          this.setData({
            userInfo: memberInfo,
            memberInfo: memberInfo,
            isAdminMember: isAdminMember
          });
          
          console.log('首页主动拉取会员信息成功：', memberInfo);
        }
      },
      fail: (err) => {
        console.error('首页拉取会员信息失败：', err);
      }
    });
  },

  // ========== 业务方法保持不变 ==========
  goToOrderList() {
    if (!this.data.isAdminMember) {
      wx.showToast({
        title: '暂无订单管理权限',
        icon: 'none'
      });
      return;
    }
    wx.navigateTo({
      url: '/pages/order-workbench/order-workbench',
      fail: (err) => {
        console.error('跳转订单管理工作台失败：', err);
        wx.showToast({
          title: '页面路径错误',
          icon: 'none'
        });
      }
    });
  },

  loadHomeData() {
    return Promise.all([
      this.fetchBannerData(), 
      this.fetchFixedImages(),
      this.fetchStarGoods()
    ]);
  },

  fetchStarGoods() {
    return new Promise((resolve) => {
      wx.request({
        url: api.base + '/app01/goods/',
        method: 'GET',
        header: {
          'Content-Type': 'application/json'
        },
        success: (res) => {
          let starGoods = [];
          if (res.data && res.data.code === 200 && res.data.data && Array.isArray(res.data.data.results)) {
            const allGoods = res.data.data.results;
            const filteredStarGoods = allGoods.filter(item => item.is_star === true);
            starGoods = filteredStarGoods.map(item => ({
              id: item.id,
              name: item.name,
              image: item.image_url?.startsWith('https') ? item.image_url : `${api.base}${item.image_url || ''}`,
              price: item.member_price || item.price,
              original_price: item.original_price
            }));
          }
          this.setData({ star_goods: starGoods });
          resolve();
        },
        fail: (error) => {
          console.error('所有商品获取失败：', error);
          this.setData({ star_goods: [] });
          resolve();
        }
      });
    });
  },

  goToGoodsDetail(event) {
    const goodsId = event.currentTarget.dataset.goodsid;
    if (!goodsId) {
      wx.showToast({ title: '商品ID不存在', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: `/pages/mall/detail?goods_id=${goodsId}`
    });
  },

  fetchBannerData() {
    return new Promise((resolve) => {
      wx.request({
        url: api.banner,
        method: 'GET',
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          let bannerList = this.data.banner_list;
          let notice = this.data.notice;
          let content = this.data.content;

          const resCode = res.data?.code;
          const resBanner = res.data?.banner || {};
          const resNotice = res.data?.notice || {};

          if (resCode === 200 || res.data?.banner) {
            bannerList = resBanner.results || resBanner || bannerList;
            notice = resNotice?.title || notice;
            content = resNotice?.content || content;
          }

          bannerList = Array.isArray(bannerList) ? bannerList : this.data.banner_list;
          this.setData({ banner_list: bannerList, notice, content });
          resolve();
        },
        fail: (error) => {
          console.error('轮播图获取失败：', error);
          resolve();
        }
      });
    });
  },

  fetchFixedImages() {
    return new Promise((resolve) => {
      wx.request({
        url: api.base + '/app01/index_annonce/',
        method: 'GET',
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          let fixedImages = [];
          if (res.data && res.data.code === 200) {
            const rawImages = res.data.fixed_images || [];
            fixedImages = rawImages.map(item => ({
              img: item?.img_url?.startsWith('https') ? item.img_url : `${api.base}${item?.img_url || item?.img || ''}`,
              id: item?.id || '',
              title: item?.title || ''
            }));
          }
          this.setData({ fixed_images: fixedImages });
          resolve();
        },
        fail: (error) => {
          this.setData({ fixed_images: [] });
          resolve();
        }
      });
    });
  },

  handleClick01(event) {
    const imgId = event.currentTarget.dataset.id;
    if (imgId) console.log('点击固定图片：', imgId);
  },

  goToLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  goToRegister() {
    wx.navigateTo({ url: '/pages/register/register' });
  }
});
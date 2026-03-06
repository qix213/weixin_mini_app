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
    // 简化：先读取缓存/全局的登录状态，再加载数据
    this.syncGlobalUserState().then(() => {
      if (this.data.isAdminMember) {
        this.fetchStarGoods().finally(() => {
          this.setData({ loading: false });
        });
      } else {
        this.loadHomeData().finally(() => {
          this.setData({ loading: false });
        });
      }
    });
  },

  // 核心简化：只做缓存+全局变量的同步，不做多余的接口验证（先保证生效）
  syncGlobalUserState() {
    return new Promise((resolve) => {
      // 1. 优先从缓存读取（pay.js里保存的）
      const cacheIsLogin = wx.getStorageSync('isLogin') || false;
      const cacheMemberInfo = wx.getStorageSync('memberInfo') || {};
      const cacheAccessToken = wx.getStorageSync('accessToken') || '';

      // 2. 同步到全局变量
      app.globalData.isLogin = cacheIsLogin;
      app.globalData.memberInfo = cacheMemberInfo;
      app.globalData.accessToken = cacheAccessToken;
      app.globalData.userInfo = cacheMemberInfo; // 统一userInfo和memberInfo

      // 3. 计算会员等级（4/5级为管理员）
      const userType = Number(cacheMemberInfo.user_type || 0);
      const isAdminMember = cacheIsLogin && [4, 5].includes(userType);

      // 4. 更新页面数据
      this.setData({
        isLogin: cacheIsLogin,
        userInfo: cacheMemberInfo,
        memberInfo: cacheMemberInfo,
        isAdminMember: isAdminMember
      }, () => {
        resolve();
      });
    });
  },

  // 页面显示时重新同步（关键：支付后跳转回来触发）
  onShow() {
    this.syncGlobalUserState();
  },

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
              image: item.image_url?.startsWith('http') ? item.image_url : `${api.base}${item.image_url || ''}`,
              price: item.member_price || item.price,
              original_price: item.original_price
            }));
          } else {
            console.warn('所有商品接口返回数据格式异常：', res.data);
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
      wx.showToast({
        title: '商品ID不存在',
        icon: 'none'
      });
      return;
    }
    
    wx.navigateTo({
      url: `/pages/mall/detail?goods_id=${goodsId}`,
      fail: (err) => {
        console.error('跳转详情页失败：', err);
        wx.showToast({
          title: '跳转失败：页面路径错误',
          icon: 'none'
        });
      }
    });
  },

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
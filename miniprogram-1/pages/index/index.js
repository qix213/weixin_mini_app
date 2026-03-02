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
    // 强制先获取全局数据，再执行判断
    this.syncGlobalUserState().then(() => {
      // 打印关键数据，排查问题
      // console.log('===== 首页初始化数据 =====');
      // console.log('全局会员信息：', app.globalData.memberInfo || app.globalData.userInfo);
      // console.log('页面memberInfo：', this.data.memberInfo);
      // console.log('user_type：', this.data.memberInfo.user_type);
      // console.log('是否为4/5级会员：', this.data.isAdminMember);

      if (this.data.isAdminMember) {
        // 4/5级会员：仅加载明星产品数据（用于表格展示）
        this.fetchStarGoods().finally(() => {
          this.setData({ loading: false });
          // console.log('✅ 已识别为4/5级会员，加载明星产品表格');
        });
      } else {
        // 普通会员：加载所有首页数据
        this.loadHomeData().finally(() => {
          this.setData({ loading: false });
          // console.log('❌ 非4/5级会员，显示原有首页内容');
        });
      }
    });
  },

  // 重构：强制同步并校验会员等级
  syncGlobalUserState() {
    return new Promise((resolve) => {
      // 1. 优先从全局获取会员信息（兜底处理）
      const globalUserInfo = app.globalData.userInfo || {};
      const globalMemberInfo = app.globalData.memberInfo || globalUserInfo;
      const globalIsLogin = app.globalData.isLogin || false;

      // 2. 强制提取user_type（转数字，避免字符串类型导致判断失败）
      const userType = Number(globalMemberInfo.user_type || globalUserInfo.user_type || 0);
      // console.log('提取到的user_type（数字）：', userType);

      // 3. 核心判断：严格检查4/5级
      const isAdminMember = globalIsLogin && [4, 5].includes(userType);
      // console.log('登录状态：', globalIsLogin, '是否4/5级：', isAdminMember);

      // 4. 完善用户信息兜底
      globalUserInfo.nickname = globalUserInfo.nickname || globalUserInfo.username || '用户';

      // 5. 强制更新页面数据（用setData确保渲染）
      this.setData({
        isLogin: globalIsLogin,
        userInfo: globalUserInfo,
        memberInfo: globalMemberInfo,
        isAdminMember: isAdminMember // 关键：确保赋值
      }, () => {
        // 回调中确认数据已更新
        // console.log('页面数据更新完成：', this.data.isAdminMember);
        resolve();
      });
    });
  },

  // 新增：页面显示时重新校验（防止登录后数据未刷新）
  onShow() {
    this.syncGlobalUserState().then(() => {
      // console.log('onShow重新校验会员等级：', this.data.isAdminMember);
      // 如果是4/5级会员，确保加载明星产品数据
      if (this.data.isAdminMember && this.data.star_goods.length === 0) {
        this.fetchStarGoods();
      }
    });
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
import api from '../../config/settings'
const app = getApp();

Page({
  data: {
    banner_list: [{ img: '' }], // 轮播图列表
    notice: 'xxx产品正在7折促销~', // 公告
    isLogin: false, // 登录状态标识
    fixed_images: [], // 固定图片列表
    star_goods: [], // 明星产品列表（新增）
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
      this.fetchFixedImages(),
      this.fetchStarGoods() // 新增：请求明星产品
    ]);
  },

 // 简化版：获取所有商品 → 前端筛选明星产品
// 适配分页格式：获取所有商品 → 筛选明星产品
fetchStarGoods() {
  return new Promise((resolve) => {
    wx.request({
      url: api.base + '/app01/goods/', // 你的所有商品接口路径
      method: 'GET',
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        let starGoods = [];
        // 关键修改：适配分页格式的返回数据（data → results）
        if (res.data && res.data.code === 200 && res.data.data && Array.isArray(res.data.data.results)) {
          // 1. 从分页数据中取出真正的商品数组
          const allGoods = res.data.data.results;
          console.log('所有商品列表：', allGoods);
          
          // 2. 筛选出 is_star 为 true 的商品（匹配你数据库中的字段名）
          const filteredStarGoods = allGoods.filter(item => item.is_star === true);
          console.log('筛选出的明星产品：', filteredStarGoods);
          
          // 3. 保留原有数据映射逻辑
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
        console.error('所有商品获取失败（明星产品筛选依赖）：', error);
        this.setData({ star_goods: [] });
        resolve();
      }
    });
  });
},

  // 新增：跳转到商品详情页
  goToGoodsDetail(event) {
    console.log('点击商品触发事件：', event); // 新增：打印完整事件
    const goodsId = event.currentTarget.dataset.goodsid;
    console.log('获取到的商品ID：', goodsId); // 新增：打印商品ID
    
    if (!goodsId) {
      wx.showToast({
        title: '商品ID不存在',
        icon: 'none'
      });
      return;
    }
    
    // 新增：先验证路径是否存在，再跳转
    wx.navigateTo({
      url: `/pages/mall/detail?goods_id=${goodsId}`,
      success: () => {
        // console.log('跳转详情页成功');
      },
      fail: (err) => {
        console.error('跳转详情页失败：', err); // 打印失败原因
        wx.showToast({
          title: '跳转失败：页面路径错误',
          icon: 'none'
        });
      }
    });
  },

  // 原有方法保持不变 ↓
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

  onShow() {
    this.syncGlobalUserState();
    this.setData({
      isLogin: app.globalData.isLogin || false,
      userInfo: app.globalData.userInfo || {}
    });
  },

  syncGlobalUserState() {
    const globalIsLogin = app.globalData.isLogin || false;
    const globalUserInfo = app.globalData.userInfo || {};
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
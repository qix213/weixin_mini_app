const app = getApp();
import api from '../../config/settings'

Page({
  data: {
    loading: true,
    searchValue: '',
    categories: [],
    goodsList: [],
    selectedCategoryId: '',
    userType: 1, 
  },

  async onLoad() {
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    this.setData({ userType: memberInfo.user_type || 1 }); 

    try {
      await this.getCategories();
      await this.getGoodsList();
    } catch (e) {
      console.error("初始化页面失败", e);
    }
  },

  onPullDownRefresh() {
    this.setData({ loading: true });
    this.getCategories().then(() => {
      this.getGoodsList().then(() => {
        wx.stopPullDownRefresh();
      });
    });
  },

  // ================= 1. 获取分类数据 =================
  getCategories() {
    return new Promise((resolve) => {
      wx.request({
        url: `${api.base}/app01/categories/`,
        method: 'GET',
        timeout: 5000,
        success: (res) => {
          let categories = [];
          if (res.data && res.data.code === 200) {
            categories = res.data.data.results || [];
          } else if (res.statusCode === 200) {
            categories = res.data.results || res.data || [];
          }
          const allCategory = { id: '', name: '全部系列', icon: 'apps-o' };
          if (!categories.some(item => item.id === '')) {
            categories = [allCategory, ...categories];
          }
          this.setData({ categories });
          resolve();
        },
        fail: (err) => {
          this.setData({ categories: [{ id: '', name: '全部系列', icon: 'apps-o' }] });
          resolve();
        }
      });
    });
  },

  // ================= 2. 获取商品数据 =================
  getGoodsList() {
    return new Promise((resolve) => {
      const { searchValue, selectedCategoryId, userType } = this.data; 
      const params = { 
        keyword: searchValue.trim(),
        user_type: userType 
      };
      if (selectedCategoryId) params.category_id = selectedCategoryId;

      wx.request({
        url: `${api.base}/app01/goods/`,
        method: 'GET',
        data: params,
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          let goodsList = [];
          if (res.data && res.data.code === 200) {
            goodsList = res.data.data.results || res.data.data || [];
          } else if (res.statusCode === 200) {
            goodsList = res.data.results || res.data || [];
          }

          this.setData({ goodsList, loading: false });
          this.formatGoodsData(); // 格式化价格显示逻辑
          resolve();
        },
        fail: (err) => {
          this.setData({ goodsList: [], loading: false });
          resolve();
        }
      });
    });
  },

  // ================= 3. 价格展示逻辑 =================
  isPointGoods(item) {
    const pointField = item.isPointGoods || item.can_point_exchange || item.canPointExchange || false;
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    let isPoint = false;
    if (typeof pointField === 'string') isPoint = pointField.toLowerCase() === 'true';
    else if (typeof pointField === 'number') isPoint = pointField === 1;
    else isPoint = !!pointField;
    return isPoint || hasPointPrice;
  },

  formatGoodsData() {
    const { goodsList, userType } = this.data; 
    if (!goodsList.length) return;
    
    const currentLevel = parseInt(userType) || 1;

    const newGoodsList = goodsList.map(item => {
      const isPointGoods = this.isPointGoods(item);
      const memberPrice = parseFloat(item.member_price || 0).toFixed(2);
      const originalPrice = parseFloat(item.original_price || 0).toFixed(2);
      
      item.pointPrice = isPointGoods ? Math.floor(parseFloat(memberPrice) * 100) : 0;
      item.isPointGoods = !!isPointGoods;

      if (currentLevel <= 1) {
        // 蓝朋友0星：零售价为主
        item.mainPriceLabel = '零售价：';
        item.mainPriceValue = originalPrice;
        item.subPriceLabel = '会员价：';
        item.subPriceValue = memberPrice;
      } else {
        // 星级会员：会员价为主
        item.mainPriceLabel = '会员价：';
        item.mainPriceValue = memberPrice;
        item.subPriceLabel = '零售价：';
        item.subPriceValue = originalPrice;
      }
      
      return item;
    });
    this.setData({ goodsList: newGoodsList });
  },

  // ================= 4. 其它交互逻辑 =================
  onSearchChange(e) { this.setData({ searchValue: e.detail.value }); },
  onSearch() {
    this.setData({ loading: true, selectedCategoryId: '' });
    this.getGoodsList();
  },
  chooseCategory(e) {
    this.setData({ selectedCategoryId: e.currentTarget.dataset.id, loading: true });
    this.getGoodsList();
  },
  toGoodsDetail(e) {
    const goodsId = e.currentTarget.dataset.id;
    if (!goodsId) return;
    wx.navigateTo({ url: `/pages/mall/detail?goods_id=${goodsId}` });
  }
});
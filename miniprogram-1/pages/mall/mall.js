const api = require('../../config/settings.js');
const app = getApp();

Page({
  data: {
    loading: true,
    searchValue: '',
    categories: [],
    goodsList: [],
    selectedCategoryId: '',
    userType: 1, 
    page: 1,           // 当前请求的页码
    hasMore: true,     // 后端是否还有更多数据
    isFetching: false, // 接口防抖锁：是否正在请求中
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
          
          // 如果没有选中任何分类，且分类列表有数据，默认选中第一个分类
          let selectedCategoryId = this.data.selectedCategoryId;
          if (categories.length > 0 && !selectedCategoryId) {
            selectedCategoryId = categories[0].id;
          }

          this.setData({ categories, selectedCategoryId });
          resolve();
        },
        fail: (err) => {
          this.setData({ categories: [] });
          resolve();
        }
      });
    });
  },

  // ================= 2. 获取商品数据 =================
  getGoodsList() {
    return new Promise((resolve) => {
      // 🌟 1. 触发请求前拦截：如果正在请求中，直接跳过，防止用户狂刷
      if (this.data.isFetching) return resolve();
      
      const { searchValue, selectedCategoryId, userType, page } = this.data; 
      const params = { 
        keyword: searchValue.trim(),
        user_type: userType,
        page: page // 🌟 2. 把当前页码传给后端
      };
      if (selectedCategoryId) params.category_id = selectedCategoryId;

      this.setData({ isFetching: true }); // 上锁

      wx.request({
        url: `${api.base}/app01/goods/`,
        method: 'GET',
        data: params,
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          let newGoods = [];
          if (res.data && res.data.code === 200) {
            newGoods = res.data.data.results || res.data.data || [];
          } else if (res.statusCode === 200) {
            newGoods = res.data.results || res.data || [];
          }

          // 🌟 3. 判断是否还有下一页（通常后端默认一页10条，少于10条说明到底了）
          const hasMore = newGoods.length === 10; 

          // 🌟 4. 核心：如果是第1页就覆盖，如果是第2、3页就把新数据拼在后面
          const currentList = this.data.page === 1 ? [] : this.data.goodsList;
          const updatedList = [...currentList, ...newGoods];

          this.setData({ 
            goodsList: updatedList, 
            loading: false,
            isFetching: false, // 解锁
            hasMore: hasMore   // 更新到底状态
          }, () => {
            // 放在 setData 的回调里执行格式化，确保拿到了最新拼接完的完整数组
            this.formatGoodsData(); 
            resolve();
          });
        },
        fail: (err) => {
          // 哪怕失败了也要解锁，否则永远滑不动了
          this.setData({ isFetching: false, loading: false });
          resolve();
        }
      });
    });
  },
  // 🌟 滚动到底部时自动调用
  loadMoreGoods() {
    // 只有在“还有数据”且“当前没在请求”的时候才触发
    if (this.data.hasMore && !this.data.isFetching) {
      this.setData({
        page: this.data.page + 1 // 页码递增
      }, () => {
        this.getGoodsList(); // 带着新页码去请求下一页
      });
    }
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
    this.setData({ 
      // 顺手做个首尾去空格，防止用户误敲空格搜不出东西
      searchValue: this.data.searchValue.trim(), 
      loading: true, 
      selectedCategoryId: '', // 搜索时通常是全局搜，所以清空左侧分类高亮
      // 👇 核心新增：彻底重置分页状态
      page: 1,         // 回到第1页
      hasMore: true,   // 恢复可加载状态
      goodsList: []    // 清空旧数据，给新搜索结果腾出干净的容器
    }, () => {
      // 确保状态全部清零后，再去请求数据
      this.getGoodsList();
    });
  },
  chooseCategory(e) {
    const id = e.currentTarget.dataset.id;
    // 🌟 切换前先重置分页状态
    this.setData({
      selectedCategoryId: id,
      page: 1,
      hasMore: true,
      goodsList: [], // 视觉上先清空旧数据体验更好
      loading: true  // 重新展示骨架屏
    }, () => {
      this.getGoodsList();
    });
  },
  toGoodsDetail(e) {
    const goodsId = e.currentTarget.dataset.id;
    const goodsType = e.currentTarget.dataset.type; 
    console.log("点击获取的 dataset:", e.currentTarget.dataset);
    
    // 你的原版安全校验，保留！
    if (!goodsId) return; 
    
    if (goodsType == 3) {
      // 🌟 新增的京东物流跳转逻辑 (建议这里也统一传 goods_id)
      wx.navigateTo({
        url: `/pages/mall/jdLogistics?goods_id=${goodsId}` 
      });
    } else {
      // 🌟 修复：用回你原来的 goods_id！
      wx.navigateTo({
        url: `/pages/mall/detail?goods_id=${goodsId}`
      });
    }
  }
});
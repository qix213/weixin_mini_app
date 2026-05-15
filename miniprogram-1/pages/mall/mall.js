const app = getApp();
import api from '../../config/settings'

Page({
  data: {
    primaryColor: '#1E88E5', 
    loading: true, 
    searchValue: '', 
    categories: [], 
    goodsList: [], 
    selectedCategoryId: '', 
    cartList: {}, 
    noop() {},
  },

  previewGoodsImg(e) {
    const imgUrl = e.currentTarget.dataset.img;
    if (!imgUrl) return;
    wx.previewImage({
      current: imgUrl,
      urls: [imgUrl]
    });
  },

  onLoad() {
    const cartList = wx.getStorageSync('cartList') || {};
    this.setData({ cartList });
    this.getCategories().then(() => {
      this.getGoodsList();
    });
  },

  minusNum(e) {
    const goodsId = e.currentTarget.dataset.id;
    const { cartList } = this.data;
    const currentNum = cartList[goodsId] || 1;
    if (currentNum <= 1) return;
    cartList[goodsId] = currentNum - 1;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    this.updateGoodsCartNum();
  },

  plusNum(e) {
    const goodsId = e.currentTarget.dataset.id;
    const { cartList } = this.data;
    const currentNum = cartList[goodsId] || 1;
    cartList[goodsId] = currentNum + 1;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    this.updateGoodsCartNum();
  },

  changeNum(e) {
    const goodsId = e.currentTarget.dataset.id;
    const num = parseInt(e.detail.value) || 1;
    const { cartList } = this.data;
    cartList[goodsId] = num < 1 ? 1 : num;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    this.updateGoodsCartNum();
  },

  updateGoodsCartNum() {
    const { goodsList, cartList } = this.data;
    if (!goodsList.length) return;
    
    const newGoodsList = goodsList.map(item => {
      item.cartNum = cartList[item.id] || 1;
      // 核心修复1：强制校验积分商品
      const isPointGoods = this.isPointGoods(item);
      // 核心修复2：严格处理member_price，避免转数字失败
      // 步骤1：先转字符串，去除空格/非数字字符（比如"60.00元"→"60.00"）
      const memberPriceStr = (item.member_price || '0').toString().replace(/[^0-9.]/g, '');
      // 步骤2：转数字，兜底0
      const memberPrice = parseFloat(memberPriceStr) || 0;
      // 步骤3：计算积分价格，强制取整，兜底0
      item.pointPrice = isPointGoods ? Math.floor(memberPrice * 100) : 0;
      // 步骤4：强制转成数字类型（避免字符串）
      item.pointPrice = Number(item.pointPrice);
      // 步骤5：强制赋值isPointGoods（布尔值）
      item.isPointGoods = !!isPointGoods;
      return item;
    });
    this.setData({ goodsList: newGoodsList });
  },

  // 统一判断是否为积分商品（兼容所有字段格式）
  isPointGoods(item) {
    // 核心修复：扩大兼容范围，优先取后端返回的isPointGoods/pointPrice
    const pointField = item.isPointGoods || item.can_point_exchange || item.canPointExchange || false;
    // 额外兜底：如果后端直接返回pointPrice>0，也判定为积分商品
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    
    let isPoint = false;
    // 兼容布尔/字符串/数字格式
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true';
    } else if (typeof pointField === 'number') {
      isPoint = pointField === 1;
    } else {
      isPoint = !!pointField;
    }
    // 兜底：如果有积分价格且>0，强制判定为积分商品
    return isPoint || hasPointPrice;
  },

// 【核心修复】addToCart方法：移除不存在的函数调用，直接更新缓存
addToCart(e) {
  const goodsId = e.currentTarget.dataset.id;
  const goodsName = e.currentTarget.dataset.name;
  const { cartList, goodsList } = this.data;
  const num = cartList[goodsId] || 1;

  // 正确找到当前商品，并获取积分标识
  const currentGoods = goodsList.find(item => item.id === goodsId) || {};
  const isPointGoods = currentGoods.can_point_exchange === true || currentGoods.is_point_goods === true;
  
  // 🌟 核心修复：直接操作 globalData 和 Storage，替代原本不存在的 app.setGoodsPointCache 方法
  if (!app.globalData.goodsPointCache) {
    app.globalData.goodsPointCache = {};
  }
  app.globalData.goodsPointCache[goodsId] = isPointGoods;
  wx.setStorageSync('goodsPointCache', app.globalData.goodsPointCache);

  // 原有逻辑（不变）
  const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
  if (!token) {
    wx.showToast({
      title: `登录后可同步【${goodsName}】到购物车`,
      icon: 'none',
      duration: 2000
    });
    cartList[goodsId] = num;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    return;
  }

  cartList[goodsId] = num;
  this.setData({ cartList });
  wx.setStorageSync('cartList', cartList);

  wx.showLoading({ title: '加入购物车...', mask: true });
  
  // 这里的 request 假设你在 app.js 中已经封装好了
  app.request({
    url: '/app01/cart/add/',
    method: 'POST',
    data: { goods_id: goodsId, num: num },
  }).then(res => {
    wx.hideLoading();
    if (res.data.code === 200) {
      wx.showToast({
        title: `【${goodsName}】已加入购物车 x${num}`,
        icon: 'success',
        duration: 1500
      });
    } else {
      if (res.data?.detail === "身份认证信息未提供" || res.statusCode === 401) {
        wx.removeStorageSync('accessToken');
        app.globalData.accessToken = '';
        wx.showToast({
          title: '登录状态失效，请重新登录',
          icon: 'none',
          duration: 2000
        });
      } else {
        wx.showToast({
          title: res.data.msg || '加入购物车失败（本地已缓存）',
          icon: 'none',
          duration: 2000
        });
      }
    }
  }).catch(err => {
    wx.hideLoading();
    wx.showToast({
      title: `【${goodsName}】已本地缓存 x${num}（登录后同步）`,
      icon: 'none',
      duration: 2000
    });
  });
},

  onPullDownRefresh() {
    this.setData({ loading: true });
    this.getGoodsList().then(() => {
      wx.stopPullDownRefresh();
      this.setData({ loading: false });
    });
  },

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
          const allCategory = { id: '', name: '全部' };
          if (!categories.some(item => item.id === '')) {
            categories = [allCategory, ...categories];
          }
          this.setData({ categories });
          resolve();
        },
        fail: (err) => {
          wx.showToast({
            title: '分类数据加载失败',
            icon: 'none',
            duration: 2000
          });
          this.setData({ categories: [{ id: '', name: '全部' }] });
          resolve();
        }
      });
    });
  },

  // 核心修改：强化积分价格计算，确保数据格式正确
  getGoodsList() {
    return new Promise((resolve) => {
      const { searchValue, selectedCategoryId, cartList } = this.data;
      const params = { keyword: searchValue.trim() };
      if (selectedCategoryId) params.category_id = selectedCategoryId;

      wx.request({
        url: `${api.base}/app01/goods/`,
        method: 'GET',
        data: params,
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          let goodsList = [];
          if (res.data && res.data.code === 200) {
            goodsList = res.data.data.results || [];
          } else if (res.statusCode === 200) {
            goodsList = res.data.results || res.data || [];
          }

          // 绑定购物车数量 + 强校验积分商品
          goodsList = goodsList.map(item => {
            item.cartNum = cartList[item.id] || 1;
            // 调用统一的判断方法
            const isPointGoods = this.isPointGoods(item);
            // 核心修复：严格处理member_price，避免转数字失败
            const memberPriceStr = (item.member_price || '0').toString().replace(/[^0-9.]/g, '');
            const memberPrice = parseFloat(memberPriceStr) || 0;
            // 计算积分价格，强制取整+转数字
            item.pointPrice = isPointGoods ? Math.floor(memberPrice * 100) : 0;
            item.pointPrice = Number(item.pointPrice);
            // 强制赋值isPointGoods
            item.isPointGoods = !!isPointGoods;
            return item;
          });

          this.setData({ goodsList, loading: false });
          // 额外：确保更新购物车数量（触发积分价格二次校验）
          this.updateGoodsCartNum();
          resolve();
        },
        fail: (err) => {
          this.setData({ goodsList: [], loading: false });
          wx.showToast({
            title: '商品数据加载失败',
            icon: 'none',
            duration: 2000
          });
          resolve();
        }
      });
    });
  },

  onSearchChange(e) {
    this.setData({ searchValue: e.detail.value });
  },

  onSearch() {
    const keyword = this.data.searchValue.trim();
    if (!keyword) {
      wx.showToast({
        title: '请输入搜索关键词',
        icon: 'none',
        duration: 1500
      });
      return;
    }
    this.setData({ 
      loading: true,
      selectedCategoryId: '' 
    });
    this.getGoodsList();
  },

  chooseCategory(e) {
    const categoryId = e.currentTarget.dataset.id;
    this.setData({ 
      selectedCategoryId: categoryId,
      loading: true 
    });
    this.getGoodsList();
  },

  toGoodsDetail(e) {
    const goodsId = e.currentTarget.dataset.id;
    if (!goodsId || isNaN(goodsId)) {
      wx.showToast({
        title: "无效的商品ID",
        icon: 'none',
        duration: 1500
      });
      return;
    }
    const detailPath = `/pages/mall/detail?goods_id=${goodsId}`;
    wx.navigateTo({
      url: detailPath,
      fail: (err) => {
        wx.showToast({
          title: "页面不存在或路径错误",
          icon: 'none',
          duration: 2000
        });
      }
    });
  }
});
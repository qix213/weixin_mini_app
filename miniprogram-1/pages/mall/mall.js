import Toast from '@vant/weapp/toast/toast';
import api from '../../config/settings'
const app = getApp(); // 全局获取 app 实例

Page({
  data: {
    primaryColor: '#1E88E5', // 品牌蓝
    loading: true, // 加载状态
    searchValue: '', // 搜索关键词
    categories: [], // 商品分类
    goodsList: [], // 商品列表
    selectedCategoryId: '', // 选中的分类ID
    cartList: {}, // 购物车缓存：{goodsId: num}
  },

  // 商品图片预览
  previewGoodsImg(e) {
    const imgUrl = e.currentTarget.dataset.img;
    if (!imgUrl) return;
    wx.previewImage({
      current: imgUrl,
      urls: [imgUrl]
    });
  },

  onLoad() {
    // 1. 初始化购物车缓存（确保cartList不为空）
    const cartList = wx.getStorageSync('cartList') || {};
    this.setData({ cartList });
    
    // 2. 先加载分类，再加载商品（保证分类加载完成后商品列表有正确的筛选基础）
    this.getCategories().then(() => {
      this.getGoodsList();
    });
  },

  // 减少商品数量
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

  // 增加商品数量
  plusNum(e) {
    const goodsId = e.currentTarget.dataset.id;
    const { cartList } = this.data;
    const currentNum = cartList[goodsId] || 1;
    cartList[goodsId] = currentNum + 1;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    this.updateGoodsCartNum();
  },

  // 手动修改数量
  changeNum(e) {
    const goodsId = e.currentTarget.dataset.id;
    const num = parseInt(e.detail.value) || 1;
    const { cartList } = this.data;
    cartList[goodsId] = num < 1 ? 1 : num;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);
    this.updateGoodsCartNum();
  },

  // 更新商品列表中的购物车数量展示
  updateGoodsCartNum() {
    const { goodsList, cartList } = this.data;
    // 安全处理：goodsList为空时不执行map
    if (!goodsList.length) return;
    
    const newGoodsList = goodsList.map(item => {
      item.cartNum = cartList[item.id] || 1;
      return item;
    });
    this.setData({ goodsList: newGoodsList });
  },

  // 加入购物车（核心优化：统一使用Promise版request，修复Token携带）
  addToCart(e) {
    const goodsId = e.currentTarget.dataset.id;
    const goodsName = e.currentTarget.dataset.name;
    const { cartList } = this.data;
    const num = cartList[goodsId] || 1;

    // 1. 获取 Token（统一用accessToken，适配app.js的全局变量）
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      Toast(`登录后可将【${goodsName}】加入购物车`);
      wx.showModal({
        title: '提示',
        content: '请先登录后同步购物车数据',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        }
      });
      // 仅本地缓存，不同步后端
      cartList[goodsId] = num;
      this.setData({ cartList });
      wx.setStorageSync('cartList', cartList);
      return;
    }

    // 2. 本地缓存更新
    cartList[goodsId] = num;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);

    // 3. 调用后端接口（使用Promise版request，统一错误处理）
    wx.showLoading({ title: '加入购物车...', mask: true });
    app.request({
      url: '/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsId, num: num },
    }).then(res => {
      wx.hideLoading();
      // console.log('列表页加入购物车响应：', res.data);
      if (res.data.code === 200) {
        Toast.success(`【${goodsName}】已加入购物车 x${num}`);
      } else {
        // Token 过期/认证失败处理
        if (res.data?.detail === "身份认证信息未提供" || res.statusCode === 401) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          Toast.fail('登录状态失效，请重新登录');
          setTimeout(() => {
            wx.navigateTo({ url: '/pages/login/login' });
          }, 1500);
        } else {
          Toast.fail(res.data.msg || '加入购物车失败');
        }
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('加入购物车接口失败：', err);
      Toast.success(`【${goodsName}】已加入购物车(本地) x${num}`);
    });
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.setData({ loading: true });
    this.getGoodsList().then(() => {
      wx.stopPullDownRefresh();
      this.setData({ loading: false });
    });
  },

  // 获取商品分类（修改为Promise版，确保顺序执行）
  getCategories() {
    return new Promise((resolve) => {
      // console.log('mall分类请求前Token：', app.globalData.accessToken);
      app.request({
        url: '/app01/categories/',
        method: 'GET',
        timeout: 5000,
      }).then(res => {
        let categories = [];
        // 兼容两种返回格式：有code/无code
        if (res.data && res.data.code === 200) {
          categories = res.data.data.results || [];
        } else if (res.statusCode === 200) {
          categories = res.data.results || res.data || [];
        }
        // 添加“全部”分类（安全处理：避免重复添加）
        const allCategory = { id: '', name: '全部' };
        if (!categories.some(item => item.id === '')) {
          categories = [allCategory, ...categories];
        }
        this.setData({ categories });
        resolve(); // 分类加载完成，执行后续逻辑
      }).catch(err => {
        console.error('分类请求失败：', err);
        Toast.fail('分类数据加载失败');
        this.setData({ categories: [{ id: '', name: '全部' }] });
        resolve(); // 即使失败也resolve，保证商品列表能加载
      });
    });
  },

  // 改造getGoodsList为Promise版，修复数据加载逻辑
  getGoodsList() {
    return new Promise((resolve) => {
      const { searchValue, selectedCategoryId, cartList } = this.data;
      const params = { keyword: searchValue.trim() };
      if (selectedCategoryId) params.category_id = selectedCategoryId;

      app.request({
        url: '/app01/goods/',
        method: 'GET',
        data: params,
        // 移除重复的header：app.js的request已封装
      }).then(res => {
        let goodsList = [];
        // 兼容两种返回格式
        if (res.data && res.data.code === 200) {
          goodsList = res.data.data.results || [];
        } else if (res.statusCode === 200) {
          goodsList = res.data.results || res.data || [];
        }
        // 绑定购物车数量（核心：确保cartNum正确赋值）
        goodsList = goodsList.map(item => {
          item.cartNum = cartList[item.id] || 1;
          return item;
        });
        this.setData({ goodsList, loading: false });
        resolve();
      }).catch(err => {
        console.error('商品请求失败：', err);
        this.setData({ goodsList: [], loading: false });
        Toast.fail('商品数据加载失败');
        resolve();
      });
    });
  },

  // 搜索框输入
  onSearchChange(e) {
    // console.log('输入内容：', e.detail.value);
    this.setData({ searchValue: e.detail.value });
  },

  // 搜索触发
  onSearch() {
    // console.log('===== 点击搜索图标/回车 =====');
    const keyword = this.data.searchValue.trim();
    if (!keyword) {
      Toast.info('请输入搜索关键词');
      return;
    }
    this.setData({ 
      loading: true,
      selectedCategoryId: '' 
    });
    this.getGoodsList();
  },

  // 选择分类
  chooseCategory(e) {
    const categoryId = e.currentTarget.dataset.id;
    // console.log('选中的分类ID：', categoryId);
    this.setData({ 
      selectedCategoryId: categoryId,
      loading: true 
    });
    this.getGoodsList();
  },

  // 跳转商品详情页
  toGoodsDetail(e) {
    // console.log("跳转商品详情事件参数：", e);
    const goodsId = e.currentTarget.dataset.id;
    if (!goodsId || isNaN(goodsId)) {
      Toast.fail("无效的商品ID");
      return;
    }
    const detailPath = `/pages/mall/detail?id=${goodsId}`;
    // console.log("商品详情跳转路径：", detailPath);
    wx.navigateTo({
      url: detailPath,
      fail: (err) => {
        console.error("跳转商品详情失败：", err);
        Toast.fail("页面不存在或路径错误");
      }
    });
  }
});
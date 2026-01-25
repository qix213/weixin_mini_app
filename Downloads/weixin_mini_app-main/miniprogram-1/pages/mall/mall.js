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
    selectedCategoryId: '', // 选中的分类ID（初始化空字符串，避免传参错误）
    cartList: {}, // 购物车缓存：{goodsId: num}
  },
  // 商品图片预览
  previewGoodsImg(e) {
    const imgUrl = e.currentTarget.dataset.img;
    if (!imgUrl) return;
    wx.previewImage({
      current: imgUrl, // 当前显示图片的URL
      urls: [imgUrl] // 需要预览的图片URL列表（单张图片直接放数组）
    });
  },
  onLoad() {
    // 无需登录，直接加载数据
    const cartList = wx.getStorageSync('cartList') || {};
    this.setData({ cartList });
    this.getCategories();
    this.getGoodsList();
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
    const newGoodsList = goodsList.map(item => {
      item.cartNum = cartList[item.id] || 1;
      return item;
    });
    this.setData({ goodsList: newGoodsList });
  },

  // 加入购物车（对接后端接口）
  addToCart(e) {
    const goodsId = e.currentTarget.dataset.id;
    const goodsName = e.currentTarget.dataset.name;
    const { cartList } = this.data;
    const num = cartList[goodsId] || 1;

    // 1. 本地缓存更新
    cartList[goodsId] = num;
    this.setData({ cartList });
    wx.setStorageSync('cartList', cartList);

    // 2. 调用后端接口（需登录则传token）
    wx.request({
      url: 'http://localhost:8000/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsId, num: num },
      header: {
        'content-type': 'application/json',
        // 登录后添加token：'Authorization': 'Bearer ' + wx.getStorageSync('token')
      },
      success: (res) => {
        if (res.data.code === 200) {
          Toast.success(`【${goodsName}】已加入购物车 x${num}`);
        } else {
          Toast.fail(res.data.msg || '加入购物车失败');
        }
      },
      fail: (err) => {
        console.error('加入购物车接口失败：', err);
        Toast.success(`【${goodsName}】已加入购物车(本地) x${num}`);
      }
    });
  },


  // 下拉刷新
  onPullDownRefresh() {
    this.setData({ loading: true });
    this.getGoodsList(() => {
      wx.stopPullDownRefresh();
    });
  },

  // 获取商品分类（对接后端接口）
// 商品列表 JS（修改 getCategories 方法）
getCategories() {
  wx.request({
    url: api.category,
    method: 'GET',
    timeout: 5000,
    success: (res) => {
      let categories = [];
      if (res.data && res.data.code === 200) {
        categories = res.data.data.results;
      }
      // 核心修改：在分类列表最前面添加“全部”分类（id 为空字符串）
      const allCategory = {
        id: '', // 空ID标识“全部商品”
        name: '全部'
      };
      // 合并“全部”分类和原有分类
      categories = [allCategory, ...categories];
      this.setData({ categories: categories });
    },
    fail: () => {
      Toast.fail('分类数据加载失败');
      // 即使分类加载失败，也添加“全部”分类
      this.setData({
        categories: [{ id: '', name: '全部' }]
      });
    }
  });
},

  // 改造getGoodsList，添加数量展示
  getGoodsList(callback) {
    const { searchValue, selectedCategoryId } = this.data;
    const params = { keyword: searchValue.trim() };
    if (selectedCategoryId) params.category_id = selectedCategoryId;

    wx.request({
      url: 'http://localhost:8000/app01/goods/',
      method: 'GET',
      data: params,
      header: { 'content-type': 'application/json' },
      success: (res) => {
        if (res.data && res.data.code === 200) {
          let goodsList = res.data.data.results;
          // 绑定购物车数量
          const { cartList } = this.data;
          goodsList = goodsList.map(item => {
            item.cartNum = cartList[item.id] || 1;
            return item;
          });
          this.setData({ goodsList });
        } else {
          this.setData({ goodsList: [] });
        }
      },
      fail: (err) => {
        console.error('商品请求失败：', err);
        this.setData({ goodsList: [] });
        Toast.fail('商品数据加载失败');
      },
      complete: () => {
        this.setData({ loading: false });
        callback && callback();
      }
    });
  },

  // 1. 搜索框输入（原生input用e.detail.value）
  onSearchChange(e) {
    console.log('输入内容：', e.detail.value);
    this.setData({ searchValue: e.detail.value });
  },

  // 2. 搜索触发（核心：必须在Page根层级，拼写正确）
  onSearch() {
    console.log('===== 点击搜索图标/回车 =====');
    console.log('搜索关键词：', this.data.searchValue);
    // 空关键词提示
    if (!this.data.searchValue.trim()) {
      Toast.info('请输入搜索关键词');
      return;
    }
    this.setData({ 
      loading: true,
      selectedCategoryId: '' // 搜索时清空分类
    });
    this.getGoodsList();
  },

  // 选择分类（核心：记录选中的分类ID并重新加载）
chooseCategory(e) {
  const categoryId = e.currentTarget.dataset.id;
  console.log('选中的分类ID：', categoryId);

  // 直接设置分类ID（空ID对应“全部商品”）
  this.setData({ 
    selectedCategoryId: categoryId,
    loading: true 
  });
  // 重新加载商品列表（分类ID为空时，后端会返回全部商品）
  this.getGoodsList();
},

  // 跳转商品详情页
toGoodsDetail(e) {
  // 打印事件参数，排查是否获取到商品 ID
  console.log("跳转商品详情事件参数：", e);
  // 用 dataset.id 取值（与 view 上的 data-id 对应）
  const goodsId = e.currentTarget.dataset.id;
  
  // 校验商品 ID
  if (!goodsId || isNaN(goodsId)) {
    Toast.fail("无效的商品ID");
    return;
  }

  // 打印跳转路径，确认页面路径正确
  const detailPath = `/pages/mall/detail?id=${goodsId}`;
  console.log("商品详情跳转路径：", detailPath);

  // 跳转（强制跳转，确保生效）
  wx.navigateTo({
    url: detailPath,
    // 跳转失败回调（排查页面是否存在）
    fail: (err) => {
      console.error("跳转商品详情失败：", err);
      Toast.fail("页面不存在或路径错误");
    }
  });
},

  // 加入购物车（提示登录）
  addToCart(e) {
    const goodsName = e.currentTarget.dataset.name;
    if (!app.globalData.token) {
    Toast(`登录后可将【${goodsName}】加入购物车`);
  }
}
});
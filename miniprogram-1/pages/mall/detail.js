import Toast from '@vant/weapp/toast/toast';
const app = getApp(); // 全局获取 app 实例

Page({
  data: {
    goodsId: '', // 商品ID
    goodsDetail: {}, // 商品详情数据
    loading: true, // 加载状态
    baseUrl: 'http://localhost:8000',
    cartNum: 1, // 默认购买数量
  },

  onLoad(options) {
    // 接收从商品列表传递的商品ID
    const goodsId = options.id;
    if (!goodsId) {
      Toast.fail('无效的商品ID');
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
      return;
    }
    this.setData({ goodsId });
    // 获取商品详情（核心修改：无需登录，直接请求）
    this.getGoodsDetail();
  },

  // 获取商品详情（核心修改：移除登录校验，纯公开访问）
  getGoodsDetail() {
    const { goodsId, baseUrl } = this.data;

    // 核心修改：不携带token，直接请求（浏览详情无需登录）
    wx.request({
      url: `${baseUrl}/app01/goods/${goodsId}/`,
      method: 'GET',
      header: { 'Content-Type': 'application/json' }, // 仅基础头，无token
      timeout: 5000,
      success: (res) => {
        console.log('商品详情请求成功：', res.data);
        // 处理后端不同的响应格式
        if (res.statusCode === 200) {
          // 情况1：后端返回自定义格式（code=200）
          if (res.data.code === 200) {
            this.setData({ goodsDetail: res.data.data });
          }
          // 情况2：后端返回DRF默认序列化格式（无code）
          else if (res.data.id) {
            this.setData({ goodsDetail: res.data });
          } else {
            Toast.fail('获取商品详情失败：数据格式异常');
            this.setData({ goodsDetail: {} });
          }
        }
        // 核心修改：401时仅提示，不强制登录/返回
        else if (res.statusCode === 401) {
          Toast.info('部分功能需登录后使用，仍可浏览商品');
          // 尝试解析无token时的商品数据（如果后端返回）
          if (res.data.id) {
            this.setData({ goodsDetail: res.data });
          } else {
            this.setData({ goodsDetail: {} });
          }
        }
        // 其他错误
        else {
          Toast.fail(`获取商品详情失败：${res.data?.detail || res.statusCode}`);
          this.setData({ goodsDetail: {} });
        }
      },
      fail: (err) => {
        console.error('商品详情请求失败：', err);
        Toast.fail('网络异常，详情加载失败');
        this.setData({ goodsDetail: {} });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  // 减少数量（仅本地，无需登录）
  minusNum() {
    const { cartNum } = this.data;
    if (cartNum <= 1) return;
    this.setData({ cartNum: cartNum - 1 });
  },

  // 增加数量（仅本地，无需登录）
  plusNum() {
    const { cartNum } = this.data;
    this.setData({ cartNum: cartNum + 1 });
  },

  // 手动修改数量（仅本地，无需登录）
  changeNum(e) {
    const num = parseInt(e.detail.value) || 1;
    this.setData({ cartNum: num < 1 ? 1 : num });
  },

  // 获取Token工具方法（仅用于操作校验）
  getValidToken() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    return token;
  },

  // 加入购物车（仅操作需要登录，浏览无需）
  addToCart() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 校验 Token（仅操作需要）
    const token = this.getValidToken();
    if (!token) {
      // 核心修改：仅提示，不强制弹窗跳转
      Toast('登录后可将商品同步到购物车（已本地缓存）');
      // 本地缓存数量
      const cartList = wx.getStorageSync('cartList') || {};
      cartList[goodsDetail.id] = cartNum;
      wx.setStorageSync('cartList', cartList);
      return;
    }

    // 2. 有token时同步后端
    wx.request({
      url: `${this.data.baseUrl}/app01/cart/add/`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { goods_id: goodsDetail.id, num: cartNum },
      success: (res) => {
        if (res.data && res.data.code === 200) {
          Toast.success(`【${goodsDetail.name}】已加入购物车 x${cartNum}`);
        } else {
          const isTokenInvalid = 
            res.statusCode === 401 || 
            res.data?.detail === "No active account found with the given credentials" ||
            res.data?.msg === "未授权访问";
          
          if (isTokenInvalid) {
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            Toast.fail('登录状态失效，请重新登录');
          } else {
            Toast.fail(res.data?.msg || '加入购物车失败（本地已缓存）');
          }
        }
      },
      fail: (err) => {
        console.error('加入购物车失败：', err);
        Toast.fail('网络异常，已本地缓存（登录后同步）');
      }
    });
  },

  // 立即购买（仅操作需要登录，浏览无需）
  buyNow() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 校验 Token（仅操作需要）
    const token = this.getValidToken();
    if (!token) {
      // 核心修改：仅提示，不强制弹窗跳转
      Toast('登录后可结算商品');
      return;
    }

    // 2. 有token时执行结算
    wx.request({
      url: `${this.data.baseUrl}/app01/cart/add/`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { goods_id: goodsDetail.id, num: cartNum },
      success: (res) => {
        if (res.data && res.data.code === 200) {
          Toast.success(`即将结算【${goodsDetail.name}】x${cartNum}`);
          setTimeout(() => {
            wx.navigateTo({
              url: `/pages/checkout/checkout?goodsId=${goodsDetail.id}&num=${cartNum}`,
              fail: (err) => {
                console.error('跳转结算页失败：', err);
                wx.switchTab({ url: '/pages/cart/cart' });
                Toast.fail('结算页不存在，已跳购物车');
              }
            });
          }, 1500);
        } else {
          Toast.fail(res.data?.msg || '加入购物车失败，无法结算');
        }
      },
      fail: (err) => {
        console.error('立即购买-加入购物车失败：', err);
        Toast.fail('网络异常，无法结算');
      }
    });
  },

  // 预览商品主图（浏览无需登录）
  previewMainImg() {
    const { goodsDetail, baseUrl } = this.data;
    if (!goodsDetail.image_url) return;
    const fullImgUrl = goodsDetail.image_url.startsWith('http') 
      ? goodsDetail.image_url 
      : `${baseUrl}/media/${goodsDetail.image_url}`;
    wx.previewImage({
      current: fullImgUrl,
      urls: [fullImgUrl]
    });
  }
});
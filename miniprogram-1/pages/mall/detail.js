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
    // 接收从商品列表传递的商品ID（对应 options.id）
    const goodsId = options.id;
    if (!goodsId) {
      Toast.fail('无效的商品ID');
      // 延迟返回上一页，确保提示显示
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
      return;
    }
    this.setData({ goodsId });
    // 获取商品详情
    this.getGoodsDetail();
  },

  // 获取商品详情（无需 Token，仅展示数据）
  getGoodsDetail() {
    const { goodsId, baseUrl } = this.data;
    wx.request({
      url: `${baseUrl}/app01/goods/${goodsId}/`,
      method: 'GET',
      timeout: 5000,
      success: (res) => {
        console.log('商品详情请求成功：', res.data);
        if (res.data && res.data.code === 200) {
          this.setData({ goodsDetail: res.data.data });
        } else {
          Toast.fail('获取商品详情失败');
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

  // 减少数量
  minusNum() {
    const { cartNum } = this.data;
    if (cartNum <= 1) return;
    this.setData({ cartNum: cartNum - 1 });
  },

  // 增加数量
  plusNum() {
    const { cartNum } = this.data;
    this.setData({ cartNum: cartNum + 1 });
  },

  // 手动修改数量
  changeNum(e) {
    const num = parseInt(e.detail.value) || 1;
    this.setData({ cartNum: num < 1 ? 1 : num });
  },

  // 加入购物车（核心修改：携带 Token 请求）
  addToCart() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 获取 Token（缓存优先，全局变量兜底）
    const token = wx.getStorageSync('accessToken') || app.globalData.token;
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再加入购物车',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/login/login' }); // 跳登录页
          }
        }
      });
      return;
    }

    // 2. 直接请求（替换原 app.request，确保 Token 携带）
    wx.request({
      url: `${this.data.baseUrl}/app01/cart/add/`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` // 核心：携带 Token
      },
      data: { goods_id: goodsDetail.id, num: cartNum },
      success: (res) => {
        console.log('加入购物车响应：', res.data);
        if (res.data && res.data.code === 200) {
          Toast.success(`【${goodsDetail.name}】已加入购物车 x${cartNum}`);
        } else {
          // Token 过期/无效时引导重新登录
          if (res.data?.detail === "No active account found with the given credentials" || res.statusCode === 401) {
            wx.removeStorageSync('accessToken'); // 清除无效 Token
            app.globalData.token = '';
            Toast.fail('登录状态失效，请重新登录');
            setTimeout(() => {
              wx.navigateTo({ url: '/pages/login/login' });
            }, 1500);
          } else {
            Toast.fail(res.data?.msg || '加入购物车失败');
          }
        }
      },
      fail: (err) => {
        console.error('加入购物车失败：', err);
        Toast.fail('网络异常，加入购物车失败');
      }
    });
  },

  // 立即购买（携带 Token 校验）
  buyNow() {
    const { goodsDetail } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 获取 Token（缓存优先，全局变量兜底）
    const token = wx.getStorageSync('accessToken') || app.globalData.token;
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再结算',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        }
      });
      return;
    }

    // 2. 提示跳转 + 跳转到购物车 Tab
    Toast.success(`即将结算【${goodsDetail.name}】`);
    setTimeout(() => {
      wx.switchTab({
        url: '/pages/cart/cart',
        fail: (err) => {
          console.error('跳转购物车失败：', err);
          Toast.fail('购物车页面不存在');
        }
      });
    }, 1500);
  },

  // 预览商品主图
  previewMainImg() {
    const { goodsDetail } = this.data;
    if (!goodsDetail.image_url) return;
    wx.previewImage({
      current: goodsDetail.image_url,
      urls: [goodsDetail.image_url]
    });
  }
});
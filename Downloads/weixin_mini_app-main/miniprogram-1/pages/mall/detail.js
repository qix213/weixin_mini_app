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

  // 获取商品详情（对接你的后端详情接口）
  getGoodsDetail() {
    const { goodsId, baseUrl } = this.data;
    wx.request({
      // 后端详情接口：goods/{id}/（你的 GoodsViewSet 已支持）
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

  // 加入购物车（对接后端）
  addToCart() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 先校验是否登录（无 Token 直接引导登录）
    if (!app.globalData.token) {
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

    // 2. 调用封装的 request 方法（自动携带 Token）
    app.request({
      url: '/app01/cart/add/', // 拼接后是 http://localhost:8000/app01/cart/add/
      method: 'POST',
      data: { goods_id: goodsDetail.id, num: cartNum }
    }).then((res) => {
      if (res.data && res.data.code === 200) {
        Toast.success(`【${goodsDetail.name}】已加入购物车 x${cartNum}`);
      } else {
        Toast.fail(res.data?.msg || '加入购物车失败');
      }
    }).catch((err) => {
      console.error('加入购物车失败：', err);
      Toast.fail('网络异常，加入购物车失败');
    });
  },

  // 立即购买（修复 Toast 错误 + 跳转购物车 Tab）
  buyNow() {
    const { goodsDetail } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 先校验登录（和加入购物车逻辑一致）
    if (!app.globalData.token) {
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

    // 2. 提示跳转 + 跳转到购物车 Tab（核心修改）
    Toast.success(`即将结算【${goodsDetail.name}】`);
    setTimeout(() => {
      // 关键：用 switchTab 跳转 Tab 页，路径对应 app.json 中的购物车 Tab 路径
      wx.switchTab({
        url: '/pages/cart/cart', // 替换为你实际的购物车 Tab 页面路径
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
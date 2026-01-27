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
    // 获取商品详情（适配401授权）
    this.getGoodsDetail();
  },

  // 获取商品详情（核心修复：适配401授权，携带Token请求）
  getGoodsDetail() {
    const { goodsId, baseUrl } = this.data;
    // 1. 获取Token（即使商品详情应公开，后端要求则携带）
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    // 2. 构造请求头（有Token则携带）
    const header = {
      'Content-Type': 'application/json'
    };
    if (token) {
      header['Authorization'] = `Bearer ${token}`;
    }

    wx.request({
      url: `${baseUrl}/app01/goods/${goodsId}/`,
      method: 'GET',
      header: header, // 携带Token（如果有）
      timeout: 5000,
      success: (res) => {
        console.log('商品详情请求成功：', res.data);
        // 处理后端不同的响应格式
        if (res.statusCode === 200) {
          // 情况1：后端返回自定义格式（code=200）
          if (res.data.code === 200) {
            this.setData({ goodsDetail: res.data.data });
          }
          // 情况2：后端返回DRF默认序列化格式（无code，直接是商品数据）
          else if (res.data.id) {
            this.setData({ goodsDetail: res.data });
          } else {
            Toast.fail('获取商品详情失败：数据格式异常');
            this.setData({ goodsDetail: {} });
          }
        }
        // 处理401未授权
        else if (res.statusCode === 401) {
          Toast.fail('查看商品详情需先登录');
          this.setData({ goodsDetail: {} });
          // 提示登录，3秒后自动弹窗
          setTimeout(() => {
            wx.showModal({
              title: '提示',
              content: '查看商品详情需要登录账号',
              confirmText: '去登录',
              cancelText: '取消',
              success: (res) => {
                if (res.confirm) {
                  // 跳转登录页，携带返回参数
                  wx.navigateTo({ 
                    url: `/pages/login/login?redirect=detail&id=${goodsId}` 
                  });
                } else {
                  // 取消则返回上一页
                  wx.navigateBack();
                }
              }
            });
          }, 1500);
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

  // 【核心优化】统一获取并校验 Token 的工具方法
  getValidToken() {
    // 统一 Token 来源：缓存的 accessToken 优先，全局变量兜底（和登录页保持一致）
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    console.log('当前获取的 Token：', token ? '已获取有效Token' : '无Token');
    return token;
  },

  // 加入购物车（优化授权校验 + 错误处理）
  addToCart() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 校验 Token
    const token = this.getValidToken();
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再加入购物车',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            // 跳转登录页时携带返回页参数（登录后可回跳）
            wx.navigateTo({ 
              url: `/pages/login/login?redirect=detail&id=${goodsDetail.id}` 
            });
          }
        }
      });
      return;
    }

    // 2. 加入购物车请求（携带 Token）
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
          // Token 过期/无效的全面判断
          const isTokenInvalid = 
            res.statusCode === 401 || 
            res.data?.detail === "No active account found with the given credentials" ||
            res.data?.msg === "未授权访问";
          
          if (isTokenInvalid) {
            // 清除无效 Token，引导重新登录
            wx.removeStorageSync('accessToken');
            app.globalData.accessToken = '';
            Toast.fail('登录状态失效，请重新登录');
            setTimeout(() => {
              wx.navigateTo({ url: `/pages/login/login?redirect=detail&id=${goodsDetail.id}` });
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

  // 立即购买（优化授权校验 + 跳结算页而非购物车）
  buyNow() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    // 1. 校验 Token
    const token = this.getValidToken();
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再结算',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            // 跳转登录页，携带商品ID（登录后回跳详情页）
            wx.navigateTo({ 
              url: `/pages/login/login?redirect=detail&id=${goodsDetail.id}` 
            });
          }
        }
      });
      return;
    }

    // 2. 先加入购物车，再跳结算页（更符合业务逻辑）
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
            // 跳转到结算页（而非购物车），携带订单相关参数
            wx.navigateTo({
              url: `/pages/checkout/checkout?goodsId=${goodsDetail.id}&num=${cartNum}`,
              fail: (err) => {
                console.error('跳转结算页失败：', err);
                // 兜底跳购物车
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

  // 预览商品主图（优化图片拼接）
  previewMainImg() {
    const { goodsDetail, baseUrl } = this.data;
    if (!goodsDetail.image_url) return;
    // 拼接完整图片URL（适配后端返回相对路径的情况）
    const fullImgUrl = goodsDetail.image_url.startsWith('http') 
      ? goodsDetail.image_url 
      : `${baseUrl}/media/${goodsDetail.image_url}`;
    wx.previewImage({
      current: fullImgUrl,
      urls: [fullImgUrl]
    });
  }
});
import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    goodsId: '',
    goodsDetail: {},
    loading: true,
    baseUrl: 'http://localhost:8000',
    cartNum: 1,
    currentSwipeIndex: 0,
    imageList: [],
    // 新增：积分商品相关字段
    isPointGoods: false,
    pointPrice: 0
  },

  onLoad(options) {
    const goodsId = options.goods_id;
    if (!goodsId) {
      Toast.fail('无效的商品ID');
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
      return;
    }
    this.setData({ goodsId });
    this.getGoodsDetail();
  },

  // 统一判断是否为积分商品（和列表页逻辑一致）
  isPointGoods(item) {
    const pointField = item.isPointGoods || item.can_point_exchange || item.canPointExchange || false;
    const hasPointPrice = item.pointPrice && Number(item.pointPrice) > 0;
    
    let isPoint = false;
    if (typeof pointField === 'string') {
      isPoint = pointField.toLowerCase() === 'true';
    } else if (typeof pointField === 'number') {
      isPoint = pointField === 1;
    } else {
      isPoint = !!pointField;
    }
    return isPoint || hasPointPrice;
  },

  // 修复：处理URL双斜杠 + 强化空值判断 + 新增积分价格计算
  getGoodsDetail() {
    const { goodsId, baseUrl } = this.data;

    wx.request({
      url: `${baseUrl}/app01/goods/${goodsId}/`,
      method: 'GET',
      header: { 'Content-Type': 'application/json' },
      timeout: 5000,
      success: (res) => {
        console.log('商品详情完整返回数据：', res.data);
        if (res.statusCode === 200 && res.data.code === 200) {
          let goodsData = res.data.data;
          let imageList = [];

          // 修复1：处理主图URL双斜杠
          if (goodsData.image_url) {
            const fixedMainUrl = goodsData.image_url.replace('//media/', '/media/');
            imageList.push(fixedMainUrl);
          }

          // 修复2：处理组图URL双斜杠 + 按order排序
          if (goodsData.images && goodsData.images.length > 0) {
            const sortedImages = goodsData.images.sort((a, b) => a.order - b.order);
            sortedImages.forEach(img => {
              if (img.image_url) {
                const fixedImgUrl = img.image_url.replace('//media/', '/media/');
                imageList.push(fixedImgUrl);
              }
            });
          }

          // 新增：判断是否为积分商品 + 计算积分价格（和列表页逻辑一致）
          const isPointGoods = this.isPointGoods(goodsData);
          let pointPrice = 0;
          if (isPointGoods) {
            // 严格处理member_price，避免转数字失败
            const memberPriceStr = (goodsData.member_price || '0').toString().replace(/[^0-9.]/g, '');
            const memberPrice = parseFloat(memberPriceStr) || 0;
            pointPrice = Math.floor(memberPrice * 100); // 会员价转积分（和列表页一致）
            pointPrice = Number(pointPrice);
          }

          // 验证：打印积分相关数据
          console.log('积分商品判断：', isPointGoods, '积分价格：', pointPrice);
          this.setData({ 
            goodsDetail: goodsData,
            imageList: imageList,
            isPointGoods: isPointGoods,
            pointPrice: pointPrice
          });
        } else {
          Toast.fail('获取商品详情失败：' + (res.data?.msg || '数据格式异常'));
        }
      },
      fail: (err) => {
        console.error('商品详情请求失败：', err);
        Toast.fail('网络异常，详情加载失败');
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  imageLoadError(e) {
    console.error('图片加载失败：', e.detail.errMsg, 'URL：', e.currentTarget.src);
    Toast.fail('图片加载失败，请检查URL');
  },

  imageLoadSuccess(e) {
    console.log('图片加载成功：', e.currentTarget.src);
  },

  onSwipeChange(e) {
    this.setData({ currentSwipeIndex: e.detail.current });
  },

  previewImages(e) {
    const { imageList } = this.data;
    if (imageList.length === 0) return;
    const currentIndex = e.currentTarget.dataset.index || 0;
    wx.previewImage({
      current: imageList[currentIndex],
      urls: imageList
    });
  },

  minusNum() {
    const { cartNum } = this.data;
    if (cartNum <= 1) return;
    this.setData({ cartNum: cartNum - 1 });
  },

  plusNum() {
    const { cartNum } = this.data;
    this.setData({ cartNum: cartNum + 1 });
  },

  changeNum(e) {
    const num = parseInt(e.detail.value) || 1;
    this.setData({ cartNum: num < 1 ? 1 : num });
  },

  getValidToken() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    return token;
  },

  addToCart() {
    const { goodsDetail, cartNum } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    const token = this.getValidToken();
    if (!token) {
      Toast('登录后可将商品同步到购物车（已本地缓存）');
      const cartList = wx.getStorageSync('cartList') || {};
      cartList[goodsDetail.id] = cartNum;
      wx.setStorageSync('cartList', cartList);
      return;
    }

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
          // 适配：积分商品/普通商品提示文案
          const tipText = this.data.isPointGoods 
            ? `【${goodsDetail.name}】已加入购物车 x${cartNum}（需${this.data.pointPrice * cartNum}积分）`
            : `【${goodsDetail.name}】已加入购物车 x${cartNum}`;
          Toast.success(tipText);
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

  buyNow() {
    const { goodsDetail, cartNum, isPointGoods, pointPrice } = this.data;
    if (!goodsDetail.id) {
      Toast.fail('商品信息异常');
      return;
    }

    const token = this.getValidToken();
    if (!token) {
      Toast('登录后可结算商品');
      return;
    }

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
          // 适配：积分商品/普通商品提示文案
          const tipText = isPointGoods
            ? `即将结算【${goodsDetail.name}】x${cartNum}（需${pointPrice * cartNum}积分）`
            : `即将结算【${goodsDetail.name}】x${cartNum}`;
          Toast.success(tipText);
          
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

  previewMainImg() {}
});
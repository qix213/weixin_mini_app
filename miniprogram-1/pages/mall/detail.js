import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    goodsId: '',
    goodsDetail: {},
    loading: true,
    baseUrl: 'http://175.178.57.168:8000',
    cartNum: 1,
    currentSwipeIndex: 0,
    
    mediaList: [], 
    isPlayingVideo: false, 
    
    isPointGoods: false,
    pointPrice: 0
  },

  onLoad(options) {
    const goodsId = options.goods_id;
    if (!goodsId) {
      Toast.fail('无效的商品ID');
      setTimeout(() => { wx.navigateBack(); }, 1500);
      return;
    }
    this.setData({ goodsId });
    this.getGoodsDetail();
  },

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

  // 🚀 核心修复：极致健壮的 URL 格式化工具
  formatUrl(url) {
    if (!url) return '';
    let fixedUrl = url.replace('//media/', '/media/');
    // 如果不是 http 开头，强制拼接 baseUrl
    if (!fixedUrl.startsWith('http')) {
      fixedUrl = this.data.baseUrl + (fixedUrl.startsWith('/') ? fixedUrl : '/' + fixedUrl);
    }
    return fixedUrl;
  },

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
          let mediaList = [];

          // 1. 处理主图
          if (goodsData.image_url) {
            mediaList.push({ type: 0, url: this.formatUrl(goodsData.image_url) });
          }

          // 2. 处理多图/视频数组
          if (goodsData.images && goodsData.images.length > 0) {
            const sortedImages = goodsData.images.sort((a, b) => a.order - b.order);
            sortedImages.forEach(item => {
              let url = item.media_url || (Number(item.media_type) === 1 ? item.video_url : item.image_url);
              if (url) {
                mediaList.push({ 
                  type: item.media_type !== undefined ? Number(item.media_type) : 0, 
                  url: this.formatUrl(url) 
                });
              }
            });
          }

          // 去重处理（防止主图在images里重复出现）
          const uniqueMediaList = Array.from(new Set(mediaList.map(a => a.url)))
            .map(url => {
              return mediaList.find(a => a.url === url)
            });

          // 3. 计算积分
          const isPointGoods = this.isPointGoods(goodsData);
          let pointPrice = 0;
          if (isPointGoods) {
            const memberPriceStr = (goodsData.member_price || '0').toString().replace(/[^0-9.]/g, '');
            const memberPrice = parseFloat(memberPriceStr) || 0;
            pointPrice = Number(Math.floor(memberPrice * 100)); 
          }

          console.log('最终清洗并拼接完整的媒体列表：', uniqueMediaList);
          this.setData({ 
            goodsDetail: goodsData,
            mediaList: uniqueMediaList,
            isPointGoods: isPointGoods,
            pointPrice: pointPrice
          });
        } else {
          Toast.fail('获取详情失败：' + (res.data?.msg || '异常'));
        }
      },
      fail: (err) => {
        console.error('详情请求失败：', err);
        Toast.fail('网络异常');
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  onSwipeChange(e) { this.setData({ currentSwipeIndex: e.detail.current }); },
  onVideoPlay() { this.setData({ isPlayingVideo: true }); },
  onVideoPause() { this.setData({ isPlayingVideo: false }); },

  previewImages(e) {
    const { mediaList } = this.data;
    if (mediaList.length === 0) return;
    
    const currentIndex = e.currentTarget.dataset.index || 0;
    const currentMedia = mediaList[currentIndex];
    
    if (currentMedia.type === 1) return; // 点击视频不触发图片预览

    const pureImgUrls = mediaList.filter(m => m.type === 0).map(m => m.url);
    wx.previewImage({
      current: currentMedia.url,
      urls: pureImgUrls
    });
  },

  imageLoadError(e) { console.error('图片加载失败，URL：', e.currentTarget.dataset.src); },

  minusNum() { if (this.data.cartNum > 1) this.setData({ cartNum: this.data.cartNum - 1 }); },
  plusNum() { this.setData({ cartNum: this.data.cartNum + 1 }); },
  changeNum(e) {
    const num = parseInt(e.detail.value) || 1;
    this.setData({ cartNum: num < 1 ? 1 : num });
  },

  getValidToken() { return wx.getStorageSync('accessToken') || app.globalData.accessToken; },

  addToCart() {
    const { goodsDetail, cartNum, isPointGoods, pointPrice } = this.data;
    if (!goodsDetail.id) return Toast.fail('商品信息异常');

    const token = this.getValidToken();
    if (!token) {
      Toast('本地已暂存，登录后同步');
      const cartList = wx.getStorageSync('cartList') || {};
      cartList[goodsDetail.id] = (cartList[goodsDetail.id] || 0) + cartNum;
      wx.setStorageSync('cartList', cartList);
      return;
    }

    wx.request({
      url: `${this.data.baseUrl}/app01/cart/add/`,
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      data: { goods_id: goodsDetail.id, num: cartNum },
      success: (res) => {
        if (res.data?.code === 200) {
          Toast.success(isPointGoods ? `已加购 x${cartNum}\n需${pointPrice * cartNum}积分` : `已加购 x${cartNum}`);
        } else if (res.statusCode === 401) {
          wx.removeStorageSync('accessToken');
          app.globalData.accessToken = '';
          Toast.fail('状态失效，请重新登录');
        } else {
          Toast.fail(res.data?.msg || '加入失败');
        }
      },
      fail: () => Toast.fail('网络异常')
    });
  },
// ======== 🚀 新增：统一管理视频暂停的利器 ========
pauseAllVideos() {
  const { mediaList } = this.data;
  mediaList.forEach((item, index) => {
    // 只要是视频类型，就创建上下文并强制暂停
    if (item.type === 1) {
      const videoContext = wx.createVideoContext(`goods-video-${index}`, this);
      videoContext.pause();
    }
  });
  // 重置播放状态，让轮播图恢复自动轮播
  this.setData({ isPlayingVideo: false });
},

// ======== 🚀 优化：轮播滑动时，触发暂停 ========
onSwipeChange(e) { 
  this.setData({ currentSwipeIndex: e.detail.current }); 
  // 滑动后立刻暂停之前可能在播放的视频
  this.pauseAllVideos();
},

// ======== 🚀 新增：生命周期函数，离开页面时触发暂停 ========
onHide() {
  // 比如用户点开全屏预览图片，或者切出微信回消息，视频也要停掉
  this.pauseAllVideos();
},

onVideoPlay() { this.setData({ isPlayingVideo: true }); },
onVideoPause() { this.setData({ isPlayingVideo: false }); },
  buyNow() {
    const { goodsDetail, cartNum, isPointGoods, pointPrice } = this.data;
    if (!goodsDetail.id) return Toast.fail('商品信息异常');

    const token = this.getValidToken();
    if (!token) return Toast('请先登录后结算');

    wx.request({
      url: `${this.data.baseUrl}/app01/cart/add/`,
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      data: { goods_id: goodsDetail.id, num: cartNum },
      success: (res) => {
        if (res.data?.code === 200) {
          Toast.success(isPointGoods ? `即将结算\n需${pointPrice * cartNum}积分` : `即将结算 x${cartNum}`);
          setTimeout(() => {
            wx.navigateTo({
              url: `/pages/checkout/checkout?goodsId=${goodsDetail.id}&num=${cartNum}`,
              fail: () => wx.switchTab({ url: '/pages/cart/cart' })
            });
          }, 1500);
        } else {
          Toast.fail(res.data?.msg || '无法结算');
        }
      },
      fail: () => Toast.fail('网络异常')
    });
  }
});
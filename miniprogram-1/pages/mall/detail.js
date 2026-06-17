import Toast from '@vant/weapp/toast/toast';
const app = getApp();

Page({
  data: {
    goodsId: '',
    goodsDetail: {},
    loading: true,
    cartNum: 1,
    currentSwipeIndex: 0,
    
    mediaList: [], 
    isPlayingVideo: false, 
    
    isPointGoods: false,
    pointPrice: 0,

    // --- 弹窗控制 ---
    showPopup: false,
    actionType: '' // 'cart' | 'buy'
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

  formatUrl(url) {
    if (!url) return '';
    let fixedUrl = url.replace('//media/', '/media/');
    const baseUrl = app.globalData.baseUrl;
    
    if (!fixedUrl.startsWith('http')) {
      fixedUrl = baseUrl + (fixedUrl.startsWith('/') ? fixedUrl : '/' + fixedUrl);
    }
    return fixedUrl;
  },

  getGoodsDetail() {
    const { goodsId } = this.data;

    app.request({
      url: `/app01/goods/${goodsId}/`, 
      method: 'GET'
    }).then(res => {
      if (res.data.code === 200) {
        let goodsData = res.data.data;
        let mediaList = [];

        if (goodsData.image_url) {
          mediaList.push({ type: 0, url: this.formatUrl(goodsData.image_url) });
        }

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

        const uniqueMediaList = Array.from(new Set(mediaList.map(a => a.url)))
          .map(url => {
            return mediaList.find(a => a.url === url)
          });

        const isPointGoods = this.isPointGoods(goodsData);
        let pointPrice = 0;
        if (isPointGoods) {
          const memberPriceStr = (goodsData.member_price || '0').toString().replace(/[^0-9.]/g, '');
          const memberPrice = parseFloat(memberPriceStr) || 0;
          pointPrice = Number(Math.floor(memberPrice * 100)); 
        }

        this.setData({ 
          goodsDetail: goodsData,
          mediaList: uniqueMediaList,
          isPointGoods: isPointGoods,
          pointPrice: pointPrice,
          loading: false
        });
      } else {
        Toast.fail('获取详情失败：' + (res.data?.msg || '异常'));
        this.setData({ loading: false });
      }
    }).catch(err => {
      Toast.fail('网络异常');
      this.setData({ loading: false });
    });
  },

  onSwipeChange(e) { 
    this.setData({ currentSwipeIndex: e.detail.current }); 
    this.pauseAllVideos();
  },
  
  onVideoPlay() { this.setData({ isPlayingVideo: true }); },
  onVideoPause() { this.setData({ isPlayingVideo: false }); },
  
  pauseAllVideos() {
    const { mediaList } = this.data;
    mediaList.forEach((item, index) => {
      if (item.type === 1) {
        const videoContext = wx.createVideoContext(`goods-video-${index}`, this);
        videoContext.pause();
      }
    });
    this.setData({ isPlayingVideo: false });
  },

  onHide() {
    this.pauseAllVideos();
  },

  previewImages(e) {
    const { mediaList } = this.data;
    if (mediaList.length === 0) return;
    
    const currentIndex = e.currentTarget.dataset.index || 0;
    const currentMedia = mediaList[currentIndex];
    
    if (currentMedia.type === 1) return;

    const pureImgUrls = mediaList.filter(m => m.type === 0).map(m => m.url);
    wx.previewImage({
      current: currentMedia.url,
      urls: pureImgUrls
    });
  },

  imageLoadError(e) { console.error('图片加载失败，URL：', e.currentTarget.dataset.src); },

  // ================= 弹窗与数量控件逻辑 =================
  openPopup(e) {
    const action = e.currentTarget.dataset.action; // 'cart' 或 'buy'
    this.setData({ 
      showPopup: true,
      actionType: action,
      cartNum: 1 // 每次打开重置为1
    });
  },

  closePopup() {
    this.setData({ showPopup: false });
  },

  minusNum() { if (this.data.cartNum > 1) this.setData({ cartNum: this.data.cartNum - 1 }); },
  plusNum() { this.setData({ cartNum: this.data.cartNum + 1 }); },
  changeNum(e) {
    const num = parseInt(e.detail.value) || 1;
    this.setData({ cartNum: num < 1 ? 1 : num });
  },

  onConfirmAction() {
    if (this.data.actionType === 'cart') {
      this.executeAddToCart();
    } else {
      this.executeBuyNow();
    }
  },

  executeAddToCart() {
    const { goodsDetail, cartNum, isPointGoods, pointPrice } = this.data;
    this.closePopup();

    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      Toast('本地已暂存，登录后同步');
      const cartList = wx.getStorageSync('cartList') || {};
      cartList[goodsDetail.id] = (cartList[goodsDetail.id] || 0) + cartNum;
      wx.setStorageSync('cartList', cartList);
      return;
    }

    app.request({
      url: '/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsDetail.id, num: cartNum }
    }).then(res => {
      if (res.data?.code === 200) {
        Toast.success(isPointGoods ? `已加购 x${cartNum}\n需${pointPrice * cartNum}积分` : `已加购 x${cartNum}`);
      } else {
        Toast.fail(res.data?.msg || '加入失败');
      }
    }).catch(err => {
      Toast.fail('网络异常');
    });
  },

  executeBuyNow() {
    const { goodsDetail, cartNum, isPointGoods, pointPrice } = this.data;
    this.closePopup();

    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) return Toast('请先登录后结算');

    app.request({
      url: '/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsDetail.id, num: cartNum }
    }).then(res => {
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
    }).catch(err => {
      Toast.fail('网络异常');
    });
  }
});
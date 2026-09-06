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
    showPopup: false,
    actionType: '',
    
    userType: 1, 
    mainPriceLabel: '',
    mainPriceValue: '',
    subPriceLabel: '',
    subPriceValue: ''
  },

  onLoad(options) {
    const memberInfo = app.globalData.memberInfo || wx.getStorageSync('memberInfo') || {};
    this.setData({ userType: memberInfo.user_type || 1 });

    const goodsId = options.goods_id;
    if (!goodsId) {
      wx.showToast({ title: '无效的商品ID', icon: 'error' });
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
    const { goodsId, userType } = this.data;

    app.request({
      url: `/app01/goods/${goodsId}/`, 
      method: 'GET'
    }).then(res => {
      if (res.data && res.data.code === 200) {
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
              mediaList.push({ type: item.media_type !== undefined ? Number(item.media_type) : 0, url: this.formatUrl(url) });
            }
          });
        }

        const uniqueMediaList = Array.from(new Set(mediaList.map(a => a.url))).map(url => mediaList.find(a => a.url === url));

        const isPointGoods = this.isPointGoods(goodsData);
        let pointPrice = 0;
        if (isPointGoods) {
          const memberPriceStr = (goodsData.member_price || '0').toString().replace(/[^0-9.]/g, '');
          pointPrice = Number(Math.floor((parseFloat(memberPriceStr) || 0) * 100)); 
        }

        // ==========================================
        // ✅ 前端展示算价逻辑
        // ==========================================
        const currentLevel = parseInt(userType) || 1;
        const memberPrice = parseFloat(goodsData.member_price || 0).toFixed(2);
        const originalPrice = parseFloat(goodsData.original_price || 0).toFixed(2);
        
        let mainPriceLabel = '', mainPriceValue = '', subPriceLabel = '', subPriceValue = '';

        if (currentLevel <= 1) {
          mainPriceLabel = '零售价';
          mainPriceValue = originalPrice;
          subPriceLabel = '会员价';
          subPriceValue = memberPrice;
        } else {
          mainPriceLabel = '会员价';
          mainPriceValue = memberPrice;
          subPriceLabel = '零售价';
          subPriceValue = originalPrice;
        }

        this.setData({ 
          goodsDetail: goodsData,
          mediaList: uniqueMediaList,
          isPointGoods: isPointGoods || false,
          pointPrice: pointPrice,
          mainPriceLabel: mainPriceLabel,
          mainPriceValue: mainPriceValue,
          subPriceLabel: subPriceLabel,
          subPriceValue: subPriceValue,
          loading: false
        });
      } else {
        const errorMsg = (res.data && res.data.msg) ? res.data.msg : '异常';
        wx.showToast({ title: '获取详情失败：' + errorMsg, icon: 'none' });
        this.setData({ loading: false });
      }
    }).catch(err => {
      wx.showToast({ title: '网络异常', icon: 'none' });
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

  imageLoadError(e) { console.error('图片加载失败', e.currentTarget.dataset.src); },

  openPopup(e) {
    const action = e.currentTarget.dataset.action; 
    this.setData({ showPopup: true, actionType: action, cartNum: 1 });
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
    const { goodsDetail, cartNum, isPointGoods } = this.data;
    this.closePopup();

    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      wx.showToast({ title: '本地已暂存，登录后同步', icon: 'none' });
      const cartList = wx.getStorageSync('cartList') || {};
      cartList[goodsDetail.id] = (cartList[goodsDetail.id] || 0) + cartNum;
      wx.setStorageSync('cartList', cartList);
      return;
    }

    app.request({
      url: '/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsDetail.id, num: cartNum } // ✅ 只传ID和数量，绝对安全
    }).then(res => {
      if (res.data && res.data.code === 200) {
        wx.showToast({ title: isPointGoods ? `加购 x${cartNum}` : `加购 x${cartNum}`, icon: 'success' });
      } else {
        const errorMsg = (res.data && res.data.msg) ? res.data.msg : '加入失败';
        wx.showToast({ title: errorMsg, icon: 'none' });
      }
    }).catch(err => {
      wx.showToast({ title: '网络异常', icon: 'none' });
    });
  },

  executeBuyNow() {
    const { goodsDetail, cartNum } = this.data;
    this.closePopup();
  
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      return wx.showToast({ title: '请先登录后结算', icon: 'none' });
    }
  
    app.request({
      url: '/app01/cart/add/',
      method: 'POST',
      data: { goods_id: goodsDetail.id, num: cartNum } // ✅ 只传ID和数量，绝对安全
    }).then(res => {
      if (res.data && res.data.code === 200) {
        wx.showToast({ title: '即将结算', icon: 'success' });
        setTimeout(() => {
          wx.navigateTo({
            url: `/pages/checkout/checkout?goodsId=${goodsDetail.id}&num=${cartNum}`,
            fail: () => wx.switchTab({ url: '/pages/cart/cart' })
          });
        }, 1500);
      } else {
        const errorMsg = (res.data && res.data.msg) ? res.data.msg : '无法结算';
        wx.showToast({ title: errorMsg, icon: 'none' });
      }
    }).catch(err => {
      wx.showToast({ title: '网络异常', icon: 'none' });
    });
  }
});
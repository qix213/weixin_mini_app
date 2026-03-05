const app = getApp();
Page({
  data: {
    typeName: '',
    originalAmount: '0.00',    // 订单总额（固定不变）
    actualAmount: '0.00',      // 实付金额
    pointDeductPoints: 0,      // 本次使用的积分数量（下单时已确定）
    
    scene: 'order',
    orderId: '',
    payMethods: [        
      { 
        id: 1, 
        name: '微信支付', 
        icon: 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/wechat.svg', 
        selected: true 
      },
      { 
        id: 2, 
        name: '支付宝支付', 
        icon: 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/alipay.svg', 
        selected: false 
      }
    ],
    selectedPayMethod: 1,
    payLoading: false,

    couponList: [],
    couponDropdownOptions: [],
    selectedCoupon: null,
    noCouponTip: '暂无可用优惠券',
    couponIndex: 0
  },

  onLoad(options) {
    const scene = options.scene || 'order';
    const typeName = decodeURIComponent(options.typeName || (scene === 'member' ? '会员缴费' : '商品订单支付'));
    
    // 订单总额
    const originalAmount = Number(options.amount || options.totalAll || 0).toFixed(2);
    // 实付金额
    const actualAmount = Number(options.actualAmount || originalAmount).toFixed(2);
    // 积分抵扣数量（从下单页传过来）
    const pointDeductPoints = parseInt(options.deduct_point || 0);
    
    const orderId = options.orderId || '';

    this.setData({
      scene,
      typeName,
      originalAmount,
      actualAmount,
      pointDeductPoints,
      orderId
    });

    this.getCouponList();
  },

  // 日期格式化
  formatDate(dateStr) {
    if (!dateStr) return '永久有效';
    if (typeof dateStr === 'number') {
      dateStr = dateStr.toString().length === 13 ? dateStr : dateStr * 1000;
      const date = new Date(dateStr);
      return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
    }
    if (typeof dateStr === 'string') {
      const reg = /(\d{4})[-/](\d{1,2})[-/](\d{1,2})/;
      const match = dateStr.match(reg);
      if (match) {
        return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
      }
    }
    return '永久有效';
  },

  // 获取优惠券
  getCouponList() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      this.setData({
        couponDropdownOptions: [{value: '', label: '不使用优惠券'}],
        noCouponTip: '请先登录'
      });
      return;
    }

    wx.showLoading({ title: '加载优惠券...' });
    app.request({
      url: 'http://localhost:8000/app01/user/coupons/', 
      method: 'GET',
      header: {
        'Authorization': `Bearer ${accessToken}`,
        'content-type': 'application/json'
      },
      data: { only_valid: true }
    }).then(res => {
      wx.hideLoading();
      const couponList = res.data?.data?.coupons || [];
      
      const formatCoupon = couponList.map(item => {
        const coupon = item.coupon || {};
        const couponType = coupon.coupon_type || item.coupon_type || 1;
        let discountDesc = '';
        if (couponType === 1) {
          const money = Number(coupon.money || item.money || 0).toFixed(2);
          discountDesc = `抵扣¥${money}元`;
        } else if (couponType === 2) {
          const discountRate = Number(coupon.discount_rate || item.discount_rate || 1);
          discountDesc = `${(discountRate * 10).toFixed(1)}折`;
        }

        const expireTime = coupon.expire_time || item.expire_time || coupon.end_time || item.end_time || '';
        const expireDesc = this.formatDate(expireTime);
        
        return {
          ...item,
          discountDesc,
          expireDesc,
          id: item.id || '',
          title: coupon.title || item.title || '优惠券',
          coupon_type: couponType
        };
      });

      const couponDropdownOptions = [
        {value: '', label: '不使用优惠券'}, 
        ...formatCoupon.map(item => ({
          value: item.id,
          label: `${item.title}（${item.discountDesc} | 有效期至${item.expireDesc}）`
        }))
      ];

      this.setData({
        couponList: formatCoupon,
        couponDropdownOptions,
        noCouponTip: formatCoupon.length === 0 ? '暂无可用优惠券' : ''
      });
    }).catch(err => {
      wx.hideLoading();
      this.setData({
        couponDropdownOptions: [{value: '', label: '不使用优惠券'}],
        noCouponTip: '加载优惠券失败'
      });
    });
  },

  onCouponChangeNative(e) {
    const index = Number(e.detail.value);
    if (index === 0) {
      this.cancelCoupon();
      return;
    }
    const selectedCoupon = this.data.couponList[index - 1] || null;
    if (selectedCoupon) {
      this.setData({
        couponIndex: index,
        selectedCoupon
      });
    } else {
      this.cancelCoupon();
    }
  },

  cancelCoupon() {
    this.setData({
      couponIndex: 0,
      selectedCoupon: null
    });
  },

  // 切换支付方式
  switchPayMethod(e) {
    const payMethodId = e.currentTarget.dataset.methodid;
    const payMethods = this.data.payMethods.map(method => {
      method.selected = method.id === payMethodId;
      return method;
    });
    this.setData({
      payMethods,
      selectedPayMethod: payMethodId
    });
  },

  // 支付
  handlePay() {
    const { payLoading } = this.data;
    if (payLoading) return;

    this.setData({ payLoading: true });
    const selectedMethod = this.data.payMethods.find(m => m.id === this.data.selectedPayMethod).name;

    setTimeout(() => {
      this.setData({ payLoading: false });
      wx.showToast({
        title: `${selectedMethod}支付成功`,
        icon: 'success',
        duration: 2000
      });
      this.paySuccess(this.data.orderId, this.data.selectedCoupon);
    }, 1500);
  },

  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

  // 使用优惠券
  useCoupon(couponId, orderSn) {
    return new Promise((resolve) => {
      if (!couponId || !orderSn) {
        resolve();
        return;
      }
      const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      app.request({
        url: 'http://localhost:8000/app01/user/coupons/use/',
        method: 'POST',
        header: {
          'content-type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        data: { 
          coupon_id: couponId,
          order_sn: orderSn 
        }
      }).finally(() => resolve());
    });
  },

  // 支付成功回调（只通知后端，积分扣减由后端处理）
  paySuccess(orderId, selectedCoupon) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.switchTab({url: '/pages/mall/mall'});
      return;
    }

    const getOrderSn = (orderId) => {
      return new Promise((resolve) => {
        wx.request({
          url: 'http://localhost:8000/app01/order/detail/',
          method: 'GET',
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          data: { order_id: orderId },
          success: (res) => {
            const orderSn = res.data?.data?.order_sn || '';
            resolve(orderSn);
          },
          fail: () => resolve('')
        });
      });
    };

    const callPaySuccessApi = () => {
      return new Promise((resolve) => {
        wx.request({
          url: 'http://localhost:8000/app01/order/pay_success/',
          method: 'POST',
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          data: {
            order_id: orderId,
            pay_method: this.data.selectedPayMethod,
            pay_no: 'test_pay_no_' + Date.now(),
            actual_amount: this.data.actualAmount,
            deduct_point: this.data.pointDeductPoints // 可选：把积分抵扣数传给后端
          },
          complete: () => resolve()
        });
      });
    };

    const clearCart = (isPrecise = false) => {
      let url = 'http://localhost:8000/app01/cart/clear/';
      if (isPrecise && orderId) url = `http://localhost:8000/app01/cart/clear/${orderId}/`;
      return new Promise((resolve) => {
        wx.request({
          url, method: 'POST',
          header: { Authorization: `Bearer ${accessToken}` },
          complete: () => resolve()
        });
      });
    };

    getOrderSn(orderId).then(orderSn => {
      callPaySuccessApi().then(() => {
        const couponPromise = selectedCoupon && orderSn 
          ? this.useCoupon(selectedCoupon.id, orderSn) 
          : Promise.resolve();

        couponPromise.finally(() => {
          clearCart(true).finally(() => {
            clearCart(false).finally(() => {
              wx.switchTab({ url: '/pages/mall/mall' });
            });
          });
        });
      });
    });
  }
});
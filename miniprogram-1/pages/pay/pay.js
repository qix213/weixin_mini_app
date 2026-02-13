const app = getApp();
Page({
  data: {
    typeName: '',
    originalAmount: 0, // 原价（两位小数）
    actualAmount: 0,   // 实际支付金额（两位小数）
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
    couponIndex: 0 // 默认选中第一个选项（不使用优惠券）
  },

  onLoad(options) {
    const scene = options.scene || 'order';
    const typeName = decodeURIComponent(options.typeName || (scene === 'member' ? '会员缴费' : '商品订单支付'));
    // 【修改1】onLoad中初始化金额时保留两位小数
    const originalAmount = Number(options.amount || options.totalAll || 0).toFixed(2);
    const orderId = options.orderId || '';

    this.setData({
      scene,
      typeName,
      originalAmount, // 已保留两位小数
      actualAmount: originalAmount, // 同步保留两位
      orderId
    });

    this.getCouponList();
  },

  // 新增：日期格式化辅助函数（处理时间戳/字符串日期）
  formatDate(dateStr) {
    if (!dateStr) return '永久有效';
    // 处理时间戳（数字）
    if (typeof dateStr === 'number') {
      dateStr = dateStr.toString().length === 13 ? dateStr : dateStr * 1000;
      const date = new Date(dateStr);
      return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
    }
    // 处理字符串日期（如2026-12-31、2026/12/31等）
    if (typeof dateStr === 'string') {
      // 简单格式化，保留YYYY-MM-DD部分
      const reg = /(\d{4})[-/](\d{1,2})[-/](\d{1,2})/;
      const match = dateStr.match(reg);
      if (match) {
        return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
      }
    }
    return '永久有效';
  },

  getCouponList() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      this.setData({
        couponDropdownOptions: [{value: '', label: '不使用优惠券'}],
        noCouponTip: '请先登录'
      });
      wx.showToast({ title: '未检测到登录状态', icon: 'none' });
      return;
    }
  
    wx.showLoading({ title: '加载优惠券...', mask: false });
    app.request({
      url: 'http://localhost:8000/app01/user/coupons/', 
      method: 'GET',
      header: {
        'Authorization': `Bearer ${accessToken}`,
        'content-type': 'application/json'
      },
      data: { 
        only_valid: true 
      }
    }).then(res => {
      wx.hideLoading();
      console.log('优惠券接口返回：', res);
      const couponList = res.data?.data?.coupons || [];
      
      const formatCoupon = couponList.map(item => {
        const coupon = item.coupon || {};
        const couponType = coupon.coupon_type || item.coupon_type || 1;
        let discountDesc = '';
        if (couponType === 1) {
          // 【修改2】优惠券抵扣金额保留两位小数
          const money = Number(coupon.money || item.money || 0).toFixed(2);
          discountDesc = `抵扣¥${money}元`;
        } else if (couponType === 2) {
          const discountRate = Number(coupon.discount_rate || item.discount_rate || 1);
          discountDesc = `${(discountRate * 10).toFixed(1)}折`;
        }

        // 核心修改1：提取并格式化有效期
        const expireTime = coupon.expire_time || item.expire_time || coupon.end_time || item.end_time || '';
        const expireDesc = this.formatDate(expireTime); // 格式化有效期
        
        return {
          ...item,
          discountDesc,
          expireDesc, // 新增：有效期描述
          id: item.id || '',
          title: coupon.title || item.title || '优惠券',
          coupon_type: couponType,
          // 【修改3】优惠券最大抵扣金额保留两位小数
          maxDeduct: couponType === 1 
            ? Math.min(Number(coupon.money || item.money || 0), Number(this.data.originalAmount)).toFixed(2)
            : (Number(this.data.originalAmount) * (1 - Number(coupon.discount_rate || item.discount_rate || 1))).toFixed(2)
        };
      });

      // 核心修改2：下拉选项label添加有效期
      const couponDropdownOptions = [
        {value: '', label: '不使用优惠券'}, 
        ...formatCoupon.map(item => ({
          value: item.id,
          label: `${item.title}（${item.discountDesc} | 有效期至${item.expireDesc}）`
        }))
      ];

      this.setData({
        couponList: formatCoupon,
        couponDropdownOptions: couponDropdownOptions,
        noCouponTip: formatCoupon.length === 0 ? '暂无可用优惠券' : ''
      });
    }).catch(err => {
      wx.hideLoading();
      console.error('加载优惠券失败：', err);
      this.setData({
        couponDropdownOptions: [{value: '', label: '不使用优惠券'}],
        noCouponTip: '加载优惠券失败'
      });
      if (err.errMsg.includes('404')) {
        wx.showToast({ title: '优惠券接口不存在，请检查后端路径', icon: 'none', duration: 3000 });
      }
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
      this.calculateActualAmount(selectedCoupon);
    } else {
      this.cancelCoupon();
    }
  },

  cancelCoupon() {
    // 【修改4】取消优惠券时金额保留两位小数
    this.setData({
      couponIndex: 0,
      selectedCoupon: null,
      actualAmount: this.data.originalAmount // originalAmount已保留两位，直接赋值
    });
  },

  calculateActualAmount(coupon) {
    const originalAmount = Number(this.data.originalAmount);
    let actualAmount = originalAmount;

    if (!coupon) {
      this.setData({ actualAmount: originalAmount.toFixed(2) });
      return;
    }

    if (coupon.coupon_type === 1) {
      const deductAmount = Number(coupon.coupon?.money || coupon.money || 0);
      actualAmount = Math.max(originalAmount - deductAmount, 0);
    } else if (coupon.coupon_type === 2) {
      const discountRate = Number(coupon.coupon?.discount_rate || coupon.discount_rate || 1);
      actualAmount = originalAmount * discountRate;
    }

    // 【修改5】计算后实际金额强制保留两位小数
    this.setData({ actualAmount: actualAmount.toFixed(2) });
  },

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

  handlePay() {
    const { payLoading } = this.data;
    if (payLoading) return;

    this.setData({ payLoading: true });
    const selectedMethod = this.data.payMethods.find(m => m.id === this.data.selectedPayMethod).name;

    setTimeout(() => {
      this.setData({ payLoading: false });
      // 【修改6】支付成功提示语中金额保留两位小数
      wx.showToast({
        title: `${selectedMethod}¥${this.data.actualAmount}元支付成功`,
        icon: 'success',
        duration: 2000
      });

      this.paySuccess(this.data.orderId, this.data.selectedCoupon);

    }, 2000);
  },

  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

// 修复后的优惠券使用接口调用方法
useCoupon(couponId, orderSn) {
  return new Promise((resolve) => {
    if (!couponId || !orderSn) {
      console.warn('优惠券ID或订单编号不能为空');
      resolve();
      return;
    }

    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    const requestFn = app.request || wx.request;

    // 核心修复1：使用后端正确的接口路径
    const couponUseUrl = `http://localhost:8000/app01/user/coupons/use/`;

    requestFn({
      url: couponUseUrl,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      // 核心修复2：请求体传参（coupon_id + order_sn，匹配后端要求）
      data: { 
        coupon_id: couponId,
        order_sn: orderSn // 注意：后端要的是order_sn（订单编号），不是order_id
      }
    }).then(res => {
      // 核心修复3：适配后端返回格式（code + msg + data）
      const resData = res.data || {};
      if (resData.code === 200) {
        console.log('优惠券标记为已使用成功：', couponId);
      } else {
        const errorMsg = resData.msg || '优惠券状态更新失败（接口返回异常）';
        console.error('优惠券标记失败：', errorMsg);
        wx.showToast({ title: errorMsg, icon: 'none', duration: 2000 });
      }
    }).catch(err => {
      // 区分404/超时等错误，提示更精准
      console.error('优惠券使用接口调用失败：', err);
      let errorTip = '优惠券状态更新失败';
      if (err.errMsg.includes('404')) {
        errorTip = '优惠券使用接口路径错误，请核对后端配置';
      } else if (err.errMsg.includes('timeout')) {
        errorTip = '优惠券状态更新超时，请稍后重试';
      }
      wx.showToast({ title: errorTip, icon: 'none', duration: 3000 });
    }).finally(() => {
      resolve();
    });
  });
},

  paySuccess(orderId, selectedCoupon) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.switchTab({url: '/pages/mall/mall'});
      return;
    }
  // 新增：先获取订单详情，拿到order_sn（订单编号）
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
        fail: () => {
          resolve(''); // 失败时返回空，不阻塞流程
        }
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
            // 【修改7】传递给后端的实际支付金额保留两位小数
            actual_amount: Number(this.data.actualAmount).toFixed(2)
          },
          success: (res) => {
            wx.showToast({ title: res.data.msg || '支付成功', icon: 'success' });
          },
          fail: (err) => {
            console.error('支付回调接口失败：', err);
            wx.showToast({ title: '支付成功但订单状态更新失败', icon: 'none' });
          },
          complete: () => resolve()
        });
      });
    };

    const clearCart = (isPrecise = false) => {
      let url = 'http://localhost:8000/app01/cart/clear/';
      if (isPrecise && orderId) {
        url = `http://localhost:8000/app01/cart/clear/${orderId}/`;
      }
      return new Promise((resolve) => {
        wx.request({
          url,
          method: 'POST',
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          success: (res) => {
            console.log(`清空购物车${isPrecise?'精准':'全'}成功`);
          },
          fail: (err) => {
            console.error(`清空购物车${isPrecise?'精准':'全'}失败：`, err);
          },
          complete: () => resolve()
        });
      });
    };

    callPaySuccessApi().then(() => {
      getOrderSn(orderId).then((orderSn) => {
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
const app = getApp();
Page({
  data: {
    typeName: '',
    originalAmount: '0.00',    // 订单总额（积分/人民币）
    actualAmount: '0.00',      // 最终实付金额
    pointDeductPoints: 0,      // 本次使用的积分数量
    isPointGoods: false,       // 是否为积分兑换商品
    exchangePoints: 0,         // 积分商品的总积分数量
    userPoints: 0,             // 用户可用积分
    maxDeductPoint: 0,         // 最大可抵扣积分
    pointToRmbRate: 100,       // 100积分=1元
    exchangePointsRmb: '0.00', 
    maxDeductPointRmb: '0.00', 
    pointDeductRmb: '0.00',    
    scene: 'order',
    orderId: '',
    memberId: '', // 会员ID
    phone: '',    // 手机号
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
    couponIndex: 0,
    pendingRegisterData: {} // 新增：存储从注册页传递的完整注册信息
  },

  onLoad(options) {
    console.log('支付页接收的参数：', options); 
    const scene = options.scene || 'order';
    const typeName = decodeURIComponent(options.typeName || (scene === 'member' ? '会员缴费' : '开店缴费'));
    const memberId = options.memberId || '';
    const phone = decodeURIComponent(options.phone || '');
    
    // 核心修复：根据场景读取正确的金额参数
    const amountSource = scene === 'member' ? options.amount : options.totalAll;
    const originalAmount = Number(amountSource || 0).toFixed(2); 
    const actualAmount = Number(options.actualAmount || originalAmount).toFixed(2);
    const pointDeductPoints = parseInt(options.deduct_point || 0);
    
    console.log('支付页金额初始化：', {
      scene, originalAmount, actualAmount, isPointGoods: options.isPointGoods === 'true'
    });

    // 积分商品参数
    const isPointGoods = options.isPointGoods === 'true';
    const exchangePoints = parseInt(options.exchangePoints || 0);
    
    // 仅使用传入的真实订单ID，不自动生成
    let orderId = options.orderId || '';

    // 提前计算积分相关金额
    const exchangePointsRmb = (exchangePoints / this.data.pointToRmbRate).toFixed(2);

    // ========== 关键修改1：读取注册页暂存的完整注册数据 ==========
    const pendingRegisterData = app.globalData.pendingRegisterData || wx.getStorageSync('pendingRegisterData') || {};
    console.log('从注册页读取的完整注册数据：', pendingRegisterData);

    // 初始化页面数据
    this.setData({
      scene,
      typeName,
      originalAmount,
      actualAmount,
      pointDeductPoints,
      orderId,
      isPointGoods,
      exchangePoints,
      exchangePointsRmb,
      pointDeductRmb: (pointDeductPoints / this.data.pointToRmbRate).toFixed(2),
      memberId,
      phone,
      pendingRegisterData // 保存到页面数据中
    });

    // 积分商品才获取用户积分
    if (isPointGoods) {
      this.getUserPoints();
    }
    setTimeout(() => {
      console.log('支付页最终数据：', this.data);
    }, 100);
    // 测试阶段屏蔽优惠券加载
    // this.getCouponList();
  },

  // 获取用户可用积分（保留原有逻辑）
  getUserPoints() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showToast({ title: '请先登录获取积分', icon: 'none' });
      return;
    }

    wx.request({
      url: `${app.globalData.baseUrl}/app01/user/points/`, 
      method: 'GET',
      header: {
        'Authorization': `Bearer ${accessToken}`,
        'content-type': 'application/json'
      },
      success: (res) => {
        const userPoints = parseInt(res.data?.data?.points || 0);
        const maxDeductPoint = Math.min(userPoints, this.data.exchangePoints);
        const maxDeductPointRmb = (maxDeductPoint / this.data.pointToRmbRate).toFixed(2);
        const initDeductPoint = Math.min(this.data.pointDeductPoints, maxDeductPoint);
        const initDeductRmb = (initDeductPoint / this.data.pointToRmbRate).toFixed(2);

        this.setData({
          userPoints,
          maxDeductPoint,
          maxDeductPointRmb,
          pointDeductPoints: initDeductPoint,
          pointDeductRmb: initDeductRmb
        }, () => {
          this.calcPointGoodsActualRmb();
        });
      },
      fail: (err) => {
        console.error('获取用户积分失败：', err);
        this.setData({ 
          userPoints: 0, 
          maxDeductPoint: 0,
          maxDeductPointRmb: '0.00' 
        });
        this.calcPointGoodsActualRmb();
        wx.showToast({ title: '加载可用积分失败', icon: 'none' });
      }
    });
  },

  // 计算积分商品实付人民币（保留原有逻辑）
  calcPointGoodsActualRmb() {
    if (!this.data.isPointGoods) return;
    const remainPoints = this.data.exchangePoints - this.data.pointDeductPoints;
    const actualRmb = (remainPoints / this.data.pointToRmbRate).toFixed(2);
    this.setData({ actualAmount: actualRmb });
  },

  // 积分抵扣相关方法（保留原有逻辑）
  updatePointDeduct(val) {
    const pointDeductRmb = (val / this.data.pointToRmbRate).toFixed(2);
    this.setData({
      pointDeductPoints: val,
      pointDeductRmb: pointDeductRmb
    }, () => {
      this.calcPointGoodsActualRmb();
    });
  },
  minusPoint() {
    if (this.data.pointDeductPoints <= 0) return;
    this.updatePointDeduct(this.data.pointDeductPoints - 1);
  },
  plusPoint() {
    if (this.data.pointDeductPoints >= this.data.maxDeductPoint) {
      wx.showToast({ title: '已达最大可抵扣积分', icon: 'none' });
      return;
    }
    this.updatePointDeduct(this.data.pointDeductPoints + 1);
  },
  inputPoint(e) {
    let val = parseInt(e.detail.value || 0);
    val = Math.max(0, Math.min(val, this.data.maxDeductPoint));
    this.updatePointDeduct(val);
  },
  useAllPoints() {
    if (this.data.maxDeductPoint <= 0) {
      wx.showToast({ title: '暂无可用积分抵扣', icon: 'none' });
      return;
    }
    this.updatePointDeduct(this.data.maxDeductPoint);
  },

  // 日期格式化（保留原有逻辑）
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

  // 优惠券相关（保留原有逻辑，测试阶段屏蔽调用）
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
    wx.request({
      url: `${app.globalData.baseUrl}/app01/user/coupons/`, 
      method: 'GET',
      header: {
        'Authorization': `Bearer ${accessToken}`,
        'content-type': 'application/json'
      },
      data: { only_valid: true },
      success: (res) => {
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
      },
      fail: (err) => {
        wx.hideLoading();
        this.setData({
          couponDropdownOptions: [{value: '', label: '不使用优惠券'}],
          noCouponTip: '加载优惠券失败'
        });
        console.error('加载优惠券失败：', err);
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

  // 支付方式切换（保留原有逻辑）
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

  // 支付核心逻辑（优化订单ID提示，适配会员场景）
  handlePay() {
    const { payLoading, orderId, scene, originalAmount, actualAmount, isPointGoods } = this.data;
    if (payLoading) return;

    // 优化：区分场景提示订单ID为空的逻辑
    if (!orderId) {
      if (scene === 'member') {
        console.log('会员缴费场景：无订单ID，正常继续支付流程');
      } else {
        console.warn('测试阶段：订单ID为空，继续支付流程');
      }
    }

    // 0元场景（积分全额抵扣）
    if (Number(originalAmount) === 0) {
      wx.showToast({ title: '0元免支付，正在完成订单...', icon: 'success' });
      setTimeout(() => {
        this.paySuccess(orderId, this.data.selectedCoupon);
      }, 1000);
      return;
    }

    // 积分商品校验
    if (isPointGoods) {
      if (this.data.exchangePoints === 0) {
        wx.showToast({ title: '积分商品积分数量异常', icon: 'none' });
        return;
      }
      if (Number(actualAmount) < 0) {
        wx.showToast({ title: '抵扣积分异常', icon: 'none' });
        return;
      }
    } else {
      // 付费场景金额校验
      if (Number(actualAmount) <= 0) {
        wx.showToast({ title: '支付金额异常，无法支付', icon: 'none' });
        return;
      }
    }

    // 模拟支付（正式环境替换为微信/支付宝SDK）
    this.setData({ payLoading: true });
    const selectedMethod = this.data.payMethods.find(m => m.id === this.data.selectedPayMethod).name;
  
    setTimeout(() => {
      this.setData({ payLoading: false });
      wx.showToast({
        title: `${selectedMethod}支付成功`,
        icon: 'success',
        duration: 2000
      });
      this.paySuccess(orderId, this.data.selectedCoupon);
    }, 1500);
  },

  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

  // 使用优惠券（保留原有逻辑）
  useCoupon(couponId, orderSn) {
    return new Promise((resolve) => {
      if (!couponId || !orderSn) {
        resolve();
        return;
      }
      const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      wx.request({
        url: `${app.globalData.baseUrl}/app01/user/coupons/use/`,
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

// ========== 核心修改：使用注册页传递的完整注册数据调用接口 ==========
saveMemberInfoAndLogin() {
  return new Promise((resolve, reject) => {
    const { memberId, phone, originalAmount, selectedPayMethod, pendingRegisterData } = this.data;
    
    // 1. 校验注册数据是否存在
    if (Object.keys(pendingRegisterData).length === 0) {
      reject('未获取到完整的注册信息，请返回注册页重新操作');
      return;
    }

    // 2. 解构注册页传递的必填参数（避免硬编码）
    const { 
      nickname, 
      password, 
      password_confirm, 
      user_type, 
      recommender_id,
      verifyCode
    } = pendingRegisterData;

    // 3. 强化参数校验（包含所有必填项）
    if (!memberId || memberId.trim() === '') {
      reject('会员ID不能为空');
      return;
    }
    if (!phone || phone.trim() === '' || !/^1[3-9]\d{9}$/.test(phone.trim())) {
      reject('请输入有效的手机号');
      return;
    }
    if (!nickname || nickname.trim() === '') {
      reject('昵称不能为空');
      return;
    }
    if (!password || password.trim() === '') {
      reject('密码不能为空');
      return;
    }
    if (!password_confirm || password_confirm.trim() === '') {
      reject('确认密码不能为空');
      return;
    }
    if (!user_type || isNaN(Number(user_type))) {
      reject('用户类型选择异常');
      return;
    }
    const amount = Number(originalAmount);
    if (isNaN(amount) || amount < 0) {
      reject('缴费金额异常');
      return;
    }
    const payMethod = Number(selectedPayMethod);
    if (![1, 2].includes(payMethod)) {
      reject('支付方式选择异常');
      return;
    }

    wx.showLoading({ title: '正在激活会员...' });
    wx.request({
      url: `${app.globalData.baseUrl}/app01/register/`, 
      method: 'POST',
      header: {
        'content-type': 'application/json'
      },
      data: {
        // 4. 使用注册页传递的完整必填参数
        member_id: memberId.trim(),       // 会员ID
        phone: phone.trim(),              // 手机号
        nickname: nickname.trim(),        // 注册页填写的昵称（不再硬编码）
        password: password.trim(),        // 注册页填写的密码（不再硬编码）
        password_confirm: password_confirm.trim(), // 新增：必填的确认密码
        user_type: Number(user_type),     // 新增：必填的用户类型
        recommender_id: recommender_id || '', // 推荐人ID（可选）
        verify_code: verifyCode || '',    // 验证码（根据后端字段名调整，若需要）
        // 缴费相关扩展参数
        amount: amount,                   
        pay_method: payMethod,
        pay_no: 'test_pay_no_' + Date.now() 
      },
      success: (res) => {
        wx.hideLoading();
        // 适配注册接口的响应格式
        if (res.data?.code === 200 && res.data?.access) {
          // 获取登录凭证（access_token）
          const accessToken = res.data.access;
          if (accessToken) {
            try {
              // ========== 关键补充：设置isLogin为true ==========
              // 1. 保存accessToken到缓存（同步操作）
              wx.setStorageSync('accessToken', accessToken);
              // 2. 保存到全局变量
              app.globalData.accessToken = accessToken;
              // 3. 保存会员信息
              const memberInfo = res.data.data || {};
              wx.setStorageSync('memberInfo', memberInfo);
              app.globalData.memberInfo = memberInfo;
              // 4. 核心补充：设置登录状态为true（缓存+全局）
              wx.setStorageSync('isLogin', true);
              app.globalData.isLogin = true;

              // 打印日志，验证保存是否成功
              console.log('登录凭证保存成功：', {
                accessToken: wx.getStorageSync('accessToken'),
                memberInfo: wx.getStorageSync('memberInfo'),
                isLogin: wx.getStorageSync('isLogin'),
                globalIsLogin: app.globalData.isLogin
              });

              resolve(true);
            } catch (e) {
              reject('登录凭证保存失败：' + e.message);
            }
          } else {
            reject('后端未返回登录凭证，自动登录失败');
          }
        } else {
          reject(res.data?.msg || '保存会员信息失败，请联系客服');
        }
      },
      fail: (err) => {
        wx.hideLoading();
        console.error('调用注册接口失败：', err);
        reject('网络异常，请检查网络后重试');
      }
    });
  });
},

  // 核心优化：会员场景保存信息+自动登录，订单场景保留原有逻辑
  paySuccess(orderId, selectedCoupon) {
    const { scene, memberId, phone, actualAmount, pointDeductPoints, isPointGoods, exchangePoints, selectedPayMethod } = this.data;
    
    // 区分场景处理登录校验
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (scene !== 'member' && !accessToken) {
      wx.showToast({ title: '请先登录再完成支付', icon: 'none' });
      return;
    }

    // 会员场景：保存信息+自动登录
    if (scene === 'member') {
      this.saveMemberInfoAndLogin()
        .then(() => {
          wx.showToast({ 
            title: '会员缴费成功，已自动登录', 
            icon: 'success', 
            duration: 2000 
          });
          setTimeout(() => {
            // 跳转至会员中心（推荐）或首页，根据业务调整路径
            wx.switchTab({ url: '/pages/index/index' });
            // 若有会员中心页面，替换为：wx.switchTab({ url: '/pages/member/member' });
          }, 1000);
        })
        .catch((errMsg) => {
          console.error('会员信息处理失败：', errMsg);
          // 优化：增加重试机制
          wx.showModal({
            title: '提示',
            content: `${errMsg}，是否重试？`,
            confirmText: '重试',
            cancelText: '返回首页',
            success: (res) => {
              if (res.confirm) {
                // 点击重试，重新执行保存逻辑
                this.saveMemberInfoAndLogin().then(() => {
                  wx.switchTab({ url: '/pages/index/index' });
                });
              } else {
                // 点击取消，返回首页
                wx.switchTab({ url: '/pages/index/index' });
              }
            }
          });
        });
      return;
    }

    // 订单场景：保留原有逻辑
    const getOrderSn = (orderId) => {
      return new Promise((resolve) => {
        if (!orderId || !/^\d+$/.test(orderId)) {
          resolve('');
          return;
        }
        wx.request({
          url: `${app.globalData.baseUrl}/app01/order/detail/`,
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
        const requestData = {
          pay_method: selectedPayMethod,
          pay_no: 'test_pay_no_' + Date.now(),
          actual_amount: actualAmount,
          deduct_point: pointDeductPoints,
          is_point_goods: isPointGoods,
          exchange_points: exchangePoints
        };
        if (orderId && /^\d+$/.test(orderId)) {
          requestData.order_id = orderId;
        }
        
        wx.request({
          url: `${app.globalData.baseUrl}/app01/order/pay_success/`,
          method: 'POST',
          header: {
            'content-type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
          },
          data: requestData,
          fail: (err) => {
            console.warn('支付回调接口调用失败：', err);
          },
          complete: () => resolve()
        });
      });
    };

    const clearCart = (isPrecise = false) => {
      return new Promise((resolve) => {
        const url = `${app.globalData.baseUrl}/app01/cart/clear/`;
        const data = isPrecise && orderId && /^\d+$/.test(orderId) ? { order_id: orderId } : {};
        
        wx.request({
          url, 
          method: 'POST',
          header: { Authorization: `Bearer ${accessToken}` },
          data: data,
          fail: (err) => {
            console.warn('购物车清空接口调用失败：', err);
          },
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
              wx.showToast({ title: '支付成功，订单已完成', icon: 'success' });
              setTimeout(() => {
                wx.switchTab({ url: '/pages/index/index' });
              }, 1000);
            });
          });
        });
      });
    });
  }
});
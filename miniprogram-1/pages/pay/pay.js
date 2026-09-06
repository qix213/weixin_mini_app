// pages/pay/pay.js
const app = getApp();

Page({
  data: {
    typeName: '',
    originalAmount: '0.00',    
    actualAmount: '0.00',      
    pointDeductPoints: 0,      
    isPointGoods: false,       
    exchangePoints: 0,         
    userPoints: 0,             
    maxDeductPoint: 0,         
    pointToRmbRate: 100,       
    exchangePointsRmb: '0.00', 
    maxDeductPointRmb: '0.00', 
    pointDeductRmb: '0.00',    
    payMethod: 'wechat',      
    walletBalance: '0.00',    // 电子钱包余额
    scene: 'order',
    orderId: '',
    memberId: '', 
    phone: '',    
    payLoading: false,
    couponList: [],
    couponDropdownOptions: [{ label: '不使用优惠券', value: -1 }],
    selectedCoupon: null,
    noCouponTip: '暂无可用优惠券',
    couponIndex: 0,
    isOfflineProject: false,
    pendingRegisterData: {},
    payButtonText: '确认支付'  
  },

  // ================= 1. 页面初始化与参数解析 =================
  onLoad(options) {
    let scene = options.scene || 'order';
    let typeName = options.typeName ? decodeURIComponent(options.typeName) : '';
    const isOfflineProject = options.isOfflineProject === 'true';
    const targetLevel = options.target_level || options.level || options.user_type || '';
    
    wx.login({
      success: (res) => {
        this.setData({ wxCode: res.code });
      }
    });

    let initialWalletBalance = '0.00';
    const memberInfo = getApp().globalData.memberInfo || wx.getStorageSync('memberInfo');
    if (memberInfo && memberInfo.wallet_balance) {
      initialWalletBalance = memberInfo.wallet_balance;
    }

    let orderId = options.orderId || options.order_sn || options.orderSn || '';
    console.log("📥 [收银台] 交付单据凭证:", orderId);

    if (isOfflineProject) {
      scene = 'offline';
      typeName = typeName || '线下项目预约/购买';
    }
    if (typeName === '会员升级订单' || scene === 'upgrade') {
      scene = 'upgrade';
    }
    if (!typeName) {
      if (scene === 'member') typeName = '开通尊享会籍';
      else if (scene === 'upgrade') typeName = '会籍权益升级';
      else if (scene === 'shop') typeName = '开通店主特权';
      else typeName = '商城订单支付';
    }

    const rawAmount = options.originalAmount || options.totalAll || options.amount || options.actualAmount || 0;
    const originalAmount = Number(rawAmount).toFixed(2);
    const actualAmount = Number(options.actualAmount || rawAmount).toFixed(2);
    
    const pointDeductPoints = parseInt(options.deduct_point || 0);
    const isPointGoods = options.isPointGoods === 'true';
    const exchangePoints = parseInt(options.exchangePoints || 0);
    const pendingRegisterData = app.globalData.pendingRegisterData || wx.getStorageSync('pendingRegisterData') || {};

    this.setData({
      scene,
      typeName,
      isOfflineProject,
      originalAmount,
      actualAmount,
      pointDeductPoints,
      orderId, 
      isPointGoods,
      exchangePoints,
      exchangePointsRmb: (exchangePoints / this.data.pointToRmbRate).toFixed(2),
      pointDeductRmb: (pointDeductPoints / this.data.pointToRmbRate).toFixed(2),
      memberId: options.memberId || '',
      phone: decodeURIComponent(options.phone || ''),
      pendingRegisterData,
      targetLevel,
      walletBalance: initialWalletBalance
    });

    if (isPointGoods) {
      this.getUserPoints();
    } else if (scene === 'order') {
      this.getCouponList();
    }

    this.getRealTimeWalletBalance();
    this.updatePayButtonUI();
  },

  // 🌟 实时拉取最新资产
  getRealTimeWalletBalance() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) return;
    
    wx.request({
      url: `${app.globalData.baseUrl}/app01/member/info/`, 
      method: 'GET',
      header: { 'Authorization': `Bearer ${token}` },
      success: (res) => {
        if (res.data.code === 200 && res.data.data) {
          const memberInfo = res.data.data;
          const realBalance = parseFloat(memberInfo.wallet_balance) || 0;
          
          wx.setStorageSync('memberInfo', memberInfo);
          app.globalData.memberInfo = memberInfo;

          this.setData({
            walletBalance: realBalance.toFixed(2),
            userPoints: memberInfo.points || 0 
          }, () => {
            this.updatePayButtonUI();
          });
          
          console.log(`💰 [资产同步] 实时获取钱包余额成功: ¥${realBalance.toFixed(2)}`);
        }
      }
    });
  },

  getOpenid() {
    return new Promise((resolve, reject) => {
      const cachedOpenid = wx.getStorageSync('openid');
      if (cachedOpenid) return resolve(cachedOpenid);
  
      if (!this.data.wxCode) return reject('获取微信凭证失败，请重试');
  
      wx.request({
        url: `${app.globalData.baseUrl}/app01/wx/code2openid/`,
        method: 'POST',
        header: { 'content-type': 'application/json' },
        data: { code: this.data.wxCode },
        success: (res) => {
          if (res.data.code === 200) {
            const openid = res.data.data.openid;
            wx.setStorageSync('openid', openid);
            resolve(openid);
          } else {
            reject(res.data.msg || '换取支付凭证失败');
          }
        },
        fail: () => reject('网络异常，无法获取支付凭证')
      });
    });
  },

  // ================= 2. 积分与优惠券逻辑 =================
  getUserPoints() {
    const memberInfo = wx.getStorageSync('memberInfo') || {};
    const points = memberInfo.points || 0;
    const maxDeductRmb = Number(this.data.originalAmount) * 0.5;
    const maxDeductPoint = Math.min(points, maxDeductRmb * this.data.pointToRmbRate);
    
    this.setData({
      userPoints: points,
      maxDeductPoint: parseInt(maxDeductPoint),
      maxDeductPointRmb: (parseInt(maxDeductPoint) / this.data.pointToRmbRate).toFixed(2)
    });
    this.calcPointGoodsActualRmb();
  },

  updatePointDeduct(val) {
    let points = parseInt(val) || 0;
    if (points < 0) points = 0;
    if (points > this.data.maxDeductPoint) points = this.data.maxDeductPoint;
    
    this.setData({ 
      pointDeductPoints: points,
      pointDeductRmb: (points / this.data.pointToRmbRate).toFixed(2)
    });
    this.calcPointGoodsActualRmb();
  },

  minusPoint() { this.updatePointDeduct(this.data.pointDeductPoints - 100); },
  plusPoint() { this.updatePointDeduct(this.data.pointDeductPoints + 100); },
  inputPoint(e) { this.updatePointDeduct(e.detail.value); },
  useAllPoints() { this.updatePointDeduct(this.data.maxDeductPoint); },

  calcPointGoodsActualRmb() {
    if (!this.data.isPointGoods) return;
    const originalRmb = Number(this.data.originalAmount);
    const deductRmb = Number(this.data.pointDeductRmb);
    let finalRmb = originalRmb - deductRmb;
    if (finalRmb < 0) finalRmb = 0;
    
    this.setData({ actualAmount: finalRmb.toFixed(2) }, () => {
      this.updatePayButtonUI();
    });
  },

  getCouponList() {
    const token = wx.getStorageSync('accessToken');
    if (!token) return;
    
    wx.request({
      url: app.globalData.baseUrl + '/app01/user/coupons/',
      method: 'GET',
      header: { 'Authorization': `Bearer ${token}` },
      data: { only_valid: true },
      success: (res) => {
        if (res.data.code === 200) {
          const coupons = res.data.data.coupons || [];
          const options = [{ label: '不使用优惠券', value: -1, _realDiscount: 0 }]; 
          const originalAmt = parseFloat(this.data.originalAmount) || 0;

          coupons.forEach(c => {
            if (!c) return; 
            const couponObj = c.coupon || c; 
            const title = couponObj.title || couponObj.name || '通用优惠券';
            const type = parseInt(couponObj.coupon_type || 1); 
            const minConsume = parseFloat(couponObj.min_consume || 0);
            
            if (originalAmt < minConsume) return; 

            let calculatedDiscount = 0;
            let displayTag = '';

            if (type === 1) {
              const money = parseFloat(couponObj.money || 0);
              calculatedDiscount = money;
              displayTag = `减￥${money.toFixed(2)}`;
            } else if (type === 2) {
              const rate = parseFloat(couponObj.discount_rate || 1.00);
              calculatedDiscount = originalAmt - (originalAmt * rate);
              displayTag = `打${parseFloat((rate * 10).toFixed(1))}折`;
            }

            if (calculatedDiscount > originalAmt) {
              calculatedDiscount = originalAmt;
            }

            options.push({ 
              label: `${title} (${displayTag})`, 
              value: c.id, 
              _realDiscount: calculatedDiscount, 
              ...couponObj 
            });
          });
          
          this.setData({ 
            couponList: coupons, 
            couponDropdownOptions: options 
          });
        }
      }
    });
  },

  onCouponChangeNative(e) {
    const index = parseInt(e.detail.value);
    this.setData({ couponIndex: index });
    
    if (index === 0) {
      this.cancelCoupon();
      return;
    }
    
    const selected = this.data.couponDropdownOptions[index];
    const original = parseFloat(this.data.originalAmount) || 0;
    const discount = parseFloat(selected._realDiscount) || 0; 
    
    let newAmount = original - discount;
    if (newAmount <= 0) newAmount = 0.01; 
    
    this.setData({
      selectedCoupon: selected,
      actualAmount: newAmount.toFixed(2)
    }, () => {
      this.updatePayButtonUI();
    });
  },

  cancelCoupon() {
    this.setData({
      selectedCoupon: null,
      actualAmount: parseFloat(this.data.originalAmount || 0).toFixed(2)
    }, () => {
      this.updatePayButtonUI();
    });
  },

  // ==============================================================
  // 🌟 拦截器1：用户切换支付方式时触发检查
  // ==============================================================
  onPayMethodChange(e) {
    const method = e.detail.value;

    // 如果选了钱包，且当前是提升会员等级场景
    if (method === 'wallet' && this.data.scene === 'upgrade') {
      wx.showToast({
        title: '提升会员等级不支持使用钱包余额哦',
        icon: 'none',
        duration: 2000
      });
      // 强行切回微信支付（此时需要 wxml 中 radio 绑定 check={{payMethod === 'wechat'}} 才会视觉回退）
      this.setData({
        payMethod: 'wechat'
      });
      this.updatePayButtonUI();
      return;
    }

    this.setData({
      payMethod: method
    });
    this.updatePayButtonUI();
  },

  updatePayButtonUI() {
    const actual = parseFloat(this.data.actualAmount) || 0;
    const wallet = parseFloat(this.data.walletBalance) || 0;
    const method = this.data.payMethod;

    let text = '确认支付';

    if (method === 'wallet') {
      if (wallet >= actual) {
        text = `钱包全额支付 ¥${actual.toFixed(2)}`;
      } else {
        let diff = actual - wallet;
        if (diff <= 0) diff = 0.01;
        text = `混合支付(微信补齐) ¥${diff.toFixed(2)}`;
      }
    } else {
      text = `微信支付 ¥${actual.toFixed(2)}`;
    }

    this.setData({ payButtonText: text });
  },

  // ================= 3. 支付主干流程 =================
  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

  handlePay() {
    const { 
      payLoading, orderId, scene, actualAmount, 
      selectedCoupon, pointDeductPoints, 
      pendingRegisterData, payMethod, walletBalance
    } = this.data;

    if (payLoading) return;

    // ==============================================================
    // 🌟 拦截器2：点击支付时的二次强制校验（防穿透）
    // ==============================================================
    if (payMethod === 'wallet' && scene === 'upgrade') {
      wx.showToast({ title: '抱歉，提升会员等级不支持钱包支付', icon: 'none' });
      return;
    }

    const isVirtualScene = ['member', 'shop', 'upgrade'].includes(scene);
    if (!orderId && !isVirtualScene) {
      wx.showToast({ title: '订单异常，缺少ID', icon: 'none' });
      return;
    }

    if (Number(actualAmount) < 0) {
      wx.showToast({ title: '金额异常或需全额抵扣', icon: 'none' });
      return;
    }

    let isMixedPay = false;
    if (payMethod === 'wallet' && Number(walletBalance) < Number(actualAmount)) {
      isMixedPay = true;
    }

    this.setData({ payLoading: true });
    wx.showLoading({ title: isMixedPay ? '生成混合支付单...' : '处理中...' });

    this.getOpenid().then(openid => {
      const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      const requestHeader = { 'content-type': 'application/json' };
      if (token) {
        requestHeader['Authorization'] = `Bearer ${token}`;
      }
      const postData = {
        scene: scene,
        point_deduct: pointDeductPoints || 0,
        coupon_id: selectedCoupon ? selectedCoupon.value : null,
        use_wallet: (payMethod === 'wallet') // 明确告诉后端是否使用钱包
      };

      if (scene === 'upgrade') {
        postData.amount = actualAmount; 
        postData.openid = openid;        
        postData.register_data = { target_level: this.data.targetLevel };
      } else if (scene === 'member' || scene === 'shop') {
        postData.amount = actualAmount; 
        postData.openid = openid;        
        postData.register_data = {
          ...pendingRegisterData,
          phone: this.data.phone, 
          user_type: this.data.targetLevel || pendingRegisterData.user_type
        };
      } else {
        postData.order_id = orderId;
      }

      wx.request({
        url: `${app.globalData.baseUrl}/app01/order/wechat_prepay/`,
        method: 'POST',
        header: requestHeader, // 🌟 使用动态组装的 header
        data: postData,
        success: (res) => {
          if (res.data.code === 200) {
            const payParams = res.data.data;
            const finalOrderSn = payParams.order_sn || orderId;
            
            if (payMethod === 'wallet' && !isMixedPay) {
              wx.setNavigationBarTitle({ title: '正在全额扣款...' });
              wx.request({
                url: `${app.globalData.baseUrl}/app01/order/pay/wallet/`, 
                method: 'POST',
                header: requestHeader, // 🌟 这里也同步替换
                data: { order_sn: finalOrderSn },
                success: (walletRes) => {
                  wx.hideLoading();
                  this.setData({ payLoading: false });
                  
                  if (walletRes.data.code === 200) {
                    wx.showToast({ title: '钱包全额支付成功', icon: 'success', duration: 1500 });
                    setTimeout(() => { this.paySuccess(finalOrderSn); }, 500);
                  } else {
                    wx.showToast({ title: walletRes.data.msg || '钱包扣款失败', icon: 'none' });
                  }
                },
                fail: () => {
                  wx.hideLoading();
                  this.setData({ payLoading: false });
                  wx.showToast({ title: '网络异常，钱包扣款失败', icon: 'none' });
                }
              });

            } else {
              wx.hideLoading();
              if (payParams && payParams.is_mock === true) {
                this.setData({ payLoading: false });
                wx.showToast({ title: isMixedPay ? '混合支付成功' : '微信支付成功', icon: 'success', duration: 1500 });
                setTimeout(() => { this.paySuccess(finalOrderSn); }, 500);
              } else {
                wx.requestPayment({
                  timeStamp: payParams.timeStamp,
                  nonceStr: payParams.nonceStr,
                  package: payParams.package,
                  signType: payParams.signType || 'RSA',
                  paySign: payParams.paySign,
                  success: (payRes) => {
                    this.setData({ payLoading: false });
                    this.paySuccess(finalOrderSn); 
                  },
                  fail: (err) => { 
                    this.setData({ payLoading: false }); 
                    wx.showToast({ title: '支付取消', icon: 'none' });
                  }
                });
              }
            }
          } else {
            wx.hideLoading();
            this.setData({ payLoading: false });
            wx.showToast({ title: res.data.msg || '支付发起失败', icon: 'none' });
          }
        },
        fail: () => {
          wx.hideLoading();
          this.setData({ payLoading: false });
          wx.showToast({ title: '网络异常，无法拉起支付', icon: 'none' });
        }
      });
    }).catch(err => {
      wx.hideLoading();
      this.setData({ payLoading: false });
      wx.showToast({ title: err || '支付初始化失败', icon: 'none' });
    });
  },

  // ================= 4. 支付成功分流逻辑 =================
  paySuccess(finalOrderSn) {
    const { scene, isOfflineProject } = this.data; 
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    const isOfflineFlag = (isOfflineProject === 'true' || isOfflineProject === true);
    
    if (scene !== 'member' && scene !== 'shop' && !accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    if (scene === 'member' || scene === 'shop' || scene === 'upgrade') {
      wx.showLoading({ title: '正在同步资产权益...', mask: true });
      this.pollOrderToken(finalOrderSn, scene, isOfflineFlag, 1);
      return;
    }

    this.clearCartAndRedirect(isOfflineFlag, scene);
  },

  // ================= 5. 核心轮询器：等待微信异步回调落盘 =================
  pollOrderToken(orderSn, scene, isOfflineFlag, attempt) {
    const that = this;
    const maxAttempts = 5; 

    wx.request({
      url: `${app.globalData.baseUrl}/app01/order/pay_get_token/`,
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { order_sn: orderSn },
      success: (res) => {
        if (res.data.code === 200) {
          wx.hideLoading();
          wx.showToast({ title: scene === 'upgrade' ? '会籍升级成功！' : '会籍开通成功', icon: 'success' });
          
          const userInfo = res.data.data;

          if (scene === 'upgrade') {
            if (userInfo) {
              wx.setStorageSync('memberInfo', userInfo);
              app.globalData.memberInfo = userInfo;
            }
            that.clearCartAndRedirect(isOfflineFlag, scene);
          } else {
            const access = res.data.access;
            const refresh = res.data.refresh;
            wx.setStorageSync('accessToken', access);
            wx.setStorageSync('refreshToken', refresh);
            wx.setStorageSync('isLogin', true);
            if (userInfo) wx.setStorageSync('memberInfo', userInfo);

            app.globalData.accessToken = access;
            app.globalData.refreshToken = refresh;
            app.globalData.isLogin = true;
            if (userInfo) app.globalData.memberInfo = userInfo;

            setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
          }
        } 
        else if (res.data.code === 402 && attempt < maxAttempts) {
          console.log(`⏳ [时序等待] 第 ${attempt} 次未果，微信回调尚未落盘，1秒后重试...`);
          setTimeout(() => {
            that.pollOrderToken(orderSn, scene, isOfflineFlag, attempt + 1);
          }, 1000);
        } 
        else {
          wx.hideLoading();
          wx.showModal({
            title: '同步延迟',
            content: res.data.msg || '微信网关处理略有延迟，您的会籍正在开通中，请1分钟后在"我的"页面查看。',
            showCancel: false,
            success: () => { wx.switchTab({ url: '/pages/my/my' }); }
          });
        }
      },
      fail: () => {
        if (attempt < maxAttempts) {
          setTimeout(() => { that.pollOrderToken(orderSn, scene, isOfflineFlag, attempt + 1); }, 1000);
        } else {
          wx.hideLoading();
          wx.showToast({ title: '网络异常，请前往“我的”查看', icon: 'none' });
          setTimeout(() => { wx.switchTab({ url: '/pages/my/my' }); }, 1500);
        }
      }
    });
  },

  // ================= 6. 核心抽离：安全清空购物车与智能跳转 =================
  clearCartAndRedirect(isOfflineFlag, scene) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    wx.showLoading({ title: '正在同步订单状态...' });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/cart/clear/`,
      method: 'POST',
      header: { 'Authorization': `Bearer ${accessToken}` },
      complete: () => {
        wx.removeStorageSync('cart');
        wx.hideLoading();
        
        if (isOfflineFlag || scene === 'offline') {
          wx.showToast({ title: '购买成功！', icon: 'success' });
          setTimeout(() => { wx.reLaunch({ url: '/pages/my/offline_project' }); }, 1500);
        } else {
          wx.showToast({ title: '支付成功', icon: 'success' });
          setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
        }
      }
    });
  }
});
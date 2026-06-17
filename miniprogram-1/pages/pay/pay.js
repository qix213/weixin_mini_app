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
    scene: 'order',
    orderId: '',
    memberId: '', 
    phone: '',    
    payMethods: [        
      { id: 1, name: '微信支付', icon: 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/wechat.svg', selected: true },
      { id: 2, name: '支付宝支付', icon: 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/icons/alipay.svg', selected: false }
    ],
    selectedPayMethod: 1,
    payLoading: false,
    couponList: [],
    couponDropdownOptions: [{ label: '不使用优惠券', value: -1 }],
    selectedCoupon: null,
    noCouponTip: '暂无可用优惠券',
    couponIndex: 0,
    pendingRegisterData: {} 
  },

  // ================= 1. 页面初始化与参数解析 =================
  onLoad(options) {
    let scene = options.scene || 'order';
    let typeName = options.typeName ? decodeURIComponent(options.typeName) : '';
    
    // 识别升级场景
    if (typeName === '会员升级订单') {
      scene = 'upgrade';
    }

    // 🌟 移除“开店缴费”，按场景赋予高级的默认标题
    if (!typeName) {
      if (scene === 'member') typeName = '开通尊享会籍';
      else if (scene === 'upgrade') typeName = '会籍权益升级';
      else if (scene === 'shop') typeName = '开通店主特权';
      else typeName = '商城订单支付';
    }

    // 🌟 万能金额解析，防 0.00 兜底！
    const rawAmount = options.originalAmount || options.totalAll || options.amount || options.actualAmount || 0;
    const originalAmount = Number(rawAmount).toFixed(2);
    const actualAmount = Number(options.actualAmount || rawAmount).toFixed(2);
    
    const pointDeductPoints = parseInt(options.deduct_point || 0);
    const isPointGoods = options.isPointGoods === 'true';
    const exchangePoints = parseInt(options.exchangePoints || 0);
    let orderId = options.orderId || '';

    const exchangePointsRmb = (exchangePoints / this.data.pointToRmbRate).toFixed(2);
    const pendingRegisterData = app.globalData.pendingRegisterData || wx.getStorageSync('pendingRegisterData') || {};

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
      memberId: options.memberId || '',
      phone: decodeURIComponent(options.phone || ''),
      pendingRegisterData 
    });

    if (isPointGoods) {
      this.getUserPoints();
    } else if (scene === 'order') {
      this.getCouponList(); // 商城订单拉取优惠券
    }
  },

  // ================= 2. 支付方式与基础功能 =================
  switchPayMethod(e) {
    const id = e.currentTarget.dataset.methodid;
    const methods = this.data.payMethods.map(m => ({
      ...m,
      selected: m.id === id
    }));
    this.setData({ payMethods: methods, selectedPayMethod: id });
  },

  formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  },

  // ================= 3. 积分相关逻辑 =================
  getUserPoints() {
    const memberInfo = wx.getStorageSync('memberInfo') || {};
    const points = memberInfo.points || 0;
    // 假设最大抵扣金额为订单金额的一半
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
    this.setData({ actualAmount: finalRmb.toFixed(2) });
  },

  // ================= 4. 优惠券相关逻辑 =================
// ================= 4. 优惠券相关逻辑 =================
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
        // 兼容后端返回结构：可能是 res.data.data.coupons，也可能是直接的一个数组 res.data.data
        const coupons = res.data.data.coupons || res.data.data || [];
        const options = [{ label: '不使用优惠券', value: -1 }];
        
        coupons.forEach(c => {
          if (!c) return; // 防御性跳过空数据
          
          // 🌟 核心修复：兼容嵌套的 c.coupon 或直接平铺的 c
          const couponObj = c.coupon || c;
          
          // 兼容不同命名习惯（有的时候后端叫 name，有的时候叫 title）
          const couponName = couponObj.name || couponObj.title || '通用优惠券';
          // 兼容抵扣金额字段（有的时候叫 discount，有的时候叫 money）
          const couponDiscount = couponObj.discount || couponObj.money || 0;

          options.push({ 
            label: `${couponName} (减￥${couponDiscount})`, 
            value: c.id, 
            ...couponObj 
          });
        });
        
        this.setData({ couponList: coupons, couponDropdownOptions: options });
      }
    },
    fail: (err) => {
      console.error("获取优惠券列表失败:", err);
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
    let newAmount = Number(this.data.originalAmount) - Number(selected.discount || 0);
    if (newAmount < 0) newAmount = 0.01; // 兜底防止0元单异常
    
    this.setData({
      selectedCoupon: selected,
      actualAmount: newAmount.toFixed(2)
    });
  },

  cancelCoupon() {
    this.setData({
      selectedCoupon: null,
      actualAmount: this.data.originalAmount
    });
  },

  // ================= 5. 核心：提交注册并自动登录 =================
  saveMemberInfoAndLogin() {
    return new Promise((resolve, reject) => {
      const registerData = this.data.pendingRegisterData;

      // 1. 防御性拦截：数据丢失直接打回
      if (!registerData || Object.keys(registerData).length === 0) {
        return reject('注册数据异常丢失，请返回重新填写');
      }

      // 2. 组装后端数据，强制附加“已支付”凭证
      const postData = {
        ...registerData,
        is_paid: true, 
        pay_amount: this.data.actualAmount 
      };

      console.log('【准备请求注册接口的数据】：', postData);

      wx.request({
        url: app.globalData.baseUrl + '/app01/register/', 
        method: 'POST',
        header: { 'content-type': 'application/json' },
        data: postData,
        success: (res) => {
          console.log('【注册接口返回结果】：', res.data);

          if (res.data.code === 200 || res.data.code === 201 || res.statusCode === 201) {
            // 3. 注册成功，写入全局登录态
            const access = res.data.access || res.data.data?.access;
            const refresh = res.data.refresh || res.data.data?.refresh;
            const userInfo = res.data.data;

            if (access) {
              wx.setStorageSync('accessToken', access);
              wx.setStorageSync('refreshToken', refresh);
              wx.setStorageSync('isLogin', true);
              if (userInfo) wx.setStorageSync('memberInfo', userInfo);

              app.globalData.accessToken = access;
              app.globalData.refreshToken = refresh;
              app.globalData.isLogin = true;
              if (userInfo) app.globalData.memberInfo = userInfo;
            }

            // 🌟 通知支付流继续前进
            resolve(res.data);
          } else {
            reject(res.data.msg || '注册失败，请联系客服');
          }
        },
        fail: (err) => {
          console.error('【注册接口请求失败】：', err);
          reject('网络请求异常，请检查网络设置');
        }
      });
    });
  },

  // ================= 6. 支付主干流程 =================
  handleCancel() {
    wx.navigateBack({ delta: 1 });
  },

  handlePay() {
    const { payLoading, orderId, scene, originalAmount, actualAmount, isPointGoods } = this.data;
    if (payLoading) return;

    if (!orderId && scene !== 'member' && scene !== 'shop') {
      console.warn('测试阶段：订单ID为空，继续支付流程');
    }

    // 免支付判断
    if (Number(originalAmount) === 0 || Number(actualAmount) === 0) {
      wx.showToast({ title: '0元免支付，正在处理...', icon: 'success' });
      setTimeout(() => {
        this.paySuccess(orderId, this.data.selectedCoupon);
      }, 1000);
      return;
    }

    if (isPointGoods && (this.data.exchangePoints === 0 || Number(actualAmount) < 0)) {
      wx.showToast({ title: '积分商品异常', icon: 'none' }); return;
    } else if (!isPointGoods && Number(actualAmount) <= 0) {
      wx.showToast({ title: '支付金额异常', icon: 'none' }); return;
    }

    this.setData({ payLoading: true });
    const selectedMethodName = this.data.payMethods.find(m => m.id === this.data.selectedPayMethod).name;

    // TODO: 这里将来要替换成真实的 wx.requestPayment
    setTimeout(() => {
      this.setData({ payLoading: false });
      wx.showToast({ title: `${selectedMethodName}支付成功`, icon: 'success', duration: 1500 });
      this.paySuccess(orderId, this.data.selectedCoupon);
    }, 1500);
  },

  // ================= 7. 支付成功分流逻辑 =================
// ================= 7. 支付成功分流逻辑 =================
paySuccess(orderId, selectedCoupon) {
  const { scene, pointDeductPoints } = this.data;
  const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
  
  // 【拦截器】非注册场景必须有登录态
  if (scene !== 'member' && scene !== 'shop' && !accessToken) {
    wx.showToast({ title: '请先登录再完成支付', icon: 'none' });
    return;
  }

  // ================= 🌟 场景 A：新用户注册缴费开通 =================
  if (scene === 'member' || scene === 'shop') {
    wx.showLoading({ title: '开通专属会籍中...' });
    
    this.saveMemberInfoAndLogin().then(() => {
      const newAccessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
      const avatarUrl = this.data.pendingRegisterData.avatarUrl; 
      
      // 如果有暂存头像，静默上传
      if (avatarUrl && newAccessToken) {
        wx.uploadFile({
          url: app.globalData.baseUrl + '/app01/member/upload_avatar/', 
          filePath: avatarUrl,
          name: 'file', 
          header: { 'Authorization': `Bearer ${newAccessToken}` },
          success: () => {
            wx.hideLoading();
            wx.showToast({ title: '开通成功', icon: 'success', duration: 2000 });
            setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
          },
          fail: () => {
            wx.hideLoading();
            wx.showToast({ title: '开通成功，头像稍后生效', icon: 'none', duration: 2000 });
            setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
          }
        });
      } else {
        wx.hideLoading();
        wx.showToast({ title: '开通成功', icon: 'success', duration: 2000 });
        setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
      }
    }).catch((errMsg) => {
      wx.hideLoading();
      wx.showToast({ title: errMsg || '注册遇到问题', icon: 'none' });
    });
    return;
  }

  // ================= 🌟 场景 B：老会员提升等级 =================
  if (scene === 'upgrade') {
    wx.showLoading({ title: '正在更新会籍...' });
    wx.request({
      url: `${app.globalData.baseUrl}/app01/member/upgrade_success/`,
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}`
      },
      data: { out_trade_no: orderId }, 
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          wx.showToast({ title: '升级成功！', icon: 'success', duration: 2000 });
          if (res.data.data) {
              app.globalData.memberInfo = res.data.data;
              wx.setStorageSync('memberInfo', res.data.data);
          }
          setTimeout(() => { wx.switchTab({ url: '/pages/my/my' }); }, 1500);
        } else {
          wx.showToast({ title: '状态更新延迟，请稍后查看', icon: 'none' });
          setTimeout(() => { wx.switchTab({ url: '/pages/my/my' }); }, 1500);
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常，请联系客服', icon: 'none' });
      }
    });
    return;
  }

  // ================= 🌟 场景 C：普通商城订单 (全新真实请求闭环) =================
  wx.showLoading({ title: '正在同步订单状态...' });

  // 1. 发起请求，通知后端该订单已支付成功
  wx.request({
    url: `${app.globalData.baseUrl}/app01/order/pay_success/`, // ⚠️ 需确保 Django 有此路由
    method: 'POST',
    header: {
      'content-type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    data: {
      order_id: orderId, // 订单ID
      coupon_user_id: selectedCoupon ? selectedCoupon.value : null, // 优惠券ID (如有)
      point_deduct: pointDeductPoints || 0 // 抵扣的积分 (如有)
    },
    success: (res) => {
      if (res.data.code === 200 || res.data.code === 201) {
        
        // 2. 订单状态修改成功后，通知后端清空用户的购物车
        wx.request({
          url: `${app.globalData.baseUrl}/app01/cart/clear/`, // ⚠️ 需确保 Django 有此路由
          method: 'POST',
          header: {
            'Authorization': `Bearer ${accessToken}`
          },
          complete: () => {
            // 3. 无论后端清空是否成功，前端强制清空本地购物车缓存，双保险！
            wx.removeStorageSync('cart');
            
            wx.hideLoading();
            wx.showToast({ title: '支付成功，订单已成', icon: 'success', duration: 2000 });
            
            // 4. 顺滑跳转到首页 (或订单列表页)
            setTimeout(() => {
              wx.switchTab({ url: '/pages/index/index' });
            }, 1500);
          }
        });

      } else {
        wx.hideLoading();
        wx.showToast({ title: res.data.msg || '订单状态更新延迟，请联系客服', icon: 'none' });
        setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1500);
      }
    },
    fail: () => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常，请在我的订单中确认状态', icon: 'none' });
    }
  });
}
});
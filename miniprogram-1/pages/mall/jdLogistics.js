const app = getApp();

Page({
  data: {
    loading: false, // 进页面不再需要等待查订单
    isSubmitting: false,
    precheckLoading: false,
    timeRange: [],         // 供选择的二维数组：[ [日期], [小时], [分钟] ]
    timeIndex: [0, 0, 0],  // 默认选中的索引
    _dateActual: [],       // 后台隐藏计算用的真实日期(YYYY/MM/DD)
    pickupTimeLabel: '立即上门（默认）', 
    pickupStartTime: null, // 最终传给后端的毫秒时间戳
    pickupEndTime: null,

    // 地址信息（不再依赖订单，直接独立存储）
    sender: {},
    receiver: {},

    // 状态与费用估算
    precheckStatus: null, // null未校验，true通过，false失败
    errorMsg: "",
    freight: 0,           // 预估运费
    needPoints: 0,        // 预估需扣积分
    userPoints: 0,        // 可用积分余额

    // 标准化包裹
    packageSpecs: [
      { name: '极小件/文件 (1kg内)', weight: 1.0, volume: 0.001 },
      { name: '小包裹 (3kg内)', weight: 3.0, volume: 0.01 },
      { name: '中大包裹 (5kg内)', weight: 5.0, volume: 0.03 }
    ],
    selectedSpecIndex: 0,
    cargoName: '护肤品/日用品'
  },

  onLoad(options) {
    // 🌟 彻底去掉了对 order_sn 的强制校验和 fetchOrderDetail 的调用！
    // 页面一进来直接获取默认寄件人地址
    this.getDefaultSenderAddress();
    this.initTimePicker();
  },
  initTimePicker() {
    const dates = [];
    const dateActual = [];
    const now = new Date();
    
    // 生成未来3天
    for (let i = 0; i < 3; i++) {
      let d = new Date(now.getTime() + i * 24 * 60 * 60 * 1000);
      let month = (d.getMonth() + 1).toString().padStart(2, '0');
      let day = d.getDate().toString().padStart(2, '0');
      let suffix = i === 0 ? '(今天)' : i === 1 ? '(明天)' : '(后天)';
      dates.push(`${month}月${day}日 ${suffix}`);
      // ⚠️ 关键：必须用反斜杠 /，如果用 - 苹果手机会解析出 NaN 导致系统崩溃
      dateActual.push(`${d.getFullYear()}/${month}/${day}`); 
    }

    // 生成小时 (9点 - 18点)
    const hours = [];
    for (let i = 9; i <= 18; i++) {
      hours.push(`${i.toString().padStart(2, '0')}时`);
    }

    // 生成分钟 (00 - 50分)
    const minutes = ['00分', '10分', '20分', '30分', '40分', '50分'];

    this.setData({
      timeRange: [dates, hours, minutes],
      _dateActual: dateActual
    });
  },

  // 2. 当用户滑动确认选择时间
  onTimeChange(e) {
    const val = e.detail.value;
    
    const dateStr = this.data._dateActual[val[0]];
    const hourStr = this.data.timeRange[1][val[1]].replace('时', '');
    const minStr = this.data.timeRange[2][val[2]].replace('分', '');

    // 拼接成标准字符串并转为毫秒时间戳
    const targetTime = new Date(`${dateStr} ${hourStr}:${minStr}:00`);
    const startMs = targetTime.getTime();

    // 拦截：不能选择过去的时间
    if (startMs < new Date().getTime()) {
      wx.showToast({
        title: '不能预约过去的时间',
        icon: 'none'
      });
      return;
    }

    this.setData({
      timeIndex: val,
      pickupTimeLabel: `${this.data.timeRange[0][val[0]].substring(0, 6)} ${hourStr}:${minStr}`,
      pickupStartTime: startMs,
      // 京东建议有一个揽收结束时间窗口，这里默认在开始时间上加 2 小时
      pickupEndTime: startMs + (2 * 60 * 60 * 1000) 
    });
  },

  // 3. 点击清除按钮，恢复默认“立即上门”
  clearPickupTime() {
    this.setData({
      timeIndex: [0, 0, 0],
      pickupTimeLabel: '立即上门（默认）',
      pickupStartTime: null,
      pickupEndTime: null
    });
  },
  onShow() {
    this.getUserPoints(); // 每次显示页面更新可用积分
  },

  // 获取用户积分
  getUserPoints() {
    const token = wx.getStorageSync('accessToken');
    app.request({
      url: '/app01/user/points/',
      header: { Authorization: `Bearer ${token}` }
    }).then(res => {
      if (res.data?.code === 200) {
        this.setData({ userPoints: res.data.data.points || 0 });
      }
    });
  },

  // 获取默认寄件人地址（通常是你商城的平台发货地址，或者是用户默认地址）
  getDefaultSenderAddress() {
    if (this.data.sender.name) return;

    app.request({
      url: `${app.globalData.baseUrl}/app01/address/list/`,
      method: 'GET',
      header: app.getRequestHeader()
    }).then(res => {
      if (res.data.code === 200) {
        const addressList = res.data.data?.address_list || [];
        let defaultAddr = addressList.find(item => item.is_default === true || item.is_default == 1);

        if (defaultAddr) {
          const baseAddress = defaultAddr.address || ''; 
          const detailAddress = defaultAddr.detail || ''; 
          const fullAddress = `${baseAddress} ${detailAddress}`.replace(/\s+/g, ' ').trim();

          const sender = {
            name: defaultAddr.name || '',
            mobile: defaultAddr.phone || '',
            fullAddress: fullAddress
          };
          this.setData({ sender });
          
          // 如果此时收件人也选好了，自动触发估算
          this.checkAndEstimate();
        }
      }
    });
  },

  // 🌟 去选择寄件人/收件人地址（你需要对接你的地址本页面）
// 🌟 改造：跳过去的时候，告诉地址页当前是选寄件人(sender)还是收件人(receiver)
chooseSender() {
  wx.navigateTo({ url: '/pages/address/address?type=sender' });
},
chooseReceiver() {
  wx.navigateTo({ url: '/pages/address/address?type=receiver' });
},

// 🌟 新增：暴露给 address.js 调用的接收函数
setAddressFromSelect(type, addrData) {
  // 1. 统一清洗地址格式
  const baseAddress = addrData.address || addrData.province + addrData.city + (addrData.district || addrData.area) || ''; 
  const detailAddress = addrData.detail || addrData.full_address || ''; 
  const fullAddress = `${baseAddress} ${detailAddress}`.replace(/\s+/g, ' ').trim();

  const formattedAddr = {
    name: addrData.name || '',
    mobile: addrData.phone || addrData.mobile || '',
    fullAddress: fullAddress
  };

  // 2. 存入对应的变量 (sender 或 receiver)
  this.setData({
    [type]: formattedAddr
  }, () => {
    // 3. 选完地址后，自动触发京东运费预估！
    this.checkAndEstimate();
  });
},

  onCargoNameInput(e) {
    this.setData({ cargoName: e.detail.value });
  },

  onSpecChange(e) {
    this.setData({ selectedSpecIndex: e.detail.value }, () => {
      this.checkAndEstimate();
    });
  },

  // 🌟 统一触发估价逻辑
  checkAndEstimate() {
    const { sender, receiver } = this.data;
    // 只有寄收件人都填了，才去请求京东预估运费
    if (sender.name && receiver.name) {
      this.jdPreCheck();
    }
  },

  // 🌟 呼叫后端京东预估接口
  jdPreCheck() {
    const { sender, receiver, cargoName, packageSpecs, selectedSpecIndex } = this.data;

    this.setData({
      precheckLoading: true,
      precheckStatus: null,
      errorMsg: "",
      freight: 0,
      needPoints: 0
    });

    const currentSpec = packageSpecs[selectedSpecIndex];
    // 随便生成一个临时单号给京东预校验用（因为京东API强校验 orderId）
    const tempOrderSn = 'PRE_' + Date.now(); 

    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd-logistics/precheck/`,
      method: 'POST',
      header: app.getRequestHeader(),
      data: {
        order_sn: tempOrderSn, // 传个假单号仅供查运费
        sender: sender,
        receiver: receiver,
        quantity: 1,
        cargo_name: cargoName || '日用品',
        cargo_weight: currentSpec.weight,
        cargo_volume: currentSpec.volume
      },
      success: (res) => {
        const freight = parseFloat(res.data.data?.freight || 0);
        // 向上取整计算积分 (1元=100分)
        const needPoints = Math.ceil(freight * 100);

        this.setData({
          precheckLoading: false,
          precheckStatus: res.data.data?.success || false,
          errorMsg: res.data.data?.error_msg || "",
          freight: freight,
          needPoints: needPoints
        });

        if (res.data.data?.success) {
          wx.showToast({ title: '已计算预估积分', icon: 'success' });
        }
      },
      fail: () => {
        this.setData({ precheckLoading: false });
      }
    });
  },

  onSubmitJDExpress() {
    const { sender, receiver, precheckStatus, needPoints, userPoints } = this.data;

    if (!sender.fullAddress || !receiver.fullAddress) {
      return wx.showToast({ title: '请完善寄/收件地址', icon: 'none' });
    }
    if (precheckStatus === null) return;
    if (precheckStatus === false) {
      return wx.showModal({ title: '风险提示', content: `地址受限：${this.data.errorMsg}`, showCancel: false });
    }

    if (needPoints > userPoints) {
      return wx.showModal({
        title: '积分不足',
        content: `需要 ${needPoints} 积分，当前仅有 ${userPoints} 积分。`,
        showCancel: false
      });
    }

    wx.showModal({
      title: '确认消耗积分？',
      content: `预估先扣除 ${needPoints} 积分，实际扣除以京东最终计费为准，差额多退少补。`,
      confirmColor: '#e64340',
      success: (res) => {
        if (res.confirm) this.executeJDSubmit();
      }
    });
  },

  executeJDSubmit() {
    const { sender, receiver, cargoName, packageSpecs, selectedSpecIndex, needPoints } = this.data;
    const currentSpec = packageSpecs[selectedSpecIndex];
    if (this.data.pickupStartTime) {
      requestData.pickupStartTime = this.data.pickupStartTime;
      requestData.pickupEndTime = this.data.pickupEndTime;
    }
    this.setData({ isSubmitting: true });
    wx.showLoading({ title: '扣除并呼叫...', mask: true });

    wx.request({
      // 🌟 注意：这里的后端接口需要同时做三件事：1. 扣除积分 2. 在数据库生成一条真实的订单记录 3. 用真实的订单号去呼叫京东生成运单
      url: `${app.globalData.baseUrl}/app01/jd-logistics/create-order-and-waybill/`, 
      method: 'POST',
      header: app.getRequestHeader(),
      data: {
        sender: sender,
        receiver: receiver,
        quantity: 1,
        cargo_name: cargoName || '日用品',
        cargo_weight: currentSpec.weight,
        cargo_volume: currentSpec.volume,
        deduct_points: needPoints // 前端认定的扣除积分数，传给后端去执行扣费
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isSubmitting: false });
        if (res.data?.code === 200) {
          wx.showToast({ title: '叫件成功', icon: 'success' });
          setTimeout(() => wx.navigateBack(), 2000);
        } else {
          wx.showModal({ title: '失败', content: res.data?.msg || '系统错误', showCancel: false });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isSubmitting: false });
      }
    });
  }
});
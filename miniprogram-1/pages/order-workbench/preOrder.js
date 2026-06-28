Page({
  data: {
    loading: true,
    orderSn: '',
    orderDetail: {},
    isSubmitting: false,
    sender: {},
    receiver: {},
    precheckLoading: false,
    "orderDetail.jd_precheck_status": null,
    "orderDetail.jd_error_msg": "",
    cargoName: '护肤品',
    cargoWeight: 1.0,
    cargoVolume: 10.0
  },

  onLoad(options) {
    const orderSn = options.order_sn;
    if (orderSn) {
      this.setData({ orderSn });
      this.fetchOrderDetail(orderSn);
    } else {
      wx.showToast({ title: '订单号异常', icon: 'error' });
      setTimeout(() => wx.navigateBack(), 1500);
    }
  },

  onShow() {
    if (this.data.orderSn && !this.data.loading && Object.keys(this.data.sender).length === 0) {
      this.getDefaultSenderAddress();
    }
  },

  fetchOrderDetail(orderSn) {
    const app = getApp();
    const header = app.getRequestHeader();

    wx.request({
      url: `${app.globalData.baseUrl}/app01/order/detail/`,
      method: 'GET',
      header: header,
      data: { order_sn: orderSn },
      success: (res) => {
        console.log("📦 订单完整数据：", res.data);
        const orderDetail = res.data.data || {};
        this.setData({
          orderDetail: orderDetail,
          loading: false,
          "orderDetail.jd_precheck_status": null,
          "orderDetail.jd_error_msg": ""
        });

        const receiverInfo = orderDetail.receiver_info || {};
        
        // 🌟 核心修复：提取 address (省市区) 与详细地址进行拼接
        const baseAddress = receiverInfo.address || ''; 
        // 兼容处理：详细地址可能在 detail 或 full_address 中
        const detailAddress = receiverInfo.detail || receiverInfo.full_address || ''; 
        
        // 拼接成完整的省市区+详细地址，并过滤多余空格
        const recFullAddress = `${baseAddress} ${detailAddress}`.replace(/\s+/g, ' ').trim();

        this.setData({
          receiver: {
            name: receiverInfo.name || '',
            mobile: receiverInfo.phone || '',
            fullAddress: recFullAddress // 赋值拼接好的终极完整地址
          }
        });

        this.getDefaultSenderAddress();
      },
      fail: () => {
        wx.showToast({ title: '网络异常', icon: 'none' });
        this.setData({ loading: false });
      }
    });
  },

  getDefaultSenderAddress() {
    if (this.data.sender.name) return;

    const app = getApp();
    app.request({
      url: `${app.globalData.baseUrl}/app01/address/list/`,
      method: 'GET',
      header: app.getRequestHeader()
    }).then(res => {
      if (res.data.code === 200) {
        const addressList = res.data.data?.address_list || [];
        let defaultAddr = addressList.find(item => item.is_default === true || item.is_default == 1);

        if (defaultAddr) {
          // 🌟 核心调试打印 2：看看后端的寄件人(地址列表)原始字段长什么样
          console.log("🔍 [Debug] 后端返回的寄件人(defaultAddr)原始数据:", defaultAddr);

          const province = defaultAddr.province || '';
          const city = defaultAddr.city || '';
          const area = defaultAddr.district || defaultAddr.area || ''; // 兼容了district
          const detail = defaultAddr.detail || '';
          
          const fullAddress = `${province} ${city} ${area} ${detail}`.replace(/\s+/g, ' ').trim();

          const sender = {
            name: defaultAddr.name || '',
            mobile: defaultAddr.phone || '',
            fullAddress: fullAddress
          };

          this.setData({
            sender: sender,
            "orderDetail.sender_name": sender.name || '默认寄件人',
            "orderDetail.sender_phone": sender.mobile || '无联系方式',
            "orderDetail.sender_address": sender.fullAddress || '无发货地址'
          });

          console.log("✅ 寄件信息组装成功：", sender);
          if (this.data.receiver.name && this.data.receiver.mobile) {
            this.jdPreCheck();
          }
        } else {
          wx.showToast({ title: '未设置默认发货地址', icon: 'none' });
          this.setData({
            "orderDetail.sender_name": '未设置',
            "orderDetail.sender_phone": '未设置',
            "orderDetail.sender_address": '请设置默认发货地址'
          });
        }
      }
    }).catch(err => {
      console.error("❌ 获取地址失败：", err);
    });
  },
  // ✅ 终极修复：地址拼接，彻底杜绝 undefined
  getDefaultSenderAddress() {
    if (this.data.sender.name) return;

    const app = getApp();
    app.request({
      url: `${app.globalData.baseUrl}/app01/address/list/`,
      method: 'GET',
      header: app.getRequestHeader()
    }).then(res => {
      if (res.data.code === 200) {
        const addressList = res.data.data?.address_list || [];
        let defaultAddr = addressList.find(item => item.is_default === true || item.is_default == 1);

        if (defaultAddr) {
          
          // 🌟 核心修改：直接利用后端已有的 address 和 detail 字段进行拼接
          const baseAddress = defaultAddr.address || ''; // 例如："北京市 北京市 海淀区"
          const detailAddress = defaultAddr.detail || ''; // 例如："东升科技园2期8号楼b2驿站"
          
          // 拼接并过滤多余空格
          const fullAddress = `${baseAddress} ${detailAddress}`.replace(/\s+/g, ' ').trim();

          const sender = {
            name: defaultAddr.name || '',
            mobile: defaultAddr.phone || '',
            fullAddress: fullAddress
          };

          this.setData({
            sender: sender,
            "orderDetail.sender_name": sender.name || '默认寄件人',
            "orderDetail.sender_phone": sender.mobile || '无联系方式',
            "orderDetail.sender_address": sender.fullAddress || '无发货地址'
          });

          console.log("✅ 寄件信息组装成功：", sender);
          if (this.data.receiver.name && this.data.receiver.mobile) {
            this.jdPreCheck();
          }
        } else {
          wx.showToast({ title: '未设置默认发货地址', icon: 'none' });
          this.setData({
            "orderDetail.sender_name": '未设置',
            "orderDetail.sender_phone": '未设置',
            "orderDetail.sender_address": '请设置默认发货地址'
          });
        }
      }
    }).catch(err => {
      console.error("❌ 获取地址失败：", err);
    });
  },

  jdPreCheck() {
    const app = getApp();
    // 🌟 1. 把动态包裹数据也解构出来
    const { orderSn, sender, receiver, orderDetail, cargoName, cargoWeight, cargoVolume } = this.data;

    if (!sender.name || !sender.mobile || !receiver.name || !receiver.mobile) {
      wx.showToast({ title: '寄/收件信息不完整', icon: 'none' });
      return;
    }

    this.setData({
      precheckLoading: true,
      "orderDetail.jd_precheck_status": null,
      "orderDetail.jd_error_msg": "",
      "orderDetail.jd_freight": 0 // 🌟 新增：初始化运费
    });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd-logistics/precheck/`,
      method: 'POST',
      header: app.getRequestHeader(),
      data: {
        order_sn: orderSn,
        sender: sender,
        receiver: receiver,
        quantity: orderDetail.goods_count || 1,
        // 🌟 2. 传给后端算运费
        cargo_name: cargoName || '护肤品',
        cargo_weight: parseFloat(cargoWeight) || 1.0,
        cargo_volume: parseFloat(cargoVolume) || 10.0
      },
      success: (res) => {
        console.log("✅ 预校验结果：", res.data);
        this.setData({
          precheckLoading: false,
          "orderDetail.jd_precheck_status": res.data.data?.success || false,
          "orderDetail.jd_error_msg": res.data.data?.error_msg || "",
          "orderDetail.jd_freight": res.data.data?.freight || 0 // 🌟 3. 接收并保存后端返回的预估运费
        });

        if (res.data.data?.success) {
          wx.showToast({ title: '京东校验通过', icon: 'success' });
        }
      },
      fail: (err) => {
        this.setData({ precheckLoading: false });
      }
    });
  },
  goToAddressList() {
    wx.navigateTo({ url: '/pages/address/address' });
  },

  onSubmitJDExpress() {
    const { orderDetail, sender, precheckLoading } = this.data;

    if (precheckLoading) {
      wx.showToast({ title: '校验中，请稍候...', icon: 'loading' });
      return;
    }

    if (!sender.fullAddress) {
      wx.showToast({ title: '请设置发货地址', icon: 'error' });
      return;
    }

    if (orderDetail.jd_precheck_status === null) {
      wx.showModal({
        title: '提示',
        content: '未完成京东前置校验，是否继续提交？',
        success: (res) => {
          if (res.confirm) this.executeJDSubmit();
        }
      });
      return;
    }

    if (orderDetail.jd_precheck_status === false) {
      wx.showModal({
        title: '风险提示',
        content: `校验未通过：${orderDetail.jd_error_msg || '地址异常'}，是否继续？`,
        success: (res) => {
          if (res.confirm) this.executeJDSubmit();
        }
      });
      return;
    }

    wx.showModal({
      title: '确认发货',
      content: '确认发起京东揽收？',
      confirmColor: '#007aff',
      success: (res) => {
        if (res.confirm) this.executeJDSubmit();
      }
    });
  },
  onCargoNameInput(e) {
    this.setData({ cargoName: e.detail.value });
  },
  onCargoWeightInput(e) {
    this.setData({ cargoWeight: e.detail.value });
  },
  onCargoVolumeInput(e) {
    this.setData({ cargoVolume: e.detail.value });
  },
  // 提交发货（完整参数）
  executeJDSubmit() {
    const { orderSn, sender, receiver, orderDetail, cargoName, cargoWeight, cargoVolume } = this.data;
    this.setData({ isSubmitting: true });
    wx.showLoading({ title: '提交中...', mask: true });

    const app = getApp();
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd-logistics/create-waybill/`,
      method: 'POST',
      header: app.getRequestHeader(),
      data: {
        order_sn: orderSn,
        sender: sender,
        receiver: receiver,
        quantity: orderDetail.goods_count || 1,
        
        // 🌟 核心增补：向后端上报动态物流数据
        cargo_name: cargoName || '护肤品',
        cargo_weight: parseFloat(cargoWeight) || 1.0,
        cargo_volume: parseFloat(cargoVolume) || 10.0
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isSubmitting: false });
        if (res.data?.code === 200) {
          wx.showToast({ title: '创建成功', icon: 'success' });
          setTimeout(() => wx.navigateBack(), 1500);
        } else {
          wx.showModal({ title: '失败', content: res.data?.msg || '系统错误', showCancel: false });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isSubmitting: false });
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  }
});
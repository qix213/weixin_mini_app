const app = getApp();
Page({
  data: {
    loading: true,
    loadingBtn: false,
    order_sn: "",

    // 原始数据（对比用）
    original: {
      sender: {},
      receiver: {}
    },
    // 表单数据
    sender: {
      name: "",
      phone: "",
      fullAddress: "",
      extendProps: { extendProps: { key: "oaid", value: "" } }
    },
    receiver: {
      name: "",
      phone: "",
      fullAddress: "",
      extendProps: { extendProps: { key: "oaid", value: "" } }
    },
    // 地址选择器显示文本
    senderRegionText: "",
    receiverRegionText: "",
    // 详细地址
    senderDetailAddr: "",
    receiverDetailAddr: ""
  },

  onLoad(options) {
    const order_sn = options.order_sn;
    if (!order_sn) {
      wx.showToast({ title: "参数错误", icon: "none" });
      return;
    }
    console.log("📌 订单号：", order_sn);
    this.setData({ order_sn });
    this.getOrderDetail();
  },

  // 获取订单详情 + 自动回填所有信息
// 获取订单详情 + 自动回填所有信息
getOrderDetail() {
  wx.request({
    url: `${app.globalData.baseUrl}/app01/order/detail/`,
    method: "GET",
    data: { order_sn: this.data.order_sn },
    header: app.getRequestHeader(),
    success: (res) => {
      console.log("📌 订单详情：", res.data);
      const { data } = res.data;
      
      // 收件人信息（正常，直接用）
      const receiver = data.receiver_info;
      const receiverRegion = `${receiver.province} ${receiver.city} ${receiver.district}`.trim();
      const receiverDetail = receiver.detail || "";

      // ✅【修复】寄件人：后端字段为空，强制从 full_address 拆分
      const sender = data.sender_info;
      let senderRegion = "请选择地区";
      let senderDetail = "";
      if (sender.full_address) {
        const addrArr = sender.full_address.split(" ");
        // 拆分：前2段为省+市，剩余为详细地址（匹配你的地址格式：山东省 青岛市 xxx）
        if (addrArr.length >= 2) {
          senderRegion = addrArr.slice(0, 2).join(" ");
          senderDetail = addrArr.slice(2).join(" ").trim();
        } else {
          senderRegion = sender.full_address;
        }
      }
      const senderFullAddr = sender.full_address;

      this.setData({
        loading: false,
        original: { sender, receiver },
        // 回填寄件人
        sender: {
          name: sender.name,
          phone: sender.phone,
          fullAddress: senderFullAddr,
          extendProps: { extendProps: { key: "oaid", value: "" } }
        },
        senderRegionText: senderRegion,
        senderDetailAddr: senderDetail,
        // 回填收件人
        receiver: {
          name: receiver.name,
          phone: receiver.phone,
          fullAddress: receiver.full_address,
          extendProps: { extendProps: { key: "oaid", value: "" } }
        },
        receiverRegionText: receiverRegion,
        receiverDetailAddr: receiverDetail
      });
    },
    fail: (err) => {
      console.log("❌ 获取订单失败：", err);
      this.setData({ loading: false });
      wx.showToast({ title: "加载失败", icon: "error" });
    }
  });
},

  // ============= 寄件人输入绑定 =============
  inputSenderName(e) { this.setData({ "sender.name": e.detail.value }); },
  inputSenderPhone(e) { this.setData({ "sender.phone": e.detail.value }); },
  // 寄件人地区选择
  changeSenderRegion(e) {
    const region = e.detail.value.join(" ");
    this.setData({ senderRegionText: region });
    this.updateFullAddress("sender");
  },
  // 寄件人详细地址
  inputSenderDetail(e) {
    this.setData({ senderDetailAddr: e.detail.value });
    this.updateFullAddress("sender");
  },

  // ============= 收件人输入绑定 =============
  inputReceiverName(e) { this.setData({ "receiver.name": e.detail.value }); },
  inputReceiverPhone(e) { this.setData({ "receiver.phone": e.detail.value }); },
  // 收件人地区选择
  changeReceiverRegion(e) {
    const region = e.detail.value.join(" ");
    this.setData({ receiverRegionText: region });
    this.updateFullAddress("receiver");
  },
  // 收件人详细地址
  inputReceiverDetail(e) {
    this.setData({ receiverDetailAddr: e.detail.value });
    this.updateFullAddress("receiver");
  },

  // 拼接完整地址（核心）
  updateFullAddress(type) {
    const region = type === "sender" ? this.data.senderRegionText : this.data.receiverRegionText;
    const detail = type === "sender" ? this.data.senderDetailAddr : this.data.receiverDetailAddr;
    const fullAddress = `${region} ${detail}`.trim();
    this.setData({ [`${type}.fullAddress`]: fullAddress });
  },

  // ============= 提交：仅传修改内容 =============
  submit() {
    const { original, sender, receiver, order_sn } = this.data;
    const modify_data = {};

    // 判断寄件人是否修改
    const senderChanged = 
      sender.name !== original.sender.name ||
      sender.phone !== original.sender.phone ||
      sender.fullAddress !== original.sender.full_address;

    // 判断收件人是否修改
    const receiverChanged = 
      receiver.name !== original.receiver.name ||
      receiver.phone !== original.receiver.phone ||
      receiver.fullAddress !== original.receiver.full_address;

    // 仅修改了才传参
    if (senderChanged) modify_data.senderContact = sender;
    if (receiverChanged) modify_data.receiverContact = receiver;

    // 无修改判断
    if (Object.keys(modify_data).length === 0) {
      wx.showToast({ title: "未修改任何信息", icon: "none" });
      return;
    }

    console.log("📌 提交后端参数：", modify_data);

    this.setData({ loadingBtn: true });
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd/order/modify/`,
      method: "POST",
      header: app.getRequestHeader(),
      data: { order_sn, modify_data },
      success: (res) => {
        console.log("📌 后端返回：", res.data);
        if (res.data.code === 200) {
          wx.showToast({ title: "修改成功" });
          setTimeout(() => wx.navigateBack(), 1500);
        } else {
          wx.showToast({ title: res.data.msg, icon: "error" });
        }
      },
      fail: () => {
        wx.showToast({ title: "网络异常", icon: "error" });
      },
      complete: () => {
        this.setData({ loadingBtn: false });
      }
    });
  }
});
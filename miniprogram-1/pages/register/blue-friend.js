Page({
  data: {
    userId: '',
    nickname: '',
    birth: '',
    phone: '',
    code: '',
    pwd: '',
    pwdConfirm: '',
    email: '',
    region: '',
    address: '',
    agree: false,
    codeDisabled: false,
    codeText: '获取验证码'
  },

  // 输入框内容变化
  handleInput(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({ [key]: e.detail.value });
  },

  // 选择出生日期
  pickBirth() {
    wx.datePicker({
      start: '1900-01-01',
      end: new Date().toISOString().split('T')[0],
      success: (res) => {
        this.setData({ birth: res.date });
      }
    });
  },

  // 选择省市区
  pickRegion() {
    wx.chooseLocation({
      success: (res) => {
        this.setData({ region: res.address });
      }
    });
  },

  // 协议勾选
  handleAgree(e) {
    this.setData({ agree: e.detail.value[0] === 'true' });
  },

  // 获取验证码（逻辑同登录页）
  getCode() {
    const { phone } = this.data;
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showToast({ title: '请输入正确手机号', icon: 'none' });
      return;
    }

    let count = 60;
    this.setData({ codeDisabled: true, codeText: `${count}s后重新获取` });
    const timer = setInterval(() => {
      count--;
      if (count <= 0) {
        clearInterval(timer);
        this.setData({ codeDisabled: false, codeText: '获取验证码' });
      } else {
        this.setData({ codeText: `${count}s后重新获取` });
      }
    }, 1000);

    wx.showToast({ title: '验证码已发送', icon: 'none' });
  },

  // 注册提交
  handleRegister() {
    const { userId, phone, code } = this.data;
    // 模拟校验（实际对接后台）
    if (code !== '123456') {
      wx.showToast({ title: '验证码错误', icon: 'none' });
      return;
    }
    if (!/^CN[a-zA-Z0-9]+$/.test(userId)) {
      wx.showToast({ title: '会员ID需以CN开头，含字母数字', icon: 'none' });
      return;
    }

    // 注册成功：存储会员信息，跳转成功页
    wx.setStorageSync('userInfo', {
      userId,
      memberType: '蓝朋友',
     权益: [
        '蓝粉VIP大礼包：3套SSTA旅行mini装，5张100元兑换单品券（单次用一张）',
        '会员积分：SSTA家居产品，10元积1分，可兑换',
        '会员价：SSTA家居产品，一年蓝粉星价'
      ]
    });
    wx.navigateTo({ url: '/pages/register/success?type=blueFriend' });
  }
});
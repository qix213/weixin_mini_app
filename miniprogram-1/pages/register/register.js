const app = getApp();
Page({
  data: {
    memberId: '',
    nickname: '',        // 昵称
    phone: '19261080527',// 手机号
    password: '',        // 密码
    passwordConfirm: '', // 确认密码
    activeTab: 0,        // 0=成为会员，1=我要开店
    tabList: [
      { name: '成为会员', id: 0 },
      { name: '我要开店', id: 1 }
    ],
    // 成为会员Tab的类型列表
    memberTypeList: [
      { 
        value: 1, 
        name: '蓝朋友（0元/年）', 
        amount: 0, // 费用
        benefits: [
          "SSTA新人券：2张200元代金券套，只能用来购买368元mini旅行套；",
          "SSTA价格：零售价格购买产品，不享受会员价；",
          "SSTA卡券：节日活动或生日优享券，优享活动参与资格；",
          "公益课程：护肤知识课程。"
        ],
        permissionLevel: 1 
      },
      { 
        value: 2, 
        name: '蓝明星（980元/年）', 
        amount: 980, // 费用
        benefits: [
          "蓝粉VIP大礼包（2选1）:（1）3套SSTA旅行套盒，2张100元兑换单品券（每单限用一张），限期一个月；（2）一套小油净化（6次），4张100元兑换单品券（每单限用一张），限期一个月；",
          "会员星价：SSTA家居产品，一年蓝粉星价",
          "会员积分：SSTA家居产品，10元积1分，可兑换",
          "SSTA卡券：节日活动或生日优享券，优享活动参与资格",
          "公益课程：家居护肤课程。"
        ],
        permissionLevel: 2 
      },
      { 
        value: 3, 
        name: '护肤私教（3980元/年）', 
        amount: 3980, // 费用
        benefits: [
          "SSTA大礼包（2选1）:（1）3980元SSTA家居产品任选，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；（2）一年24次SSTA小油净化，2套SSTA旅行套，5张100元兑换单品券（每单限用一张），限期三个月；",
          "SSTA积分：SSTA家居产品积分兑换，10元积1分；",
          "SSTA奇肌币：裂变客户购买产品15%返点，可提现；",
          "SSTA卡券：节日或活动优享券；",
          "专业课程：护肤专业课程。"
        ],
        permissionLevel: 3 
      }
    ],
    // 我要开店Tab的类型列表
    shopTypeList: [
      { 
        value: 4, 
        name: 'MINI-studio 主理人（9800元）', 
        amount: 9800, // 费用
        benefits: [
          "产品折扣：享产品零售价5折权益，产品任选；",
          "培训赋能：护肤私教初级班+初级证书；",
          "工具系统：系统化配套标准化+工具设备；",
          "专业课程：蓝色奇肌商学院小程序专业皮肤课程。"
        ],
        permissionLevel: 4 
      },
      { 
        value: 5, 
        name: 'Ta创+（9.8万元）', 
        amount: 98000, // 费用
        benefits: [
          "Ta创+高端俱乐部会员，享奇肌疗愈营，高端沙龙活动；",
          "产品折扣：享产品零售价2.5折权益，产品任选；",
          "SSTA运营：运营中心模版店的打造及扶持；",
          "培训赋能：护肤私教全部体系课程+证书；",
          "专业课程：蓝色奇肌商学院小程序专业皮肤课程；",
          "《她力量》，《明星代言人》首推官资格。",
        ],
        permissionLevel: 5 
      }
    ],
    userTypeIndex: 0,    // 当前Tab下的类型选择索引
    selectedUserType: {}, // 当前选中的会员/开店类型
    currentBenefits: [],  // 当前类型对应的权益
    // ====== 关键修改3：推荐人ID默认值改为ABCD1234（大写） ======
    recommenderId: 'ABCD1234',    // 推荐人ID（默认大写）
    verifyCode: '123456',       // 验证码（默认123456）
    countDown: 0,
    timer: null
  },

  onLoad(options) {
    this.generateMemberId();
    const defaultUserType = this.data.memberTypeList[0];
    this.setData({
      selectedUserType: defaultUserType,
      currentBenefits: defaultUserType.benefits
    });
  },

  onUnload() {
    if (this.data.timer) {
      clearInterval(this.data.timer);
      this.setData({ timer: null });
    }
  },

  generateMemberId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let memberId = '';
    for (let i = 0; i < 8; i++) {
      memberId += chars[Math.floor(Math.random() * chars.length)];
    }
    this.setData({ memberId });
  },

  refreshMemberId() {
    this.generateMemberId();
    wx.showToast({ title: '会员ID已刷新', icon: 'success', duration: 1000 });
  },

  switchTab(e) {
    const tabId = Number(e.currentTarget.dataset.tabid);
    this.setData({
      activeTab: tabId,
      userTypeIndex: 0
    });
    let defaultType = {};
    if (tabId === 0) {
      defaultType = this.data.memberTypeList[0];
    } else {
      defaultType = this.data.shopTypeList[0];
    }
    this.setData({
      selectedUserType: defaultType,
      currentBenefits: defaultType.benefits
    });
  },

  handleNicknameInput(e) {
    this.setData({ nickname: e.detail.value.trim() });
  },
  handlePhoneInput(e) {
    this.setData({ phone: e.detail.value.trim() });
  },
  handlePasswordInput(e) {
    this.setData({ password: e.detail.value.trim() });
  },
  handlePasswordConfirmInput(e) {
    this.setData({ passwordConfirm: e.detail.value.trim() });
  },
  handleUserTypeChange(e) {
    const index = e.detail.value;
    let selected = {};
    if (this.data.activeTab === 0) {
      selected = this.data.memberTypeList[index];
    } else {
      selected = this.data.shopTypeList[index];
    }
    this.setData({
      userTypeIndex: index,
      selectedUserType: selected,
      currentBenefits: selected.benefits
    });
  },
  handleRecommenderIdInput(e) {
    this.setData({ recommenderId: e.detail.value.trim() });
  },
  handleCodeInput(e) {
    this.setData({ verifyCode: e.detail.value.trim() });
  },

  getSmsCode() {
    const { phone } = this.data;
    if (!/^1[3-9]\d{9}$/.test(phone)) {
        wx.showToast({ title: "请输入正确的手机号", icon: "none" });
        return;
    }
    wx.request({
        url: `${app.globalData.baseUrl}/app01/send-sms/`,
        method: "POST",
        data: { phone },
        success: (res) => {
            if (res.data.code === 200) {
                wx.showToast({ title: "验证码已发送", icon: "success" });
                this.setData({ bizId: res.data.data.biz_id });
                this.startCountDown();
            } else {
                wx.showToast({ title: res.data.msg, icon: "none" });
            }
        },
        fail: (err) => {
            wx.showToast({ title: "网络异常", icon: "none" });
            console.error("发送验证码失败：", err);
        }
    });
  },

  handleGetVerifyCode() {
    const { phone } = this.data;
    const phoneReg = /^1[3-9]\d{9}$/;
    if (!phone || !phoneReg.test(phone)) {
      wx.showToast({ title: '请输入正确的11位手机号', icon: 'none' });
      return;
    }
    if (this.data.countDown > 0) {
      wx.showToast({ title: '请稍后再获取验证码', icon: 'none' });
      return;
    }
    let count = 60;
    this.setData({
      countDown: count,
      timer: setInterval(() => {
        count--;
        this.setData({ countDown: count });
        if (count <= 0) {
          clearInterval(this.data.timer);
          this.setData({ timer: null });
        }
      }, 1000)
    });
    wx.showToast({ title: '验证码发送成功（123456）', icon: 'success' });
  },

  // 注册逻辑（已移除验证码和推荐人ID校验）
  handleRegister() {
    const {
      memberId, nickname, phone, password, passwordConfirm,
      selectedUserType, recommenderId, verifyCode
    } = this.data;
    const app = getApp(); 
    const userType = selectedUserType.value;
    const userTypeName = selectedUserType.name;
    const userTypeAmount = selectedUserType.amount; // 获取费用

    // 1. 基础验证（仅保留昵称、手机号、密码校验）
    if (!nickname) { wx.showToast({ title: '请设置昵称', icon: 'none' }); return; }
    const phoneReg = /^1[3-9]\d{9}$/;
    if (!phone || !phoneReg.test(phone)) { wx.showToast({ title: '请输入正确的11位手机号', icon: 'none' }); return; }
    const pwdReg = /^(?=.*[0-9])(?=.*[a-zA-Z])(?!.*\s).{8,}$/;
    if (!password || !pwdReg.test(password)) {
      wx.showToast({ title: '密码需8位以上数字+字母组合', icon: 'none' }); return;
    }
    if (password !== passwordConfirm) {
      wx.showToast({ title: '两次密码不一致', icon: 'none' }); return;
    }

    // 2. 组装注册数据
    const registerData = {
      nickname: nickname,
      phone: phone,
      password: password,
      password_confirm: passwordConfirm,
      user_type: userType,
      recommender_id: recommenderId,       
    };

    // 3. 发送注册请求
    wx.showLoading({ title: '注册中...', mask: true });
    wx.request({
      url: app.globalData.baseUrl + '/app01/register/',
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: registerData,
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          // 存储用户信息
          const userInfo = res.data.user_info;
          app.globalData.userInfo = userInfo;
          app.globalData.accessToken = res.data.access;
          app.globalData.refreshToken = res.data.refresh;
          app.globalData.isLogin = true;

          wx.setStorageSync('userInfo', userInfo);
          wx.setStorageSync('accessToken', res.data.access);
          wx.setStorageSync('refreshToken', res.data.refresh);
          wx.setStorageSync('isLogin', true);

          // 类型判断跳转逻辑
          if (userType === 1) {
            wx.showToast({ title: '注册成功', icon: 'success', duration:1500 });
            setTimeout(()=>{
              wx.switchTab({ url: '/pages/index/index' });
            },1000);
          } else {
            wx.showToast({ title: '注册成功，请完成支付', icon: 'success', duration:1500 });
            setTimeout(()=>{
              wx.navigateTo({
                url: `/pages/pay/pay?typeName=${encodeURIComponent(userTypeName)}&amount=${userTypeAmount}&phone=${phone}`,
              });
            },1000);
          }
        } else {
          wx.showToast({ title: res.data.msg || '注册失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: '网络错误', icon: 'none' });
      }
    });
  },

  startCountDown() {
    let count = 60;
    this.setData({
      countDown: count,
      timer: setInterval(() => {
        count--;
        this.setData({ countDown: count });
        if (count <= 0) {
          clearInterval(this.data.timer);
          this.setData({ timer: null });
        }
      }, 1000)
    });
  }
});
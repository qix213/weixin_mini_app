const app = getApp();

Page({
  data: {
    // 基础表单字段
    memberId: '',
    nickname: '',        
    password: '',        
    passwordConfirm: '', 
    activeTab: 0,        
    avatarUrl: '',
    // 🌟 伸缩式生日选择器状态
    birthDate: '',       
    showDatePicker: false,
    dpStep: 'decade', 
    dpDecade: '',     
    dpYear: '',       
    dpMonth: '',      
    dpDay: '',        
    decades: [1960, 1970, 1980, 1990, 2000, 2010, 2020], 
    months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    days: [],         

    tabList: [
      { name: '成为会员', id: 0 },
      { name: '我要开店', id: 1 }
    ],
    memberTypeList: [
      { value: 1, name: '蓝朋友 0星', amount: 0.1 },
      { value: 2, name: '蓝朋友 1星', amount: 0.1 },
      { value: 3, name: '蓝朋友 2星', amount: 0.1 },
      { value: 4, name: '蓝朋友 3星', amount: 0.1 }
    ],
    shopTypeList: [
      { value: 5, name: 'Ta创+', amount: 0.1 }
    ],
    userTypeIndex: 0,    
    selectedUserType: {}, 
    
    recommenderId: 'LANSIK26',
    
    isAgreed: false,       
    showAgreement: false   
  },

  onLoad(options) {
    this.generateMemberId();
    this.setData({ selectedUserType: this.data.memberTypeList[0] });
  },

  onChooseAvatar(e) {
    const { avatarUrl } = e.detail;
    this.setData({ avatarUrl });
  },

  toggleDatePicker() {
    const isShowing = !this.data.showDatePicker;
    let step = this.data.dpStep;
    if (isShowing) {
      if (this.data.dpYear && this.data.dpMonth) {
        step = 'day';
        const daysInMonth = new Date(this.data.dpYear, this.data.dpMonth, 0).getDate();
        this.setData({ days: Array.from({length: daysInMonth}, (_, i) => i + 1) });
      } else {
        step = 'decade';
      }
    }
    this.setData({ showDatePicker: isShowing, dpStep: step });
  },

  goToDpStep(e) { this.setData({ dpStep: e.currentTarget.dataset.step }); },
  selectDecade(e) { this.setData({ dpDecade: e.currentTarget.dataset.val, dpStep: 'year' }); },
  selectYear(e) { this.setData({ dpYear: e.currentTarget.dataset.val, dpStep: 'month' }); },
  selectMonth(e) {
    const month = e.currentTarget.dataset.val;
    const daysInMonth = new Date(this.data.dpYear, month, 0).getDate();
    this.setData({ 
      dpMonth: month, 
      days: Array.from({length: daysInMonth}, (_, i) => i + 1),
      dpStep: 'day' 
    });
  },
  selectDay(e) {
    const day = e.currentTarget.dataset.val;
    const y = this.data.dpYear;
    const m = this.data.dpMonth < 10 ? '0' + this.data.dpMonth : this.data.dpMonth;
    const d = day < 10 ? '0' + day : day;
    
    this.setData({ 
      dpDay: day,
      birthDate: `${y}-${m}-${d}`,
      showDatePicker: false 
    });
  },

  generateMemberId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let memberId = '';
    for (let i = 0; i < 8; i++) { memberId += chars[Math.floor(Math.random() * chars.length)]; }
    this.setData({ memberId });
  },

  refreshMemberId() {
    this.generateMemberId();
    wx.showToast({ title: '会员ID已刷新', icon: 'success', duration: 1000 });
  },

  switchTab(e) {
    const tabId = Number(e.currentTarget.dataset.tabid);
    const defaultType = tabId === 0 ? this.data.memberTypeList[0] : this.data.shopTypeList[0];
    this.setData({ activeTab: tabId, userTypeIndex: 0, selectedUserType: defaultType });
  },

  // 表单输入绑定
  handleNicknameInput(e) { this.setData({ nickname: e.detail.value.trim() }); },
  handlePasswordInput(e) { this.setData({ password: e.detail.value.trim() }); },
  handlePasswordConfirmInput(e) { this.setData({ passwordConfirm: e.detail.value.trim() }); },
  handleRecommenderIdInput(e) { this.setData({ recommenderId: e.detail.value.trim() }); },

  handleUserTypeChange(e) {
    const index = e.detail.value;
    const selected = this.data.activeTab === 0 ? this.data.memberTypeList[index] : this.data.shopTypeList[index];
    this.setData({ userTypeIndex: index, selectedUserType: selected });
  },

  toggleAgreement() { this.setData({ isAgreed: !this.data.isAgreed }); },
  openAgreement() { this.setData({ showAgreement: true }); },
  closeAgreement() { this.setData({ showAgreement: false }); },
  preventBubbling() { },

  // ================= 🌟 核心：一键授权并提交注册 =================
  handleRegisterWithPhone(e) {
    const {
      memberId, nickname, password, passwordConfirm, 
      selectedUserType, recommenderId, activeTab, isAgreed, birthDate
    } = this.data;

    // 1. 协议校验
    if (!isAgreed) { wx.showToast({ title: '请先阅读并勾选《用户充值须知》', icon: 'none' }); return; }

    // 2. 基础表单严校验
    if (!this.data.avatarUrl) { wx.showToast({ title: '请点击顶部设置头像', icon: 'none' }); return; } // 🌟 拦截未设置头像
    if (!nickname) { wx.showToast({ title: '请设置昵称', icon: 'none' }); return; }
    if (!birthDate) { wx.showToast({ title: '请选择出生日期', icon: 'none' }); return; }
    
    // 🌟 新增：强制校验推荐人ID
    if (!recommenderId) { 
      wx.showToast({ title: '推荐人ID为必填项', icon: 'none' }); 
      return; 
    }

    if (!/^(?=.*[0-9])(?=.*[a-zA-Z])(?!.*\s).{8,}$/.test(password)) {
      wx.showToast({ title: '密码需8位以上数字+字母组合', icon: 'none' }); return;
    }
    if (password !== passwordConfirm) {
      wx.showToast({ title: '两次输入密码不一致，请检查', icon: 'none' }); return;
    }

    // 3. 检查用户是否同意了微信手机号授权
    if (e.detail.errMsg !== "getPhoneNumber:ok") {
      wx.showToast({ title: '需授权手机号才能完成注册', icon: 'none' }); 
      return;
    }

    // 4. 获取用于解密真实手机号的 code
    const phoneCode = e.detail.code;

    wx.showLoading({ title: '安全校验中...' });

// 5. 获取用于换取 openid 的 login code
wx.login({
  success: (res) => {
    if (!res.code) {
      wx.hideLoading();
      return wx.showToast({ title: '微信登录失败', icon: 'none' });
    }
    const loginCode = res.code;

    // 🌟 核心修改：跳转收银台前，先发给后端做校验和解密！
    wx.request({
      url: `${app.globalData.baseUrl}/app01/register/pre_check/`,
      method: 'POST',
      data: {
        recommender_id: recommenderId,
        phone_code: phoneCode
      },
      success: (checkRes) => {
        wx.hideLoading();
        // console.log("【后端预校验返回完整数据】:", checkRes.data); // 🌟 加上这行
        if (checkRes.data.code === 200) {
          // 校验通过！拿到后端解密出来的真实手机号
          const realPhone = checkRes.data.data.real_phone;

          // 6. 构建数据，注意：这里存的是 real_phone，彻底丢弃 phone_code！
          const registerData = {
            memberId: memberId,
            nickname: nickname,
            avatarUrl: this.data.avatarUrl,
            password: password,
            password_confirm: passwordConfirm,
            user_type: selectedUserType.value,
            recommender_id: recommenderId,
            birth_date: birthDate,
            real_phone: realPhone, // 🌟 传明文手机号给暂存区
            login_code: loginCode  
          };
          
          app.globalData.pendingRegisterData = registerData;
          wx.setStorageSync('pendingRegisterData', registerData);

          // 7. 安全放行，跳转支付页
          const scene = activeTab === 0 ? 'member' : 'shop';
          wx.showToast({ title: '校验通过，前往支付', icon: 'success', duration: 1000 });
          
          setTimeout(() => {
            wx.navigateTo({
              // 把真实的手机号展示在收银台页面
              url: `/pages/pay/pay?scene=${scene}&typeName=${encodeURIComponent(selectedUserType.name)}&amount=${selectedUserType.amount}&phone=${realPhone}&memberId=${memberId}`,
            });
          }, 1000);
        } else {
          // 拦截器生效：推荐人不对、手机号已经注册过、授权失败等，直接弹窗阻止跳转
          console.error("【业务拦截报错】:", checkRes.data.msg);
          wx.showToast({ title: checkRes.data.msg, icon: 'none', duration: 3000 });
        }
      },
      fail: () => {
        wx.hideLoading();
        console.error("【前端网络请求彻底失败】:", err);
        wx.showToast({ title: '网络异常，校验失败', icon: 'none' });
      }
    });
  }
});
  }
});
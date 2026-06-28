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
      { value: 1, name: '蓝朋友 0星', amount: 1 },
      { value: 2, name: '蓝朋友 1星', amount: 980 },
      { value: 3, name: '蓝朋友 2星', amount: 3980 },
      { value: 4, name: '蓝朋友 3星', amount: 9800 }
    ],
    shopTypeList: [
      { value: 5, name: 'Ta创+', amount: 39800 }
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
        wx.hideLoading();
        if (res.code) {
          const loginCode = res.code;

          // 6. 构建全新的注册数据结构（彻底抛弃明文 phone 和 verifyCode）
          const registerData = {
            memberId: memberId,
            nickname: nickname,
            avatarUrl: this.data.avatarUrl,
            password: password,
            password_confirm: passwordConfirm,
            user_type: selectedUserType.value,
            recommender_id: recommenderId, // 必填的推荐人ID
            birth_date: birthDate,
            phone_code: phoneCode,         // 传给后端去换取真实手机号
            login_code: loginCode          // 传给后端去换取 openid
          };
          
          app.globalData.pendingRegisterData = registerData;
          wx.setStorageSync('pendingRegisterData', registerData);

          // 7. 跳转支付页
          const scene = activeTab === 0 ? 'member' : 'shop';
          wx.showToast({ title: '授权成功，即将前往支付', icon: 'success', duration: 1500 });
          
          setTimeout(() => {
            wx.navigateTo({
              // phone 字段传入占位文字，实际手机号由后端解析生成
              url: `/pages/pay/pay?scene=${scene}&typeName=${encodeURIComponent(selectedUserType.name)}&amount=${selectedUserType.amount}&phone=微信授权手机号&memberId=${memberId}`,
            });
          }, 1000);
        } else {
          wx.showToast({ title: '微信登录失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  }
});
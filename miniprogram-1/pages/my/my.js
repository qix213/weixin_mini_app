const app = getApp();
Page({
  data: {
    isLogin: false,
    memberInfo: {}, // 完整会员信息
    showQrcode: false,
    points: 0, 
    couponCount: 0, 
    walletBalance: '0.00', // 🌟 1. 初始化定义钱包余额字段
    levelConfig: [
      {value:2,cost:980},
      {value:3,cost:3980},
      {value:4,cost:9800}
    ]},

  onShow() {
    this.syncGlobalState();
    if (this.data.isLogin) {
      this.getMemberInfo();
      this.getValidCouponCount(); 
    }
  },
// 🌟 2. 编写跳转到电子钱包明细页的方法
goToWallet() {
  wx.navigateTo({
    url: '/pages/wallet/wallet' // 指向你的钱包账单明细页
  });
},
  checkLogin(redirectPage = '') {
    if (!this.data.isLogin) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再操作',
        confirmText: '去登录',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            let loginUrl = '/pages/login/login';
            if (redirectPage) {
              loginUrl += `?redirect=${encodeURIComponent(redirectPage)}`;
            }
            wx.navigateTo({ url: loginUrl });
          }
        }
      });
      return false;
    }
    return true;
  },

  goToSubMemberConsume() {
    if (!this.checkLogin('/pages/my/my?action=subMemberConsume')) return;
    const currentLevel = this.data.memberInfo.user_type;
    if (!currentLevel) {
      wx.showToast({ title: '会员等级未获取，请刷新页面', icon: 'none' });
      return;
    }
    if (currentLevel === 1) {
      wx.showToast({ title: '当前会员等级无查看下级消费记录权限', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: `/pages/sub-member-consume/sub-member-consume?currentLevel=${currentLevel}` });
  },

  goToBillRecord() {
    if (!this.checkLogin('/pages/my/my?action=billRecord')) return;
    wx.navigateTo({ url: '/pages/bill-record/bill-record' });
  },

  goToMemberCenter() {
    wx.navigateTo({ 
      url: '/pages/my/benefits', 
      success: () => {},
      fail: (err) => {
        console.error("跳转失败", err);
      }
    });
  },

  goToPoints() {
    if (!this.checkLogin('/pages/my/my?action=points')) return;
    wx.navigateTo({ url: '/pages/points/points' });
  },

  goToCoupon() {
    if (!this.checkLogin('/pages/my/my?action=coupon')) return;
    wx.navigateTo({
      url: '/pages/coupun/coupun',
      fail: (err) => console.error('跳转失败：', err)
    });
  },

  goToAddressManage() {
    if (!this.checkLogin('/pages/my/my?action=address')) return;
    wx.navigateTo({ url: '/pages/address/address' });
  },

  goToInvoiceManage() {
    if (!this.checkLogin('/pages/my/my?action=invoice')) return;
    wx.navigateTo({ url: '/pages/order-list/order-list' });
  },

  goToSetting() {
    if (!this.checkLogin('/pages/my/my?action=setting')) return;
    wx.navigateTo({ url: '/pages/setting/setting' });
  },

  syncGlobalState() {
    const app = getApp();
    const memberInfo = app.globalData.memberInfo || {};
    this.setData({
      isLogin: app.globalData.isLogin || false,
      memberInfo: memberInfo,
      points: memberInfo.points || 0 
    });
  },

getMemberInfo() {
  const app = getApp();
  const header = app.getRequestHeader();

  wx.showLoading({ title: '加载会员信息...', mask: true });
  wx.request({
    url: app.globalData.baseUrl + '/app01/member/info/',
    method: 'GET',
    header: header,
    success: (res) => {
      wx.hideLoading();
      if (res.data.code === 200) {
        const memberInfo = res.data.data;

        const currentType = memberInfo.user_type || 1;
        const actualStars = Math.max(0, currentType - 1);
        memberInfo.starsArray = Array.from({ length: actualStars }, (v, i) => i);

        // 🌟 核心修复：优先取后端计算好的精准到期字段 expire_time 
        let expireDateStr = memberInfo.expire_time || memberInfo.expire_time_text;
        
        if (expireDateStr) {
          // 截取前10位(YYYY-MM-DD)，兼容带时区的完整时间戳字符串
          memberInfo.expire_time_text = expireDateStr.substring(0, 10);
        } else {
          // 兜底降级旧逻辑
          const joinDateStr = memberInfo.date_joined || memberInfo.create_time; 
          if (joinDateStr) {
            const safeDateStr = joinDateStr.substring(0, 10).replace(/-/g, '/');
            const joinDate = new Date(safeDateStr);
            joinDate.setFullYear(joinDate.getFullYear() + 1);
            const year = joinDate.getFullYear();
            const month = String(joinDate.getMonth() + 1).padStart(2, '0');
            const day = String(joinDate.getDate()).padStart(2, '0');
            memberInfo.expire_time_text = `${year}-${month}-${day}`;
          } else {
            memberInfo.expire_time_text = '永久有效'; 
          }
        }

        // 会员差额与会籍文本配置（同步支持5级：Ta创+）
        const levelCosts = { 1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5 };
        const levelNames = { 1: '蓝朋友0星', 2: '蓝朋友1星', 3: '蓝朋友2星', 4: '蓝朋友3星', 5: 'Ta创+' };

        if (currentType < 5) {
          // memberInfo.nextLevelDiff = levelCosts[currentType + 1] - levelCosts[currentType];
          memberInfo.nextLevelDiff = levelCosts[currentType + 1] ;        
          memberInfo.nextLevelName = levelNames[currentType + 1];
        } else {
          memberInfo.nextLevelDiff = 0; 
        }
        
        memberInfo.user_type_text = levelNames[currentType] || '蓝朋友0星';

        app.globalData.memberInfo = memberInfo; 
        
        this.setData({
          memberInfo: memberInfo,
          points: memberInfo.points || 0,
          couponCount: memberInfo.coupon_count || 0,
          walletBalance: memberInfo.wallet_balance || '0.00', 
          isLogin: true
        });
      } else {
        wx.showToast({ title: res.data.msg || '加载会员信息失败', icon: 'none' });
      }
    }
  });
},

// 🌟 新增：处理微信头像授权与上传
onChooseAvatar(e) {
  const { avatarUrl } = e.detail; // 这是微信给你的临时图片路径
  console.log('获取到微信头像临时路径：', avatarUrl);

  const app = getApp();
  const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;

  if (!token) {
    wx.showToast({ title: '登录状态已失效，请重新登录', icon: 'none' });
    return;
  }

  wx.showLoading({ title: '正在保存头像...' });

  // 调用后端的上传接口 (你需要在 Django 里写一个接收文件的接口)
  wx.uploadFile({
    url: app.globalData.baseUrl + '/app01/member/upload_avatar/', // ⚠️ 替换为你真实的后端接口路径
    filePath: avatarUrl,
    name: 'file', // Django 后端通过 request.FILES.get('file') 来获取
    header: {
      'Authorization': `Bearer ${token}`
    },
    success: (res) => {
      wx.hideLoading();
      try {
        // wx.uploadFile 返回的 data 是字符串，需要手动 parse
        const data = JSON.parse(res.data);
        if (data.code === 200) {
          wx.showToast({ title: '头像更新成功', icon: 'success' });
          
          // 🌟 局部刷新前端页面，立刻显示新头像
          // 假设后端返回的数据格式是 { data: { avatar_url: 'https://...' } }
          this.setData({
            'memberInfo.avatar_url': data.data.avatar_url
          });
          
          // 同步更新全局变量
          app.globalData.memberInfo.avatar_url = data.data.avatar_url;
          wx.setStorageSync('memberInfo', app.globalData.memberInfo);

        } else {
          wx.showToast({ title: data.msg || '上传失败', icon: 'none' });
        }
      } catch (err) {
        console.error('解析后端返回数据失败：', err);
        wx.showToast({ title: '服务器响应异常', icon: 'none' });
      }
    },
    fail: (err) => {
      wx.hideLoading();
      console.error('上传头像请求失败：', err);
      wx.showToast({ title: '网络异常，上传失败', icon: 'none' });
    }
  });
},

  getValidCouponCount() {
    const app = getApp();
    const header = app.getRequestHeader();
    
    wx.request({
      url: app.globalData.baseUrl + '/app01/user/coupons/',
      method: 'GET',
      header: header,
      data: { only_valid: true },
      success: (res) => {
        if (res.data.code === 200) {
          let couponList = res.data.data?.coupons || [];
          const now = new Date().getTime(); 
          const validCoupons = couponList.filter(coupon => {
            const isUnused = !coupon.is_used && coupon.is_used !== 1;
            let expireTime = coupon.end_time || coupon.expire_time;
            if (!expireTime) return true; 
            if (typeof expireTime === 'string') {
              expireTime = expireTime.replace(/-/g, '/');
            }
            expireTime = new Date(expireTime).getTime();
            return isUnused && (expireTime > now);
          });
          this.setData({ couponCount: validCoupons.length });
        } else {
          this.setData({ couponCount: 0 });
        }
      },
      fail: () => {
        this.setData({ couponCount: 0 });
      }
    });
  },

  goToLogin() { wx.navigateTo({ url: '/pages/login/login' }); },

  previewQrcode() {
    this.setData({ showQrcode: true });
    wx.showToast({ title: '长按二维码关注公众号', icon: 'none', duration: 2000 });
  },

  hideQrcode() { this.setData({ showQrcode: false }); },

  goToCustomerService() { wx.navigateTo({ url: '/pages/my/service' }); },

  goToLogout() {
    const app = getApp();
    wx.removeStorageSync('hakelong');
    wx.clearStorageSync();
    app.globalData = { ...app.globalData, isLogin: false, accessToken: '', memberInfo: {} };
    this.setData({ isLogin: false, memberInfo: {}, couponCount: 0 });
    wx.reLaunch({ url: '/pages/index/index' });
    wx.showToast({ title: '退出登录成功', icon: 'success' });
  },

  goToAIChat() {
    if (!this.checkLogin('/pages/my/my?action=aiChat')) return;
    wx.navigateTo({ url: '/pages/ai-chat/ai-chat' });
  },
  goToUpgrade() {
    if (!this.checkLogin('/pages/my/update')) return;
    wx.navigateTo({ url: '/pages/my/update' });
  },
  // 跳转线下项目
  goToOfflineProject() {
    const memberInfo = wx.getStorageSync('memberInfo') || app.globalData.memberInfo || {};
    const userType = Number(memberInfo.user_type || 1);
    console.log(memberInfo)

    if (userType > 4) {
      // 🌟 店长/管理员去专业的管理台
      wx.navigateTo({
        url: '/pages/my/offline_manage' // 需在 app.json 新建此页面
      });
    } else {
      // 🌟 普通用户去极简的个人资产页
      wx.navigateTo({
        url: '/pages/my/offline_project'
      });
    }
  },

});
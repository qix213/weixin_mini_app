const app = getApp();

Page({
  data: {
    currentLevel: 1,
    currentLevelName: '蓝朋友0星',
    selectedLevelId: null, // 当前选中的升级目标ID
    selectedAmount: 0,
    
    // 全部的升级配置（前端写死展示用，安全性由后端兜底）
    allLevels: [
      { id: 2, name: '蓝朋友1星', price: 980, desc: '解锁基础分销与专属护肤指导' },
      { id: 3, name: '蓝朋友2星', price: 3980, desc: '解锁高级分销与线下沙龙名额' },
      { id: 4, name: '蓝朋友3星', price: 9800, desc: '尊享区域代理权与全系产品折扣' },
      { id: 5, name: 'Ta创+', price: 39800, desc: '顶级合伙人，共享品牌城市分红' }
    ],
    availableLevels: [] // 实际可升级的列表
  },

  onLoad() {
    this.initLevelData();
  },

  initLevelData() {
    const memberInfo = app.globalData.memberInfo || {};
    const cLevel = memberInfo.user_type || 1;
    
    // 过滤出比当前等级高的选项
    const available = this.data.allLevels.filter(item => item.id > cLevel);
    
    this.setData({
      currentLevel: cLevel,
      currentLevelName: memberInfo.user_type_text || '蓝朋友0星',
      availableLevels: available,
      // 默认选中第一个可升级的
      selectedLevelId: available.length > 0 ? available[0].id : null,
      selectedAmount: available.length > 0 ? available[0].price : 0
    });
  },

  selectLevel(e) {
    const { id, price } = e.currentTarget.dataset;
    this.setData({ selectedLevelId: id, selectedAmount: price });
  },

  // 提交升级订单
  submitUpgrade() {
    if (!this.data.selectedLevelId) {
      return wx.showToast({ title: '请选择升级等级', icon: 'none' });
    }

    const token = wx.getStorageSync('accessToken');
    wx.showLoading({ title: '创建订单中...' });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/member/upgrade_order/`,
      method: 'POST',
      header: { 'Authorization': `Bearer ${token}`, 'content-type': 'application/json' },
      data: { target_level: this.data.selectedLevelId },
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          const orderId = res.data.data.order_id; // 后端返回的订单号
          const amount = res.data.data.amount;
          
          // 跳转到公共支付页
          wx.navigateTo({
            url: `/pages/pay/pay?orderId=${orderId}&actualAmount=${amount}&typeName=会员升级订单`
          });
        } else {
          wx.showToast({ title: res.data.msg || '创建失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  }
});
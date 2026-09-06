const app = getApp();

Page({
  data: {
    currentLevel: 1,
    currentLevelName: '蓝朋友',
    selectedLevelId: null, // 当前选中的升级目标ID
    selectedAmount: 0,
    
    // 🌟 核心修改：全新 6 个升级目标（对应 1星 到 Ta创+）
    allLevels: [
      { id: 2, name: '蓝朋友1星', price: 980, desc: '解锁会员专享价与100元代金券' },
      { id: 3, name: '蓝朋友2星', price: 1980, desc: '解锁300元代金券及专业护肤私教认证资格' },
      { id: 4, name: '蓝朋友3星', price: 3980, desc: '解锁家居品10%消费补贴与千元代金券' },
      { id: 5, name: '蓝朋友4星', price: 9800, desc: '解锁全产品15%消费补贴与胶原mini核销权益' },
      { id: 6, name: '蓝朋友5星', price: 39800, desc: '尊享实物大礼包与全产品15%补贴' },
      { id: 7, name: 'Ta创+', price: 98000, desc: '高端俱乐部合伙人，尊享产品任选与门店全面扶持' }
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
      currentLevelName: memberInfo.user_type_text || '蓝朋友',
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
          const resData = res.data.data || res.data;
          
          const orderId = resData.order_id || resData.order_sn || '';
          const amount = resData.amount || resData.total_price || '0.00';
          
          // 🌟 直接拿你 data 里定义的 selectedLevelId
          const target_level = this.data.selectedLevelId; 
        
          if (!target_level) {
            wx.showToast({ title: '前端未获取到选中的等级数据', icon: 'none' });
            return;
          }
        
          // 带着真实的等级数据，硬核跳往收银台！
          wx.navigateTo({
            url: `/pages/pay/pay?scene=upgrade&orderId=${orderId}&actualAmount=${amount}&typeName=会员升级订单&target_level=${target_level}`
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
const app = getApp();
Page({
  data: {
    addressList: [],
    defaultAddressId: ''
  },

  onShow() {
    wx.nextTick(() => {
      this.getAddressList();
    });
  },

  getAddressList() {
    wx.showLoading({ title: '加载中...', mask: true });
    app.request({
      url: '/app01/address/list/',
      method: 'GET',
      header: { 'Cache-Control': 'no-cache' }
    }).then(res => {
      wx.hideLoading();
      const result = res.data || res;
      if (result.code === 200) {
        const addressList = result.data?.address_list || [];
        const normalizedList = addressList.map(item => ({
          id: item.id || '',
          name: item.name || '',
          phone: item.phone || '',
          province: item.province || '',
          city: item.city || '',
          district: item.district || '',
          detail: item.detail || item.detail_address || '',
          is_default: item.is_default || false,
        }));
        const defaultAddress = normalizedList.find(item => item.is_default === true);
        this.setData({
          addressList: normalizedList,
          defaultAddressId: defaultAddress?.id || ''
        });
      } else {
        wx.showToast({ title: result.msg || '加载地址失败', icon: 'none' });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('地址列表请求失败：', err);
    });
  },

  // ✅【终极修复】选择地址回传（完美传递所有字段，无null）
  selectAddress(e) {
    const { address } = e.currentTarget.dataset;
    console.log("🔍 [Debug] 当前选中的原始地址数据:", address); // 联调时先看一眼控制台
    
    const pages = getCurrentPages();
    if (pages.length < 2) {
      wx.navigateBack({ delta: 1 });
      return;
    }
  
    const prevPage = pages[pages.length - 2];
    const prevRoute = prevPage.route || '';
  
    if (prevRoute.includes('preOrder')) {
      // 🌟 1. 超强兼容性省市区抓取流：
      // 优先读 address，如果没有，就动态把分拆的 province、city、district/area 强行拼接起来
      let baseAddr = '';
      if (address.address) {
        baseAddr = address.address;
      } else {
        const p = address.province || '';
        const c = address.city || '';
        const d = address.district || address.area || ''; // 兼容区县可能叫 area 的情况
        baseAddr = `${p} ${c} ${d}`.trim();
      }

      // 🌟 2. 详细地址安全抓取
      const detailAddr = address.detail || address.detail_address || '';
      const fullAddress = `${baseAddr} ${detailAddr}`.replace(/\s+/g, ' ').trim();
      const senderName = address.name || '';
      const senderPhone = address.phone || address.mobile || '';
      console.log("✈️ 准备同步回上一页的终极地址:", fullAddress);

      // 🌟 3. 双向同步上一页的变量，激活重新校验
      prevPage.setData({
        sender: {
          name: senderName,
          mobile: senderPhone,
          fullAddress: fullAddress
        },
        "orderDetail.sender_name": senderName,
        "orderDetail.sender_phone": senderPhone,
        "orderDetail.sender_address": fullAddress
      }, () => {
        if (prevPage.jdPreCheck) prevPage.jdPreCheck();
      });
      wx.navigateBack({ delta: 1 });
      return;
    }
    // ================ 👆 原本代码结束 👆 ================

    // ================ 👇 2. 新增：给物流页面开的无污染通道 👇 ================
    if (prevRoute.includes('jdLogistics')) {
      // 动态获取是从哪个按钮跳过来的（寄还是收）
      const type = this.options.type || 'sender'; 
      
      // 直接调用物流页面里的接收函数
      if (prevPage.setAddressFromSelect) {
        prevPage.setAddressFromSelect(type, address);
      }
      wx.navigateBack({ delta: 1 });
      return;
    }
    // ====================================================================

    // 其他情况直接返回
    wx.navigateBack({ delta: 1 });
  },

  // 以下代码保持不变（setDefault/delete/edit/goToAdd）
  setDefaultAddress(e) {
    const { addressid } = e.currentTarget.dataset;
    if (addressid === this.data.defaultAddressId) return;
    wx.showLoading({ title: '设置中...', mask: true });
    app.request({
      url: `/app01/address/${addressid}/set_default/`,
      method: 'POST'
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;
      if (result.code == 200) {
        wx.showToast({ title: '设置默认地址成功', icon: 'success' });
        this.getAddressList();
      } else {
        wx.showToast({ title: result.msg || '设置失败', icon: 'none' });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('设置默认地址失败：', err);
    });
  },

  deleteAddress(e) {
    const { addressid } = e.currentTarget.dataset;
    wx.showModal({
      title: '提示',
      content: '确定要删除该地址吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '删除中...', mask: true });
          app.request({
            url: `/app01/address/${addressid}/`,
            method: 'DELETE'
          }).then(res => {
            wx.hideLoading();
            const result = res.data ? res.data : res;
            if (result.code == 200) {
              wx.showToast({ title: '删除成功', icon: 'success' });
              this.getAddressList();
            } else {
              wx.showToast({ title: result.msg || '删除失败', icon: 'none' });
            }
          }).catch(err => {
            wx.hideLoading();
            console.error('删除地址失败：', err);
          });
        }
      }
    });
  },

  goToAddAddress() {
    wx.navigateTo({ url: '/pages/addressAdd/addressAdd' });
  },

  goToEditAddress(e) {
    const { addressid } = e.currentTarget.dataset;
    wx.navigateTo({ url: `/pages/addressAdd/addressAdd?addressId=${addressid}` });
  },
});
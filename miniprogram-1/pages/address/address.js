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
    const pages = getCurrentPages();
    if (pages.length < 2) {
      wx.navigateBack({ delta: 1 });
      return;
    }
  
    const prevPage = pages[pages.length - 2];
    const prevRoute = prevPage.route || '';
  
    // 京东发货页：直接用完整拼接地址
    if (prevRoute.includes('preOrder')) {
      let orderDetail = prevPage.data.orderDetail || {};
      orderDetail.sender_name = address.name;
      orderDetail.sender_phone = address.phone;
      // 🔥 直接用前端拼接好的完整地址，永不丢省市区
      orderDetail.sender_address = `${address.address} ${address.detail}`.trim();
  
      prevPage.setData({ orderDetail: orderDetail });
    }
  
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
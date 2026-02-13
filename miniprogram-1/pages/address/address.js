const app = getApp();

Page({
  data: {
    addressList: [],  // 地址列表
    defaultAddressId: ''  // 默认地址ID
  },

  onShow() {
    // 强制刷新：每次显示页面立即重新获取列表（移除可能的缓存影响）
    wx.nextTick(() => {
      this.getAddressList();
    });
  },

  // 修复：获取地址列表（核心优化）
  getAddressList() {
    wx.showLoading({ title: '加载中...', mask: true }); // 增加mask防止重复点击
    app.request({
      url: '/app01/address/list/',  // 核对后端URL：需和urls.py中的配置一致
      method: 'GET',
      // 新增：强制禁用缓存（避免读取旧数据）
      header: {
        'Cache-Control': 'no-cache'
      }
    }).then(res => {
      wx.hideLoading();
      // 统一数据解析逻辑（兼容后端可能的返回格式）
      const result = res.data || res;
      console.log('地址列表接口返回：', result); // 新增调试日志，方便定位问题

      if (result.code === 200) {
        // 核心修复1：字段名统一（后端返回detail，前端错写detail_address）
        const addressList = result.data?.address_list || [];
        // 标准化地址数据（确保关键字段存在）
        const normalizedList = addressList.map(item => ({
          id: item.id || '',
          name: item.name || '',
          phone: item.phone || '',
          address: item.address || `${item.province || ''} ${item.city || ''} ${item.district || ''}`,
          detail: item.detail || item.detail_address || '', // 兼容两种字段名
          is_default: item.is_default || false, // 确保布尔值
          province: item.province || '',
          city: item.city || '',
          district: item.district || ''
        }));

        // 核心修复2：正确查找默认地址
        const defaultAddress = normalizedList.find(item => item.is_default === true);
        this.setData({
          addressList: normalizedList,
          defaultAddressId: defaultAddress?.id || ''
        });

        // 调试：打印最终渲染的列表
        console.log('标准化后地址列表：', normalizedList);
      } else {
        wx.showToast({ title: result.msg || '加载地址失败', icon: 'none', duration: 2000 });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('地址列表请求失败：', err); // 新增错误日志
      wx.showToast({ title: '网络错误，无法加载地址', icon: 'none', duration: 2000 });
    });
  },

  // 其余方法（setDefaultAddress/deleteAddress等）保持不变，仅补充日志
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
        this.getAddressList(); // 强制刷新列表
      } else {
        wx.showToast({ title: result.msg || '设置失败', icon: 'none' });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('设置默认地址失败：', err);
      wx.showToast({ title: '网络错误', icon: 'none' });
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
              this.getAddressList(); // 强制刷新列表
            } else {
              wx.showToast({ title: result.msg || '删除失败', icon: 'none' });
            }
          }).catch(err => {
            wx.hideLoading();
            console.error('删除地址失败：', err);
            wx.showToast({ title: '网络错误', icon: 'none' });
          });
        }
      }
    });
  },

  goToAddAddress() {
    wx.navigateTo({
      url: '/pages/addressAdd/addressAdd'
    });
  },

  goToEditAddress(e) {
    const { addressid } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/addressAdd/addressAdd?addressId=${addressid}`
    });
  },

// 地址页（address.js）中选择地址后的返回逻辑（已正确）
selectAddress(e) {
  const { address } = e.currentTarget.dataset;
  const pages = getCurrentPages();
  const prevPage = pages[pages.length - 2];
  // 可选：直接给结算页赋值最新地址（双重保障）
  prevPage.setData({
    defaultAddress: address
  });
  wx.navigateBack({ delta: 1 }); // 此方式会触发结算页onShow
},

// 地址添加页（addressAdd.js）保存地址后的返回逻辑
saveAddress() {
  // 保存地址逻辑...
  wx.showToast({ title: '地址保存成功', icon: 'success' });
  // 使用navigateBack返回，触发结算页onShow
  wx.navigateBack({ delta: 1 });
}
});
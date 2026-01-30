const app = getApp();

Page({
  data: {
    region: ['北京市', '北京市', '东城区'],
    addressId: '',
    formData: {
      name: '',
      phone: '',
      detail: '' // 统一字段名为detail，和后端保持一致
    }
  },

  onLoad(options) {
    if (options.addressId) {
      this.setData({ addressId: options.addressId });
      this.getAddressDetail(options.addressId);
    }
  },

  // 修复：获取地址详情（字段名统一）
  getAddressDetail(addressId) {
    wx.showLoading({ title: '加载中...', mask: true });
    app.request({
      url: `/app01/address/${addressId}/`,
      method: 'GET'
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;
      console.log('地址详情返回：', result); // 调试日志
      if (result.code == 200) {
        const address = result.data;
        // 修复：拆分省市区（兼容后端返回的address字段）
        let region = ['北京市', '北京市', '东城区'];
        if (address.address) {
          region = address.address.split(/\s+/);
          while (region.length < 3) {
            region.push(region[region.length - 1] || '东城区');
          }
        } else if (address.province && address.city && address.district) {
          // 兼容后端返回的省市区单独字段
          region = [address.province, address.city, address.district];
        }
        // 核心修复：字段名统一（detail_address → detail）
        this.setData({
          region,
          formData: {
            name: address.name || '',
            phone: address.phone || '',
            detail: address.detail || address.detail_address || '' // 兼容两种字段名
          }
        });
      } else {
        wx.showToast({ title: result.msg || '加载地址失败', icon: 'none' });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('获取地址详情失败：', err);
      wx.showToast({ title: '网络错误', icon: 'none' });
    });
  },

  bindRegionChange(e) {
    this.setData({ region: e.detail.value });
  },

  onInputChange(e) {
    const { name } = e.currentTarget.dataset;
    const { formData } = this.data;
    formData[name] = e.detail.value.trim();
    this.setData({ formData });
  },

  // 修复：保存地址（字段名统一+返回逻辑优化）
  saveAddress(e) {
    const val = this.data.addressId ? this.data.formData : e.detail.value;
    const { region, addressId } = this.data;

    // 基础校验
    if (!val.name || !val.phone || !val.detail) {
      wx.showToast({ title: '请填写完整', icon: 'none' });
      return;
    }
    if (!/^1[3-9]\d{9}$/.test(val.phone)) {
      wx.showToast({ title: '手机号格式错误', icon: 'none' });
      return;
    }

    // 核心修复：字段名统一（detail_address → detail，和后端保持一致）
    const postData = {
      name: val.name,
      phone: val.phone,
      address: region.join(' '),
      detail: val.detail, // 原detail_address改为detail
      is_default: false, // 显式传递默认值，避免后端报错
      // 补充省市区字段，方便后端存储
    };

    wx.showLoading({ title: '保存中...', mask: true });
    const requestConfig = {
      url: addressId ? `/app01/address/${addressId}/` : '/app01/address/add/',
      method: addressId ? 'PUT' : 'POST',
      data: postData
    };

    app.request(requestConfig).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;
      if (result.code == 200) {
        wx.showToast({
          title: addressId ? '修改成功' : '添加成功',
          icon: 'success',
          duration: 1000 // 缩短延迟，加快返回列表页
        });
        // 修复：立即返回列表页，且取消setTimeout（避免延迟导致刷新不及时）
        wx.navigateBack({ delta: 1 });
      } else {
        wx.showToast({ title: result.msg || '保存失败', icon: 'none' });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('保存地址失败：', err);
      wx.showToast({ title: '网络请求失败', icon: 'none' });
    });
  }
});
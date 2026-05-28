const app = getApp();

Page({
  data: {
    smartText: '', // 智能解析绑定的文本
    region: [],
    addressId: '',
    isSaving: false,
    is_default: false,
    formData: {
      name: '',
      phone: '',
      detail: '',
      province: '',
      city: '',
      district: ''
    }
  },

  onLoad(options) {
    if (options.addressId) {
      this.setData({ addressId: options.addressId });
      this.getAddressDetail(options.addressId);
    }
  },

  // 清空智能解析文本
  clearSmartText() {
    this.setData({ smartText: '' });
  },

  // 🚀 核心：前端启发式智能地址解析算法
  smartParse() {
    let text = this.data.smartText.trim();
    if (!text) return wx.showToast({ title: '请粘贴地址文本', icon: 'none' });

    wx.showLoading({ title: '智能解析中...' });

    // 1. 提取手机号 (支持国内常见的11位手机号)
    const phoneReg = /(1[3-9]\d{9})/g;
    const phoneMatch = text.match(phoneReg);
    let phone = phoneMatch ? phoneMatch[0] : '';
    if (phone) {
      text = text.replace(phone, ' '); // 挖去手机号，替换为空格
    }

    // 2. 剥离可能存在的邮编 (连续6位数字)
    const zipReg = /\b\d{6}\b/g;
    const zipMatch = text.match(zipReg);
    if (zipMatch) text = text.replace(zipMatch[0], ' ');

    // 3. 提取姓名 (根据空格或标点符号分段，寻找2-4个字的非地址段)
    const parts = text.split(/[\s,，。、\n\t]+/);
    let name = '';
    let addressParts = [];
    const addressKeywords = /省|市|区|县|盟|州|镇|街|路|道|村|号|栋|楼|单元|室/;

    parts.forEach(part => {
      if (!part) return;
      // 如果还没找到名字，长度2-4，且不含常见地址后缀，大概率是名字
      if (!name && part.length >= 2 && part.length <= 4 && !addressKeywords.test(part)) {
        name = part;
      } else {
        addressParts.push(part);
      }
    });

    // 如果上面规则没命中，且第一段较短，直接拿第一段当名字
    if (!name && addressParts.length > 0 && addressParts[0].length <= 5) {
      name = addressParts.shift();
    }

    // 4. 解析省市区 (粗略切分)
    let addressStr = addressParts.join('');
    let province = '', city = '', district = '';
    
    // 匹配省
    const provReg = /(.+?(省|自治区|北京市|天津市|上海市|重庆市|特别行政区))/;
    const provMatch = addressStr.match(provReg);
    if (provMatch) {
      province = provMatch[1];
      addressStr = addressStr.replace(province, '');
    }

    // 匹配市
    const cityReg = /(.+?(市|自治州|地区|盟))/;
    const cityMatch = addressStr.match(cityReg);
    if (cityMatch) {
      city = cityMatch[1];
      addressStr = addressStr.replace(city, '');
    }

    // 匹配区/县
    const distReg = /(.+?(区|县|旗|海域|岛))/;
    const distMatch = addressStr.match(distReg);
    if (distMatch) {
      district = distMatch[1];
      addressStr = addressStr.replace(district, '');
    }

    // 组装回显数据
    let region = [];
    if (province) region.push(province);
    if (city) region.push(city);
    if (district) region.push(district);

    this.setData({
      'formData.name': name,
      'formData.phone': phone,
      'formData.detail': addressStr.trim(),
      'formData.province': province,
      'formData.city': city,
      'formData.district': district,
      region: region.length > 0 ? region : this.data.region,
      smartText: '' // 解析完自动清空输入框
    });

    wx.hideLoading();
    wx.showToast({ title: '解析成功', icon: 'success' });
  },

  // 常规数据绑定
  onInputChange(e) {
    const { name } = e.currentTarget.dataset;
    this.setData({ [`formData.${name}`]: e.detail.value.trim() });
  },

  bindRegionChange(e) {
    const region = e.detail.value;
    this.setData({
      region: region,
      'formData.province': region[0] || '',
      'formData.city': region[1] || '',
      'formData.district': region[2] || ''
    });
  },

  onDefaultChange(e) {
    this.setData({ is_default: e.detail.value });
  },

  // 获取详情回显代码（保留你的原逻辑）
  getAddressDetail(addressId) {
    wx.showLoading({ title: '加载中...' });
    app.request({
      url: `/app01/address/${addressId}/`,
      method: 'GET'
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;
      if (result.code == 200) {
        const address = result.data;
        let region = ['北京市', '北京市', '东城区'];
        if (address.address) {
          region = address.address.split(/\s+/);
          while (region.length < 3) region.push(region[region.length - 1] || '东城区');
        } else if (address.province && address.city && address.district) {
          region = [address.province, address.city, address.district];
        }
        this.setData({
          region,
          is_default: address.is_default || false,
          formData: {
            name: address.name || '',
            phone: address.phone || '',
            detail: address.detail || address.detail_address || '',
            province: address.province || region[0] || '',
            city: address.city || region[1] || '',
            district: address.district || region[2] || ''
          }
        });
      }
    }).catch(err => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  // 提交保存逻辑（保留你完善好的 API 逻辑）
  saveAddress() {
    if (this.data.isSaving) return;
    this.setData({ isSaving: true });

    const { formData, is_default, region } = this.data;
    const { name, phone, detail, province, city, district } = formData;
    const address = region.join(' ');

    if (!name || !phone || !detail || !province || !city || !district) {
      wx.showToast({ title: '请填写完整信息', icon: 'none' });
      this.setData({ isSaving: false });
      return; 
    }

    wx.showLoading({ title: '保存中...', mask: true });
    const url = this.data.addressId ? `/app01/address/${this.data.addressId}/` : '/app01/address/add/';
    const method = this.data.addressId ? 'PUT' : 'POST';

    app.request({
      url: url,
      method: method,
      data: { name, phone, address, detail, is_default, province, city, district }
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;
      if (result.code === 200 || result.code === 201) {
        wx.showToast({ title: '保存成功', icon: 'success', duration: 1500 });
        setTimeout(() => {
          const pages = getCurrentPages();
          if (pages.length >= 2) {
            const prevPage = pages[pages.length - 2];
            if (prevPage.route.includes('address/address')) {
              wx.navigateBack({ delta: 1 });
            } else {
              wx.redirectTo({ url: '/pages/address/address' });
            }
          } else {
            wx.redirectTo({ url: '/pages/address/address' });
          }
        }, 1500);
      } else {
        wx.showToast({ title: result.msg || '保存失败', icon: 'none' });
        this.setData({ isSaving: false });
      }
    }).catch(err => {
      wx.hideLoading();
      wx.showToast({ title: '网络异常', icon: 'none' });
      this.setData({ isSaving: false });
    });
  }
});
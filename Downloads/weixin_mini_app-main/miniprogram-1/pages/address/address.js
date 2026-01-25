const app = getApp();

Page({
  data: {
    region: ['北京市', '北京市', '东城区'],
  },

  bindRegionChange: function (e) {
    this.setData({ region: e.detail.value });
  },

  saveAddress: function (e) {
    const val = e.detail.value;
    const { region } = this.data;

    // 1. 数据校验
    if (!val.name || !val.phone || !val.detail) {
      wx.showToast({ title: '请填写完整', icon: 'none' });
      return;
    }

    // 2. 构造与 Django Model 匹配的字段
    const postData = {
      name: val.name,
      phone: val.phone,
      address: region.join(''),   // 后端模型字段：address
      detail_address: val.detail  // 后端模型字段：detail_address
    };

    wx.showLoading({ title: '保存中...' });

    app.request({
      url: '/app01/address/add/',
      method: 'POST',
      data: postData
    }).then(res => {
      wx.hideLoading();
      
      // --- 🔍 深度调试开始 ---
      console.log('--- 后端原始返回对象 ---', res);
      
      /**
       * 兼容性处理：
       * 有些封装返回 res，数据在 res.data
       * 有些封装直接返回了 res.data
       */
      const result = res.data ? res.data : res;
      console.log('--- 解析后的数据内容 ---', result);
      // --- 🔍 深度调试结束 ---

      // 判断后端返回的 code
      // 注意：即便后端返回 200，也要确认是数字还是字符串 '200'
      if (result.code == 200 || result.code == '200') {
        wx.showToast({
          title: '保存成功',
          icon: 'success',
          duration: 1500,
          success: () => {
            // 成功后延迟返回结算页
            setTimeout(() => {
              wx.navigateBack({ delta: 1 });
            }, 1500);
          }
        });
      } else {
        // 如果数据库进了数据但显示失败，说明逻辑掉到了这里
        console.error('逻辑判定失败，后端返回的 code 是：', result.code);
        wx.showToast({
          title: result.msg || '数据异常',
          icon: 'none'
        });
      }
    }).catch(err => {
      wx.hideLoading();
      console.error('请求彻底失败：', err);
      wx.showToast({ title: '网络请求失败', icon: 'none' });
    });
  }
});
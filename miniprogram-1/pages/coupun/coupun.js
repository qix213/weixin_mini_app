// ========== 第一步：提取为独立常量，不依赖Page的data ==========
const COUPON_STATUS_MAP = {
  all: '全部',
  unused: '未使用',
  used: '已使用',
  expired: '已过期'
};

Page({
  data: {
    // 优惠券列表（核心数据）
    couponList: [],
    // 空状态提示
    emptyTip: '暂无优惠券',
    // 加载状态
    loading: true,
    // 优惠券状态筛选（默认全部）
    activeStatus: 'all', // all:全部, unused:未使用, used:已使用, expired:已过期
    // 保留原statusMap（兼容其他逻辑），但格式化时用独立常量
    statusMap: COUPON_STATUS_MAP
  },

  onShow() {
    // 页面每次显示时重新请求数据（保证数据最新）
    this.getCouponList();
  },

  // ========== 核心方法：请求优惠券列表 ==========
  getCouponList() {
    const app = getApp();
    // 1. 登录校验（未登录跳转登录页）
    if (!app.globalData.isLogin) {
      wx.navigateTo({
        url: '/pages/login/login?redirect=' + encodeURIComponent('/pages/coupon/coupon')
      });
      return;
    }

    // 2. 发起请求
    this.setData({ loading: true });
    wx.request({
      url: `${app.globalData.baseUrl}/app01/member/coupons/`, // 后端优惠券列表接口
      method: 'GET',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${app.globalData.accessToken}` // 带token认证
      },
      success: (res) => {
        this.setData({ loading: false });
        // 调试日志：打印后端返回的完整数据，确认结构
        console.log('后端返回数据：', res.data);
        
        if (res.data.code === 200) {
          // 正确获取优惠券数组 + 类型校验
          const rawCouponList = Array.isArray(res.data.data?.coupons) ? res.data.data.coupons : [];
          // 格式化优惠券数据
          const couponList = this.formatCouponData(rawCouponList);
          this.setData({
            couponList: couponList,
            emptyTip: couponList.length === 0 ? '暂无优惠券' : ''
          });
        } else {
          wx.showToast({ title: res.data.msg || '加载优惠券失败', icon: 'none' });
          this.setData({ emptyTip: '加载失败，请重试' });
        }
      },
      fail: (err) => {
        this.setData({ loading: false, emptyTip: '网络异常，请重试' });
        console.error('优惠券列表请求失败：', err);
      }
    });
  },

  // ========== 辅助方法：格式化优惠券数据（彻底脱离this依赖） ==========
  formatCouponData(couponList) {
    if (!Array.isArray(couponList)) return [];

    const now = new Date().getTime();
    return couponList.map(coupon => {
      if (!coupon || typeof coupon !== 'object') return {};

      // 1. 修正状态计算：优先使用后端返回的is_expired，字段匹配is_used
      let status = 'unused';
      if (coupon.is_used) { // 后端返回is_used（是否已使用）
        status = 'used';
      } else if (coupon.is_expired) { // 后端返回is_expired（是否已过期）
        status = 'expired';
      }

      // 2. 修正有效期字段：用start_time/end_time替代create_time/expire_time
      const startDate = coupon.start_time ? this.formatDate(coupon.start_time) : '';
      const endDate = coupon.end_time ? this.formatDate(coupon.end_time) : '';
      const validPeriod = `${startDate} 至 ${endDate}`;

      return {
        ...coupon,
        status: status,
        statusText: COUPON_STATUS_MAP[status] || '未知状态',
        validPeriod: validPeriod,
        // 兼容前端渲染：新增amount/name字段（映射后端的money/title）
        amount: coupon.money,
        name: coupon.title
      };
    });
  },

  // 日期格式化（YYYY-MM-DD）
  formatDate(dateStr) {
    if (!dateStr || typeof dateStr !== 'string') return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '';
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  // ========== 交互方法：切换优惠券状态筛选 ==========
  switchStatus(e) {
    const status = e.currentTarget.dataset.status;
    this.setData({ activeStatus: status });
  },

  // ========== 交互方法：优惠券点击事件 ==========
  onCouponTap(e) {
    const coupon = e.currentTarget.dataset.coupon;
    if (!coupon) return; // 空值校验

    // 仍可使用常量COUPON_STATUS_MAP，或用this.data.statusMap
    const statusText = COUPON_STATUS_MAP[coupon.status] || '未知状态';
    if (coupon.status === 'unused') {
      wx.showToast({ title: '暂未开放使用功能', icon: 'none' });
    } else if (coupon.status === 'used') {
      wx.showToast({ title: `该优惠券已${statusText}`, icon: 'none' });
    } else if (coupon.status === 'expired') {
      wx.showToast({ title: `该优惠券已${statusText}`, icon: 'none' });
    } else {
      wx.showToast({ title: '优惠券状态未知', icon: 'none' });
    }
  },

  // 重试加载优惠券
  retryLoad() {
    this.getCouponList();
  }
});
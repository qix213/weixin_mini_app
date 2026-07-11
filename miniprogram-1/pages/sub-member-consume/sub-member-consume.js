const app = getApp();
Page({
  data: {
    loading: true,
    consumeList: [],
    memberList: [],
    currentMemberId: '',
    currentMemberInfo: {},
    currentLevel: 0,
    totalAllConsume: '0.00',
    totalCommission: '0.00', // 可提现余额
    frozenCommission: '0.00', // 冻结中余额
    showWithdrawModal: false, // 控制弹窗显示
    withdrawAmount: '', // 用户输入的提现金额
    showCommissionList: false,
    showConsumeList: false,
    withdrawStatus: -1, // -1:无记录/可提现, 0:审核中, 1:待确认, 2:已成功
    packageInfo: '', // 后端传来的微信收款包
    mchId: '1747481772', // 替换为你的微信支付商户号
    appId: 'wx8c245b48cd8672b3' // 替换为你的小程序APPID    
  },

  onLoad(options) {
    // 页面加载时弹出一个转圈提示
    wx.showLoading({
      title: '加载中...'
    });
    // 🌟 1. 拉取钱包余额
    this.fetchWalletData();
    // 🌟 2. 补上拉取下级消费列表的方法！
    this.getSubMemberConsumeList();
    // 每次进入页面，拉取最新状态
    this.fetchWithdrawStatus();

  },

  onShow() {
    // 每次回到页面都刷新一下余额，防止数据不一致
    this.fetchWalletData();
    // 🌟 修改点 2：每次回到页面，也必须刷新提现按钮状态！
    this.fetchWithdrawStatus();
  },
  // 🌟 新增：切换佣金明细折叠状态
  toggleCommissionList() {
    this.setData({
      showCommissionList: !this.data.showCommissionList
    });
  },

  // 🌟 新增：切换消费明细折叠状态
  toggleConsumeList() {
    this.setData({
      showConsumeList: !this.data.showConsumeList
    });
  },
  // 统一下发请求
  fetchWalletData() {
    const app = getApp();
    app.request({
      url: '/app01/user/wallet/',
      method: 'GET'
    }).then(res => {
      // 🌟 核心：只要接口返回了，就立刻关掉转圈！
      wx.hideLoading();

      const result = res.data ? res.data : res;
      if (result.code === 200) {
        this.setData({
          totalCommission: parseFloat(result.data.withdrawable_balance || 0).toFixed(2),
          frozenCommission: parseFloat(result.data.frozen_balance || 0).toFixed(2),
          walletDetails: result.data.details || [] // 🌟 确保这行存在，WXML才能渲染出列表
        });
      }
    }).catch(err => {
      // 🌟 核心：接口报错了也要关掉转圈，不然页面就卡死了！
      wx.hideLoading();
      console.error("获取资产失败", err);
    });
  },

// 1. 确保在获取状态时，把单号 out_bill_no 也存进 data 变量里
fetchWithdrawStatus() {
  const app = getApp();
  app.request({
    url: '/app01/withdraw/status/', 
    method: 'GET'
  }).then(res => {
    const result = res.data ? res.data : res;
    if (result.status !== undefined) {
      this.setData({
        withdrawStatus: result.status,
        packageInfo: result.package_info || '',
        outBillNo: result.out_bill_no || '' // 🌟 核心修复：必须把单号存起来！
      });
    }
  }).catch(err => {
    console.error("获取提现状态失败", err);
  });
},

// 2. 确认收款逻辑
handleConfirmReceipt() {
  const that = this;
  const packageStr = this.data.packageInfo;
  const outBillNo = this.data.outBillNo; // 🌟 拿到刚才存的单号

  if (!packageStr) {
    wx.showToast({ title: '收款信息有误，请联系客服', icon: 'none' });
    return;
  }
  if (!outBillNo) {
    wx.showToast({ title: '缺少内部单号，请重新进入页面', icon: 'none' });
    return;
  }

  wx.requestMerchantTransfer({
    mchId: this.data.mchId,
    appId: this.data.appId,
    package: packageStr,
    success(res) {
      console.log('微信收银台返回收款成功', res);
      
      // 弹出加载圈，防止用户多次点击
      wx.showLoading({ title: '同步状态中...', mask: true });

      // 🌟 向 Django 发送同步请求
      const app = getApp();
      app.request({
        url: '/app01/withdraw/confirm_success/', 
        method: 'POST',
        data: {
          out_bill_no: outBillNo // 🌟 此时单号一定有值了！
        }
      }).then(backendRes => {
        wx.hideLoading();
        const result = backendRes.data ? backendRes.data : backendRes;
        
        if (result.code === 200) {
          wx.showToast({ title: '收款成功！', icon: 'success', duration: 2000 });
          
          // 🌟 状态强行转为 2，按钮瞬间变回“提现”
          that.setData({ withdrawStatus: 2 }); 
          
          // 重新拉取最新的钱包余额和单据状态
          that.fetchWalletData();       
          that.fetchWithdrawStatus();   
        } else {
          wx.showToast({ title: result.msg || '状态同步失败', icon: 'none' });
        }
      }).catch(err => {
        wx.hideLoading();
        console.error("同步后端状态网络异常", err);
        wx.showToast({ title: '网络异常，请重试', icon: 'none' });
      });
    },
    fail(err) {
      console.log('收款失败或取消', err);
      if (err.errMsg.indexOf('cancel') === -1) {
        wx.showToast({ title: '拉起收银台失败', icon: 'none' });
      }
    }
  });
},

  handleWithdraw() {
    if (parseFloat(this.data.totalCommission) < 0.1) {
      return wx.showToast({
        title: '余额满 0.1 元方可提现',
        icon: 'none'
      });
    }
    this.setData({
      showWithdrawModal: true,
      withdrawAmount: '' // 打开时清空输入框
    });
  },

  // 🌟 3. 关闭弹窗
  closeWithdrawModal() {
    this.setData({
      showWithdrawModal: false
    });
  },

  // 🌟 4. 监听输入金额
  onWithdrawInput(e) {
    let val = e.detail.value;
    // 限制只能输入两位小数
    if (val.indexOf('.') !== -1) {
      let arr = val.split('.');
      if (arr[1].length > 2) {
        val = arr[0] + '.' + arr[1].substr(0, 2);
      }
    }
    this.setData({
      withdrawAmount: val
    });
  },
  // 点击最低提现
  onWithdrawMin() {
    this.setData({
      withdrawAmount: '0.10'
    });
  },
  // 🌟 5. 点击全部提现
  onWithdrawMax() {
    this.setData({
      withdrawAmount: this.data.totalCommission
    });
  },

  // 🌟 6. 点击确认提现，提交给后端
  submitWithdraw() {
    const amount = parseFloat(this.data.withdrawAmount);
    const maxAmount = parseFloat(this.data.totalCommission);

    if (isNaN(amount) || amount <= 0) {
      return wx.showToast({
        title: '请输入提现金额',
        icon: 'none'
      });
    }
    if (amount < 0.1) {
      return wx.showToast({
        title: '单笔提现最低 0.1 元',
        icon: 'none'
      });
    }
    if (amount > maxAmount) {
      return wx.showToast({
        title: '输入金额超过可提现余额',
        icon: 'none'
      });
    }

    wx.showLoading({
      title: '提交申请中...',
      mask: true
    });

    app.request({
      url: '/app01/wallet/withdraw/', // 🌟 请确保后端你的提现接口是这个路由
      method: 'POST',
      data: {
        amount: amount
      }
    }).then(res => {
      wx.hideLoading();
      const result = res.data ? res.data : res;

      if (result.code === 200) {
        wx.showToast({
          title: '提现申请已提交',
          icon: 'success',
          duration: 2000
        });
        this.closeWithdrawModal();
        // 🌟 修改点 3：不仅要刷新余额，还要手动把状态改成 0 (待审核)，或者重新请求状态接口
        this.setData({
          withdrawStatus: 0 
        });
        this.fetchWalletData();
        this.fetchWithdrawStatus(); // 重新向后端确认最新状态
      } else {
        // 如果触发了本月只能提现一次的限制，后端会返回错误msg，直接弹出
        wx.showToast({
          title: result.msg || '提现失败',
          icon: 'none',
          duration: 3000
        });
      }
    }).catch(err => {
      wx.hideLoading();
      wx.showToast({
        title: '网络异常',
        icon: 'none'
      });
    });
  },
  // --- 以下为你原有的核心逻辑，保持不变 ---
  getSubMemberConsumeList() {
    const app = getApp();
    const header = app.getRequestHeader();

    wx.request({
      url: app.globalData.baseUrl + '/app01/member/sub-consume/',
      method: 'GET',
      header: header,
      data: {
        current_level: this.data.currentLevel
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({
          loading: false
        });
        if (res.data.code === 200) {
          const memberMap = {};
          let allConsumeList = [];
          let totalAllConsume = 0;

          res.data.data.forEach(memberItem => {
            const memberInfo = memberItem.member_info || {};
            const memberId = memberInfo.id || `sub_${Math.random().toString(36).substr(2, 8)}`;
            const memberNickname = memberInfo.nickname || '未知会员';
            const memberType = memberInfo.user_type || 0;
            const memberTypeName = memberInfo.user_type_name || '普通会员';
            const memberStarLevel = memberInfo.star_level || 0;
            const memberCode = memberInfo.member_id || '';

            const memberOrders = memberItem.orders || [];
            const formatOrders = memberOrders.map(order => {
              const orderSn = order.order_sn || '';
              const status = order.status || 0;
              const statusName = order.status_name || '未知状态';
              const orderPrice = this.safeToNumber(order.total_price || 0);
              const createTime = order.create_time || '';

              const goodsList = order.goods_list || [];
              const formatGoods = goodsList.map(good => {
                return {
                  goods_name: good.goods_name || '未知商品',
                  num: this.safeToNumber(good.num || 1),
                  price: this.safeToNumber(good.price || 0),
                  total_price: this.safeToNumber(good.total_price || 0)
                };
              });

              const formatOrder = {
                id: orderSn,
                order_sn: orderSn,
                status: status,
                status_name: statusName,
                total_price: orderPrice,
                create_time: this.formatDate(createTime),
                goods: formatGoods
              };
              allConsumeList.push(formatOrder);
              return formatOrder;
            });

            const memberTotalConsume = formatOrders.reduce((sum, item) => sum + item.total_price, 0);
            totalAllConsume += memberTotalConsume;

            memberMap[memberId] = {
              id: memberId,
              member_code: memberCode,
              nickname: memberNickname,
              level: memberType,
              level_name: memberTypeName,
              star_level: memberStarLevel,
              consumeRecords: formatOrders,
              totalConsume: memberTotalConsume.toFixed(2)
            };
          });

          const memberList = Object.values(memberMap);

          this.setData({
            consumeList: allConsumeList,
            memberList: memberList,
            currentMemberId: '',
            currentMemberInfo: {},
            totalAllConsume: totalAllConsume.toFixed(2)
          });
        } else {
          wx.showToast({
            title: res.data.msg || '获取记录失败',
            icon: 'none'
          });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        this.setData({
          loading: false
        });
        wx.showToast({
          title: '网络请求失败',
          icon: 'none'
        });
      }
    });
  },

  safeToNumber(value) {
    const num = parseFloat(value);
    return isNaN(num) ? 0 : num;
  },

  formatDate(dateStr) {
    if (!dateStr) return '未知时间';
    try {
      const date = new Date(dateStr);
      const year = date.getFullYear();
      const month = (date.getMonth() + 1).toString().padStart(2, '0');
      const day = date.getDate().toString().padStart(2, '0');
      const hour = date.getHours().toString().padStart(2, '0');
      const minute = date.getMinutes().toString().padStart(2, '0');
      return `${year}-${month}-${day} ${hour}:${minute}`;
    } catch (e) {
      return dateStr;
    }
  },

  onMemberClick(e) {
    const memberId = e.currentTarget.dataset.memberId;
    const {
      memberList
    } = this.data;

    if (this.data.currentMemberId === memberId) {
      this.setData({
        currentMemberId: '',
        currentMemberInfo: {}
      });
      return;
    }

    const currentMemberInfo = memberList.find(item => item.id === memberId) || {
      nickname: '未知会员',
      level_name: '普通会员',
      totalConsume: '0.00',
      consumeRecords: []
    };
    this.setData({
      currentMemberId: memberId,
      currentMemberInfo: currentMemberInfo
    });
  }
});
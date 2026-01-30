Page({
  data: {
    loading: true,
    consumeList: [], // 原始消费记录列表（备用）
    memberList: [], // 分组后的会员列表（真实会员信息）
    currentMemberId: '', // 当前选中的会员ID（默认空=全部收起）
    currentMemberInfo: {}, // 当前选中会员的完整信息
    currentLevel: 0, // 当前会员等级
    totalAllConsume: '0.00' // 新增：所有会员总消费
  },

  onLoad(options) {
    this.setData({
      currentLevel: options.currentLevel || 0
    });
    this.getSubMemberConsumeList();
  },

  // 核心：请求下级消费记录接口（适配新数据结构）
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
        this.setData({ loading: false });
        console.log("后端返回数据：", res.data); // 打印日志便于调试
        if (res.data.code === 200) {
          // 1. 初始化会员映射表（按真实会员ID分组）
          const memberMap = {};
          // 临时存储所有消费记录（备用）
          let allConsumeList = [];
          // 新增：累计所有会员总消费
          let totalAllConsume = 0;

          // 遍历后端返回的每个会员数据
          res.data.data.forEach(memberItem => {
            // 提取会员基础信息（兜底处理，避免字段缺失）
            const memberInfo = memberItem.member_info || {};
            const memberId = memberInfo.id || `sub_${Math.random().toString(36).substr(2, 8)}`; // 兜底ID
            const memberNickname = memberInfo.nickname || '未知会员';
            const memberType = memberInfo.user_type || 0;
            const memberTypeName = memberInfo.user_type_name || '普通会员';
            const memberStarLevel = memberInfo.star_level || 0;
            const memberCode = memberInfo.member_id || ''; // 会员编号

            // 处理该会员的所有订单
            const memberOrders = memberItem.orders || [];
            // 格式化该会员的订单列表
            const formatOrders = memberOrders.map(order => {
              // 订单基础信息格式化
              const orderSn = order.order_sn || '';
              const status = order.status || 0;
              const statusName = order.status_name || '未知状态';
              const orderPrice = this.safeToNumber(order.total_price || 0);
              const createTime = order.create_time || '';

              // 格式化商品列表
              const goodsList = order.goods_list || [];
              const formatGoods = goodsList.map(good => {
                return {
                  goods_name: good.goods_name || '未知商品',
                  num: this.safeToNumber(good.num || 1),
                  price: this.safeToNumber(good.price || 0),
                  total_price: this.safeToNumber(good.total_price || 0)
                };
              });

              // 组装单条订单数据
              const formatOrder = {
                id: orderSn, // 用订单编号作为唯一ID
                order_sn: orderSn,
                status: status,
                status_name: statusName,
                total_price: orderPrice,
                create_time: this.formatDate(createTime),
                goods: formatGoods // 前端WXML绑定的goods字段
              };
              // 加入全局消费记录列表
              allConsumeList.push(formatOrder);
              return formatOrder;
            });

            // 计算该会员的合计消费金额
            const memberTotalConsume = formatOrders.reduce((sum, item) => {
              return sum + item.total_price;
            }, 0);
            // 累加至总消费
            totalAllConsume += memberTotalConsume;

            // 将该会员加入映射表
            memberMap[memberId] = {
              id: memberId, // 会员ID（唯一）
              member_code: memberCode, // 会员编号
              nickname: memberNickname, // 真实昵称
              level: memberType, // 会员等级码
              level_name: memberTypeName, // 会员等级名称
              star_level: memberStarLevel, // 星级
              consumeRecords: formatOrders, // 该会员的订单列表
              totalConsume: memberTotalConsume.toFixed(2) // 单个会员合计（保留2位小数）
            };
          });

          // 2. 转换为会员列表（供前端渲染）
          const memberList = Object.values(memberMap);

          // 3. 核心修改：默认全部收起（不选中任何会员）
          let defaultMemberId = ''; // 空=默认收起
          let defaultMemberInfo = {};

          // 4. 更新页面数据（包含总消费）
          this.setData({
            consumeList: allConsumeList,
            memberList: memberList,
            currentMemberId: defaultMemberId,
            currentMemberInfo: defaultMemberInfo,
            totalAllConsume: totalAllConsume.toFixed(2) // 所有会员总消费（保留2位小数）
          });
        } else {
          wx.showToast({ title: res.data.msg || '获取消费记录失败', icon: 'none' });
        }
      },
      fail: (err) => {
        this.setData({ loading: false });
        console.error('请求失败：', err);
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // 安全转换数字（兜底NaN）
  safeToNumber(value) {
    const num = parseFloat(value);
    return isNaN(num) ? 0 : num;
  },

  // 格式化时间（兜底）
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

  // 点击会员切换选中状态（每个会员独立展开/收起）
  onMemberClick(e) {
    const memberId = e.currentTarget.dataset.memberId;
    const { memberList } = this.data;

    if (this.data.currentMemberId === memberId) {
      // 点击已选中的会员，收起
      this.setData({
        currentMemberId: '',
        currentMemberInfo: {}
      });
      return;
    }

    // 查找选中的会员信息
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
  },

  // 清空选中状态
  clearCurrentMember() {
    this.setData({
      currentMemberId: '',
      currentMemberInfo: {}
    });
  }
});
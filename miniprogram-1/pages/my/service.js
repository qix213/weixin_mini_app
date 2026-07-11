Page({
  data: {
    // 模拟客服电话，可从后端动态获取
    servicePhone: '400-123-4567', 
    // 常见问题列表
    faqList: [
      { 
        question: "如何升级我的会员等级？", 
        answer: "您可以在「我的」页面点击「去升级」，购买对应的等级卡即可完成会员升级，享受更多专属权益。", 
        isOpen: false 
      },
      { 
        question: "积分怎么获取和使用？", 
        answer: "每次消费均可获得积分奖励，积分可在积分商城兑换实物商品或抵扣线下项目服务次数。", 
        isOpen: false 
      },
      { 
        question: "购买的商品/服务可以退换吗？", 
        answer: "根据平台规定，未拆封的商品在7天内可联系客服申请无理由退货。线下服务类项目若未消费，支持随时退款。", 
        isOpen: false 
      },
      { 
        question: "如何查看我的线下预约记录？", 
        answer: "在「我的」页面点击「线下项目」，即可查看您所有已购买、已预约及已核销的项目记录。", 
        isOpen: false 
      }
    ]
  },

  onLoad() {
    // 可以在这里请求后端接口，动态获取客服企微链接、客服电话和最新 FAQ 列表
  },

  // 🌟 核心：拉起企业微信在线客服
// 🌟 核心：动态请求后端并拉起企业微信客服
openWechatService() {
  const app = getApp();
  const header = app.getRequestHeader(); // 复用你现有的请求头获取方法

  wx.showLoading({ title: '正在连接专属客服...', mask: true });

  // 1. 请求 Django 后端，获取最新的企微配置
  wx.request({
    url: `${app.globalData.baseUrl}/app01/api/config/kf/`,// ⚠️ 注意核对你 urls.py 中配置的真实路径
    method: 'GET',
    header: header,
    success: (res) => {
      if (res.data.code === 200) {
        const { corp_id, kf_url } = res.data.data;

        console.log(corp_id)
        console.log(kf_url)   

        // 2. 拿到参数后，调用微信底层接口拉起对话框
        wx.openCustomerServiceChat({
          extInfo: { url: kf_url },
          corpId: corp_id,
          success: (kfRes) => {
            wx.hideLoading();
            console.log('成功拉起企业微信客服', kfRes);
          },
          fail: (err) => {
            wx.hideLoading();
            console.error('拉起客服原生组件失败', err);
            wx.showToast({
              title: '客服通道繁忙，请稍后重试',
              icon: 'none',
              duration: 2000
            });
          }
        });
      } else {
        wx.hideLoading();
        wx.showToast({ 
          title: res.data.msg || '获取客服配置失败', 
          icon: 'none' 
        });
      }
    },
    fail: (err) => {
      wx.hideLoading();
      console.error('请求客服接口网络异常', err);
      wx.showToast({ 
        title: '网络异常，请检查连接', 
        icon: 'none' 
      });
    }
  });
},

  // 🌟 拨打客服电话
  callServicePhone() {
    wx.makePhoneCall({
      phoneNumber: this.data.servicePhone,
      success: () => {
        console.log('拨打电话成功');
      },
      fail: (err) => {
        console.error('拨打电话取消或失败', err);
      }
    });
  },

  // 控制 FAQ 折叠/展开
  toggleFaq(e) {
    const index = e.currentTarget.dataset.index;
    const faqList = this.data.faqList;
    
    // 切换当前点击项的展开状态
    faqList[index].isOpen = !faqList[index].isOpen;
    
    // （可选）实现手风琴效果：打开一个时，自动关闭其他的
    // faqList.forEach((item, i) => {
    //   if (i !== index) item.isOpen = false;
    // });

    this.setData({ faqList });
  }
});
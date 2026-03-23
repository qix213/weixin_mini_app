const app = getApp();
Page({
  data: {
    userId: '',
    messageList: [],
    inputText: '',
    isStreaming: false
  },

  onLoad() {
    this.initAIGreet();
    this.syncGlobalState();
  },

  syncGlobalState() {
    const memberInfo = app.globalData.memberInfo || {};
    const isLogin = app.globalData.isLogin || false;
    if (!isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1000);
      return;
    }
    this.setData({ userId: memberInfo.member_id || '1' });
  },

  initAIGreet() {
    this.setData({
      messageList: [{ role: 'assistant', content: '您好，我是AI蓝博士，请问有什么我可以帮助您的？' }]
    });
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  // 优化版：发送消息 + 思考中状态 + 打字机效果
  sendMessage() {
    const { inputText, userId, isStreaming } = this.data;
    if (isStreaming) return;
    if (!inputText.trim()) {
      wx.showToast({ title: '请输入问题', icon: 'none' });
      return;
    }

    // 1. 插入用户消息
    const userMsg = { role: 'user', content: inputText };
    // 🔥 核心：等待AI回复时，显示【思考中】
    const aiMsg = { role: 'assistant', content: '🧠 AI正在思考中...' };
    const newList = [...this.data.messageList, userMsg, aiMsg];
    
    this.setData({
      messageList: newList,
      inputText: '',
      isStreaming: true
    });

    const lastIndex = newList.length - 1;

    // 2. 请求后端
    wx.request({
      url: app.globalData.baseUrl + '/app01/ai/chat/',
      method: 'POST',
      header: {
        "Content-Type": "application/json",
        ...app.getRequestHeader()
      },
      data: { user_id: userId, question: inputText },
      
      success: (res) => {
        if (res.data.code === 200) {
          const fullText = res.data.data.answer;
          let currentText = '';
          let index = 0;

          // 打字机效果
          const timer = setInterval(() => {
            if (index < fullText.length) {
              currentText += fullText[index];
              this.setData({
                [`messageList[${lastIndex}].content`]: currentText
              });
              index++;
            } else {
              clearInterval(timer);
              this.setData({ isStreaming: false });
            }
          }, 40); // 加快打字速度
        }
      },
      
      fail: () => {
        wx.showToast({ title: 'AI请求失败', icon: 'none' });
        this.setData({ isStreaming: false });
      },
      
      complete: () => {
        this.setData({ isStreaming: false });
      }
    });
  }
});
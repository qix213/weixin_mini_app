const app = getApp();

Page({
  data: {
    userId: '',
    messageList: [],
    inputText: '',
    isStreaming: false,
    
    // 🔥 新增：当前选中的模型类型，默认为免费小模型
    modelType: 'lite' 
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
      messageList: [{ 
        role: 'assistant', 
        // 🔥 修改点：明确告知计费规则
        content: '您好，我是AI蓝博士。您可以免费使用【本地小模型】进行极速问答；或切换至【专业大模型】获取更深度的解答（专业版将消耗积分：1积分可抵扣10个Token）。',
        modelType: 'system' // 标记为系统欢迎语
      }]
    });
  },

  // 🔥 新增：切换模型的方法（供 WXML 里的按钮绑定使用）
  switchModel(e) {
    if (this.data.isStreaming) return; // AI 回答期间不允许切换
    const selectedType = e.currentTarget.dataset.type;
    this.setData({ modelType: selectedType });
    
    wx.showToast({
      title: selectedType === 'pro' ? '已切换至专业大模型' : '已切换至快速小模型',
      icon: 'none'
    });
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  // 优化版：发送消息 + 思考中状态 + 打字机效果 + 积分处理
  sendMessage() {
    const { inputText, userId, isStreaming, modelType } = this.data;
    if (isStreaming) return;
    if (!inputText.trim()) {
      wx.showToast({ title: '请输入问题', icon: 'none' });
      return;
    }

    // 1. 插入用户消息
    const userMsg = { role: 'user', content: inputText };
    // 2. 插入 AI 思考中占位符
    const aiMsg = { 
      role: 'assistant', 
      content: modelType === 'pro' ? '💎 专业大模型深度思考中...' : '⚡ 快速模型处理中...',
      modelType: modelType // 记录当前使用的是哪个模型，方便前端渲染尊贵标识
    };
    
    const newList = [...this.data.messageList, userMsg, aiMsg];
    
    this.setData({
      messageList: newList,
      inputText: '',
      isStreaming: true
    });

    const lastIndex = newList.length - 1;

    // 3. 请求后端
    wx.request({
      url: app.globalData.baseUrl + '/app01/ai/chat/',
      method: 'POST',
      header: {
        "Content-Type": "application/json",
        ...app.getRequestHeader()
      },
      // 🔥 核心修改：把当前选中的 modelType 传给后端
      data: { 
        user_id: userId, 
        question: userMsg.content,
        model_type: modelType 
      },
      
      success: (res) => {
        // ✅ 成功返回解答
        if (res.data.code === 200) {
          const { answer, points_deducted, remaining_points } = res.data.data;
          
          // 如果是 Pro 且扣除了积分，友善地提示一下用户
          if (modelType === 'pro' && points_deducted > 0) {
            wx.showToast({
              title: `深度解答完成，消耗 ${points_deducted} 积分`,
              icon: 'none',
              duration: 2000
            });
            // 同步更新本地全局积分状态（可选）
            if (app.globalData.memberInfo) {
              app.globalData.memberInfo.points = remaining_points;
            }
          }

          let currentText = '';
          let index = 0;

          // 打字机效果（先清空思考中状态）
          this.setData({ [`messageList[${lastIndex}].content`]: '' });

          const timer = setInterval(() => {
            if (index < answer.length) {
              currentText += answer[index];
              this.setData({
                [`messageList[${lastIndex}].content`]: currentText
              });
              index++;
            } else {
              clearInterval(timer);
              this.setData({ isStreaming: false });
            }
          }, 30); // 稍微加快一点点打字速度，体验更好
          
        } 
        // ❌ 积分不足被拦截
        else if (res.data.code === 403) {
          wx.showModal({
            title: '积分不足',
            content: res.data.msg,
            confirmText: '去赚积分',
            cancelText: '用免费版',
            success: (modalRes) => {
              if (modalRes.confirm) {
                // TODO: 跳转到签到或赚积分页面
                // wx.navigateTo({ url: '/pages/points/points' });
              } else {
                // 用户选择用免费版，自动帮他切回来
                this.setData({ modelType: 'lite' });
              }
            }
          });
          // 把刚才没成功的回答和提问撤回
          this.data.messageList.pop(); // 删掉思考中
          this.setData({ 
            messageList: this.data.messageList, 
            isStreaming: false,
            inputText: userMsg.content // 把用户刚才打的字退回到输入框里
          });
        } 
        // ⚠️ 其他服务器错误
        else {
          this.setData({
            [`messageList[${lastIndex}].content`]: res.data.msg || '大模型开小差了，请稍后再试',
            isStreaming: false
          });
        }
      },
      
      fail: () => {
        this.setData({
          [`messageList[${lastIndex}].content`]: '网络连接失败，请检查网络',
          isStreaming: false
        });
      }
    });
  }
});
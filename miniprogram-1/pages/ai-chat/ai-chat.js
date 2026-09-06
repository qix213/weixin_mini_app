const app = getApp();

Page({
  data: {
    scrollToView: '',
    messages: [
      { 
        id: 'init', 
        role: 'ai', 
        content: '您好呀，宝贝！✨ 我是您的专属护肤私教蓝博士。<br><br>第一步：请输入<strong style="color: rgb(125, 140, 115);">被测人姓名</strong>，并完成肤质问卷。', 
        isTyping: false 
      }
    ],
    scrollToId: '',
    currentStep: 0, 
    subjectName: '',
    showQuestionnaire: false,
    questionnaireData: [], 
    currentQIndex: 0,
    answers: {},
    isQuestionnaireSkipped: false 
  },

  onLoad() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      wx.showToast({ title: '请先登录/注册', icon: 'none', duration: 2000 });
      setTimeout(() => { wx.navigateTo({ url: '/pages/login/login' }); }, 1000);
      return; 
    }
    this.fetchQuestionnaire();
  },

  onShow() {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      wx.showToast({ title: '登录后即可体验智能专属护肤私教', icon: 'none' });
      setTimeout(() => { wx.switchTab({ url: '/pages/index/index' }); }, 1000);
    }
  },

  fetchQuestionnaire() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/api/get_questionnaire/`, 
      success: (res) => {
        let data = res.data;
        if (data && data.data) this.setData({ questionnaireData: data.data });
        else if (Array.isArray(data)) this.setData({ questionnaireData: data });
      }
    });
  },

  scrollToBottom() {
    if (this.scrollTimer) clearTimeout(this.scrollTimer);
    
    // 150ms 完美防抖，给足微信把文字画到屏幕上的时间
    this.scrollTimer = setTimeout(() => {
      // 🚀 核心绝招：先置空，再在回调中赋值！
      // 这相当于把锚点“拔出来，再插进去”，强制唤醒微信底层的滚动功能
      this.setData({ scrollToView: '' }, () => {
        this.setData({ scrollToView: 'chat-bottom' });
      });
    }, 150);
  },

  onSupInput(e) {
    const key = e.currentTarget.dataset.key; // 获取类似 'Q1_sup' 的键名
    this.setData({ 
      [`answers.${key}`]: e.detail.value 
    });
  },
  // ==========================================
  // 🌟 高级富文本渲染器 (完美支持流式)
  // ==========================================
  formatMessage(text) {
    if (!text) return "";
    let lines = text.split('\n');
    let html = '';
    let isHeader = false;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim(); 
      line = line.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #7D8C73; font-weight: 900; padding: 0 4rpx;">$1</strong>');
      if (line.startsWith('- ') || line.startsWith('* ')) {
        line = '<span style="color: #7D8C73; margin-right: 8rpx;">•</span>' + line.substring(2);
      }

      if (line.includes('|') && line.length > 2) {
        if (/^[\|\-\:\s]+$/.test(line)) continue; 
        
        let cols = line.split('|').map(c => c.trim());
        if (cols[0] === '') cols.shift(); 
        if (cols.length > 0 && cols[cols.length - 1] === '') cols.pop();
        if (cols.length === 0) continue;

        if (cols[0].includes('步骤') || cols[0].includes('时间')) {
          isHeader = true; continue; 
        }

        let stepName = cols[0] || "护理步骤";
        let products = cols[1] || "暂无建议";
        let notes = cols[2] ? cols[2] : "";

        let cardHtml = `
          <div style="background: #fcfdfc; border-radius: 16rpx; padding: 24rpx; margin-bottom: 24rpx; border: 2rpx solid #eef2eb; box-shadow: 0 4rpx 16rpx rgba(125,140,115,0.08);">
              <div style="display: flex; align-items: center; margin-bottom: 16rpx;">
                  <div style="background: #7D8C73; width: 8rpx; height: 28rpx; border-radius: 4rpx; margin-right: 12rpx; display: inline-block;"></div>
                  <div style="font-weight: 800; color: #43503a; font-size: 28rpx; display: inline-block;">${stepName}</div>
              </div>
              <div style="color: #374151; font-size: 26rpx; line-height: 1.6; margin-bottom: ${notes ? '16rpx' : '0'};">
                  <span style="font-weight:bold; color:#7D8C73;">方案：</span>${products}
              </div>
              ${notes ? `
              <div style="padding-top: 16rpx; border-top: 2rpx dashed #d1d5db; color: #6b7280; font-size: 24rpx; line-height: 1.5;">
                  <span style="font-weight:bold; color:#9ca3af;">注意：</span>${notes}
              </div>` : ''}
          </div>
        `;
        html += cardHtml;
      } else {
        html += line === '' ? '<br>' : line + '<br>';
      }
    }
    html = html.replace(/(<br>){3,}/g, '<br><br>');
    return html;
  },

  // ==========================================
  // 🌟 终极流式网络引擎 + 独立打字机
  // ==========================================
  async requestAIStream(step, queryText, imageBase64 = null) {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) return;
    
    const originalStep = this.data.currentStep;
    this.setData({ currentStep: -1 });

    const aiMsgIndex = this.data.messages.length;
    this.setData({
      [`messages[${aiMsgIndex}]`]: { id: Date.now(), role: 'ai', content: '', isTyping: true }
    });
    this.scrollToBottom();

    let fullText = "";
    let displayLength = 0;
    let isNetworkDone = false;
    let nextStepToSet = originalStep;
    
    // 微信专供：手动 UTF-8 拼包解码器 (防断字乱码)
    let textBuffer = new Uint8Array(0);
    const decodeStream = (arrayBuffer) => {
      let newBytes = new Uint8Array(arrayBuffer);
      let merged = new Uint8Array(textBuffer.length + newBytes.length);
      merged.set(textBuffer); merged.set(newBytes, textBuffer.length);
      let i = 0, str = "";
      while (i < merged.length) {
        let b0 = merged[i], charLength = 0;
        if ((b0 & 0x80) === 0) charLength = 1;
        else if ((b0 & 0xE0) === 0xC0) charLength = 2;
        else if ((b0 & 0xF0) === 0xE0) charLength = 3;
        else if ((b0 & 0xF8) === 0xF0) charLength = 4;
        else { i++; continue; } 
        if (i + charLength > merged.length) break; 
        if (charLength === 1) str += String.fromCharCode(b0);
        else if (charLength === 2) str += String.fromCharCode(((b0 & 0x1F) << 6) | (merged[i+1] & 0x3F));
        else if (charLength === 3) str += String.fromCharCode(((b0 & 0x0F) << 12) | ((merged[i+1] & 0x3F) << 6) | (merged[i+2] & 0x3F));
        else if (charLength === 4) {
          let codePoint = ((b0 & 0x07) << 18) | ((merged[i+1] & 0x3F) << 12) | ((merged[i+2] & 0x3F) << 6) | (merged[i+3] & 0x3F);
          codePoint -= 0x10000;
          str += String.fromCharCode((codePoint >> 10) + 0xD800, (codePoint & 0x3FF) + 0xDC00);
        }
        i += charLength;
      }
      textBuffer = merged.slice(i); return str;
    };

    // 🚀 独立打字机定时器
    if (this.typewriterTimer) clearInterval(this.typewriterTimer);
    
    this.typewriterTimer = setInterval(() => {
      if (displayLength < fullText.length) {
        // 动态调速：如果网络猛灌数据进来，打字机自动加速消化
        let backlog = fullText.length - displayLength;
        let charsToAdd = 2; 
        if (backlog > 20) charsToAdd = 4;
        if (backlog > 60) charsToAdd = 8;
        
        displayLength += charsToAdd;
        if (displayLength > fullText.length) displayLength = fullText.length;

        let currentMarkdown = fullText.substring(0, displayLength);
        currentMarkdown = currentMarkdown.replace(/\[SHOW_STEP_2_AND_SKIP\]|\[SHOW_STEP_3\]|\[SHOW_STEP_4\]/g, "");
        
        this.setData({ [`messages[${aiMsgIndex}].content`]: this.formatMessage(currentMarkdown) });
        this.scrollToBottom();

      } else if (isNetworkDone) {
        clearInterval(this.typewriterTimer);
        this.setData({ [`messages[${aiMsgIndex}].isTyping`]: false, currentStep: nextStepToSet });
      }
    }, 40); // 间隔 40 毫秒

    // 发起真实的网络请求
    const requestTask = wx.request({
      url: `${app.globalData.baseUrl}/app01/api/wx_chat_stream/`,
      method: 'POST',
      enableChunked: true, // 开启流式通道
      header: { 'content-type': 'application/x-www-form-urlencoded', 'Authorization': `Bearer ${token}` },
      data: { step: step, query: queryText, subject_name: this.data.subjectName, image_base64: imageBase64 || '' },
      success: (res) => {
        if (fullText.includes('[SHOW_STEP_3]')) nextStepToSet = 2;
        if (fullText.includes('[SHOW_STEP_4]')) nextStepToSet = 3;
        if (step === 'submit_questionnaire') nextStepToSet = originalStep === 0 ? 1 : originalStep; 
        else if (step === 'analyze') nextStepToSet = 3;
        else if (step === 'generate_plan') nextStepToSet = 4;
        
        isNetworkDone = true; // 发送完工信号给打字机
      },
      fail: () => {
        clearInterval(this.typewriterTimer);
        this.setData({
          [`messages[${aiMsgIndex}].content`]: "❌ 网络连接中断，请重试。",
          [`messages[${aiMsgIndex}].isTyping`]: false, currentStep: originalStep 
        });
      }
    });

    requestTask.onChunkReceived((res) => {
      let newText = decodeStream(res.data);
      if (!newText) return; 

      // 🛡️ 核心拦截：把后端的 1024 破冰空格彻底清理掉，绝不放进展示区
      if (fullText.trim().length === 0) {
          newText = newText.trimStart();
      }
      
      // 文字直接扔进水池，页面渲染全靠定时器
      fullText += newText;
    });
  },

  onNameInput(e) { this.setData({ subjectName: e.detail.value }); },

  startQuestionnaire() { 
    if (!this.data.subjectName.trim()) return wx.showToast({ title: '请先输入被测人姓名', icon: 'none' });
    this.setData({ showQuestionnaire: true, currentQIndex: 0, answers: {} }); 
  },
  closeQuestionnaire() { this.setData({ showQuestionnaire: false }); },
  
  selectOption(e) {
    const key = e.currentTarget.dataset.key;
    const qId = this.data.questionnaireData[this.data.currentQIndex].id;
    this.setData({ [`answers.${qId}`]: key });
  },
  prevQ() { if(this.data.currentQIndex > 0) this.setData({ currentQIndex: this.data.currentQIndex - 1 }); },
  
  nextQ() {
    const qId = this.data.questionnaireData[this.data.currentQIndex].id;
    if(!this.data.answers[qId]) return wx.showToast({ title: '请选择一项', icon: 'none' });
    
    if(this.data.currentQIndex < this.data.questionnaireData.length - 1) {
      this.setData({ currentQIndex: this.data.currentQIndex + 1 });
    } else {
      this.setData({ showQuestionnaire: false, isQuestionnaireSkipped: false });
      this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `被测人：${this.data.subjectName}\n📝 肤质问卷已提交。` }] });
      this.requestAIStream('submit_questionnaire', JSON.stringify({ subject_name: this.data.subjectName, answers: this.data.answers }));
    }
  },

  skipQuestionnaire() {
    if (!this.data.subjectName.trim()) return wx.showToast({ title: '请先输入被测人姓名', icon: 'none' });
    this.setData({
      isQuestionnaireSkipped: true, 
      messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `被测人：${this.data.subjectName}\n⏭️ 跳过肤质问卷` }],
      currentStep: 1 
    });
    this.scrollToBottom();

    setTimeout(() => {
       this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: '好的，已为您跳过肤质问卷！\n\n第二步：请上传面部照片，蓝博士将为您存档入库。', isTyping: false }] });
       this.scrollToBottom();
    }, 500);
  },

  uploadPhoto() {
    if (!this.data.subjectName.trim()) return wx.showToast({ title: '请重新输入姓名', icon: 'none' });

    wx.chooseMedia({
      count: 10, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'],
      success: (res) => {
        const tempFiles = res.tempFiles; 
        const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;

        const newMessages = tempFiles.map((file, index) => ({
          id: Date.now() + index, role: 'user',
          content: tempFiles.length > 1 ? `（已上传第 ${index + 1}/${tempFiles.length} 张照片）` : '（已上传面部照片）',
          image: file.tempFilePath
        }));

        this.setData({ messages: [...this.data.messages, ...newMessages], currentStep: 2 });
        this.scrollToBottom();
        wx.showLoading({ title: '照片加密上传中...', mask: true });

        const uploadTasks = tempFiles.map(file => {
          return new Promise((resolve, reject) => {
            wx.uploadFile({
              url: `${app.globalData.baseUrl}/app01/api/save_skin_photo/`,
              filePath: file.tempFilePath, name: 'file',
              formData: { 'subject_name': this.data.subjectName }, 
              header: { 'Authorization': `Bearer ${token}` },
              success: (uploadRes) => resolve(uploadRes), fail: (err) => reject(err)
            });
          });
        });

        Promise.all(uploadTasks).then(() => {
            wx.hideLoading();
            setTimeout(() => {
              const aiMsg = this.data.isQuestionnaireSkipped 
                ? `一共 ${tempFiles.length} 张照片已为您存档入库！\n\n⚠️ 蓝博士发现您跳过了问卷，需要补充问卷数据才能出具精准分析报告哦~\n\n第三步：点击下方按钮生成报告。` 
                : `一共 ${tempFiles.length} 张照片已为您存档入库！\n\n第三步：请点击下方按钮生成深度肤质报告。`;
              
              this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: aiMsg, isTyping: false }] });
              this.scrollToBottom();

              wx.request({
                url: `${app.globalData.baseUrl}/app01/api/wx_chat_stream/`,
                method: 'POST',
                header: { 'content-type': 'application/x-www-form-urlencoded', 'Authorization': `Bearer ${token}` },
                data: { step: 'pre_analyze', subject_name: this.data.subjectName, query: '预生成报告' }
              });
            }, 500);
          }).catch((err) => {
            wx.hideLoading();
            wx.showToast({ title: '上传失败', icon: 'none' });
          });
      }
    });
  },

  skipPhoto() {
    this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `⏭️ 跳过照片上传` }], currentStep: 2 });
    this.scrollToBottom();

    setTimeout(() => {
       const aiMsg = this.data.isQuestionnaireSkipped 
         ? '好的，已为您跳过照片上传！\n\n⚠️ 提示：您没有留存数据，只能提供通用指引...\n\n第三步：点击下方按钮生成报告。' 
         : '好的，已为您跳过照片上传！\n\n第三步：请点击下方按钮生成深度肤质报告。';

       this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: aiMsg, isTyping: false }] });
       this.scrollToBottom();
       
       wx.request({
         url: `${app.globalData.baseUrl}/app01/api/wx_chat_stream/`,
         method: 'POST',
         header: { 'content-type': 'application/x-www-form-urlencoded', 'Authorization': `Bearer ${wx.getStorageSync('accessToken')}` },
         data: { step: 'pre_analyze', subject_name: this.data.subjectName, query: '预生成报告' }
       });
    }, 500);
  },

  generateAnalysis() {
    this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: '🧠 请生成深度肤质分析报告。' }] });
    this.requestAIStream('analyze', '请结合档案生成深度报告。');
  },

  generatePlan() {
    this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: '📋 请为我定制专属护肤方案。' }] });
    this.requestAIStream('generate_plan', '请生成专属方案表格。');
  },

  resetChat() {
    this.setData({
      messages: [{ id: 'init', role: 'ai', content: '已为您重置档案，您可以随时开启全新放大镜！', isTyping: false }],
      currentStep: 0, subjectName: '', answers: {}, isQuestionnaireSkipped: false
    });
  }
});
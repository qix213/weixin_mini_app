const app = getApp();

Page({
  data: {
    messages: [
      { 
        id: 'init', 
        role: 'ai', 
        content: '您好呀，宝贝！✨ 我是您的专属护肤私教蓝博士。<br><br>第一步：请输入**被测人姓名**，并完成肤质问卷。', 
        isTyping: false 
      }
    ],
    scrollToId: '',
    currentStep: 0, 
    
    // 🌟 被测人姓名
    subjectName: '',

    // 问卷相关
    showQuestionnaire: false,
    questionnaireData: [], 
    currentQIndex: 0,
    answers: {},
    isQuestionnaireSkipped: false // 🌟 新增：标记是否跳过了问卷
  },

  onLoad() {
    this.fetchQuestionnaire();
  },

  // 获取问卷数据
  fetchQuestionnaire() {
    wx.request({
      url: `${app.globalData.baseUrl}/app01/api/get_questionnaire/`, 
      success: (res) => {
        let data = res.data;
        if (data && data.data) {
           this.setData({ questionnaireData: data.data });
        } else if (Array.isArray(data)) {
           this.setData({ questionnaireData: data });
        } else {
           console.error("【题库调试】后端返回的数据格式无法解析");
        }
      },
      fail: (err) => {
        console.error("【题库调试】请求失败:", err);
      }
    });
  },

  scrollToBottom() {
    setTimeout(() => {
      const lastMsgIndex = this.data.messages.length - 1;
      this.setData({ scrollToId: `msg-${lastMsgIndex}` });
    }, 100);
  },

  decodeUTF8(arrayBuffer) {
    let uint8Array = new Uint8Array(arrayBuffer);
    let out = "", i = 0, len = uint8Array.length;
    while(i < len) {
        let c = uint8Array[i++];
        switch(c >> 4) { 
          case 0: case 1: case 2: case 3: case 4: case 5: case 6: case 7:
            out += String.fromCharCode(c); break;
          case 12: case 13:
            out += String.fromCharCode(((c & 0x1F) << 6) | (uint8Array[i++] & 0x3F)); break;
          case 14:
            out += String.fromCharCode(((c & 0x0F) << 12) | ((uint8Array[i++] & 0x3F) << 6) | ((uint8Array[i++] & 0x3F) << 0)); break;
        }
    }
    return out;
  },

  async requestAIStream(step, queryText, imageBase64 = null) {
    const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!token) {
      wx.showToast({ title: '请先登录账号', icon: 'none' });
      setTimeout(() => { wx.navigateTo({ url: '/pages/login/login' }); }, 1500);
      return;
    }
    
    // 🌟 核心修复 1：在变成 -1 之前，把当前的真实步骤备份下来！
    const originalStep = this.data.currentStep;
    
    this.setData({ currentStep: -1 });

    const aiMsgIndex = this.data.messages.length;
    this.setData({
      [`messages[${aiMsgIndex}]`]: { id: Date.now(), role: 'ai', content: '', isTyping: true }
    });
    this.scrollToBottom();

    let fullText = "";

    const requestTask = wx.request({
      url: `${app.globalData.baseUrl}/app01/api/wx_chat_stream/`,
      method: 'POST',
      enableChunked: true,
      header: { 
        'content-type': 'application/x-www-form-urlencoded',
        'Authorization': `Bearer ${token}` 
      },
      data: {
        step: step,
        query: queryText,
        image_base64: imageBase64 || ''
      },
      success: (res) => {
        this.setData({ [`messages[${aiMsgIndex}].isTyping`]: false });
        
        // 🌟 核心修复 2：使用备份的 originalStep 参与流转逻辑的计算
        let nextStep = originalStep; 
        
        if (fullText.includes('[SHOW_STEP_3]')) nextStep = 2;
        if (fullText.includes('[SHOW_STEP_4]')) nextStep = 3;
        
        if (step === 'submit_questionnaire') {
          // 如果是第一次提交(0)，走向第2步(拍照为1)；如果是第三步返回补充的(2)，停留在第三步(2)
          nextStep = originalStep === 0 ? 1 : originalStep; 
        } else if (step === 'analyze') {
          nextStep = 3;
        } else if (step === 'generate_plan') {
          nextStep = 4;
        }

        let cleanedText = fullText.replace(/\[SHOW_STEP_2_AND_SKIP\]|\[SHOW_STEP_3\]|\[SHOW_STEP_4\]/g, "");
        cleanedText = cleanedText.replace(/\n/g, '<br>'); 
        
        this.setData({ 
          [`messages[${aiMsgIndex}].content`]: cleanedText,
          currentStep: nextStep 
        });
      },
      fail: () => {
        this.setData({
          [`messages[${aiMsgIndex}].content`]: "❌ 网络连接中断，请重试。",
          [`messages[${aiMsgIndex}].isTyping`]: false,
          currentStep: originalStep // 🌟 修复：如果失败，退回原来的步骤，而不是退回 0
        });
      }
    });

    requestTask.onChunkReceived((res) => {
      const newText = this.decodeUTF8(res.data);
      fullText += newText;
      let displayText = fullText.replace(/\[SHOW_STEP_2_AND_SKIP\]|\[SHOW_STEP_3\]|\[SHOW_STEP_4\]/g, "");
      displayText = displayText.replace(/\n/g, '<br>');
      this.setData({ [`messages[${aiMsgIndex}].content`]: displayText });
      this.scrollToBottom();
    });
  },

  // ======== 姓名输入 ========
  onNameInput(e) {
    this.setData({ subjectName: e.detail.value });
  },

  // ======== 🌟 全新第一步：问卷 ========
  startQuestionnaire() { 
    const { subjectName } = this.data;
    if (!subjectName || !subjectName.trim()) {
      return wx.showToast({ title: '请先输入被测人姓名', icon: 'none' });
    }
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
      
      this.setData({
        messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `被测人：${this.data.subjectName}\n📝 肤质问卷已提交。` }]
      });

      const payload = {
        subject_name: this.data.subjectName,
        answers: this.data.answers
      };
      this.requestAIStream('submit_questionnaire', JSON.stringify(payload));
    }
  },

  skipQuestionnaire() {
    const { subjectName } = this.data;
    if (!subjectName || !subjectName.trim()) {
      return wx.showToast({ title: '请先输入被测人姓名', icon: 'none' });
    }

    this.setData({
      isQuestionnaireSkipped: true, // 标记为跳过
      messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `被测人：${subjectName}\n⏭️ 跳过肤质问卷` }],
      currentStep: 1 // 进入第二步拍照
    });
    this.scrollToBottom();

    setTimeout(() => {
       this.setData({
          messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: '好的，已为您跳过肤质问卷！\n\n第二步：请上传面部照片，蓝博士将为您存档入库。', isTyping: false }]
       });
       this.scrollToBottom();
    }, 500);
  },

  // ======== 🌟 全新第二步：上传照片 ========
// ======== 🌟 全新第二步：上传照片 (支持多图并发上传) ========
uploadPhoto() {
  const { subjectName } = this.data;
  wx.chooseMedia({
    count: 10, // 🔥 修改点 1：将 1 改为 10，允许最多选 10 张
    mediaType: ['image'],
    sourceType: ['album', 'camera'],
    sizeType: ['compressed'],
    // camera: 'front', // 💡 建议注释掉：既然允许多张，用户可能需要用后置摄像头拍侧脸或局部细节
    success: (res) => {
      const tempFiles = res.tempFiles; // 现在这是一个数组
      const token = wx.getStorageSync('accessToken') || app.globalData.accessToken;

      // 🔥 修改点 2：将所有选中的照片转化为多条气泡消息
      const newMessages = tempFiles.map((file, index) => ({
        id: Date.now() + index, // 确保 key 唯一
        role: 'user',
        content: tempFiles.length > 1 ? `（已上传第 ${index + 1}/${tempFiles.length} 张照片）` : '（已上传面部照片）',
        image: file.tempFilePath
      }));

      this.setData({
        messages: [...this.data.messages, ...newMessages],
        currentStep: 2 // 转向第三步：报告分析
      });
      this.scrollToBottom();

      // 增加全屏 Loading 防护，避免上传过程中用户乱点别的按钮
      wx.showLoading({ title: '照片加密上传中...', mask: true });

      // 🔥 修改点 3：利用 Promise.all 解决 wx.uploadFile 只能单张上传的痛点
      const uploadTasks = tempFiles.map(file => {
        return new Promise((resolve, reject) => {
          wx.uploadFile({
            url: `${app.globalData.baseUrl}/app01/api/save_skin_photo/`,
            filePath: file.tempFilePath,
            name: 'file',
            formData: { 'subject_name': subjectName },
            header: { 'Authorization': `Bearer ${token}` },
            success: (uploadRes) => resolve(uploadRes),
            fail: (err) => reject(err)
          });
        });
      });

      // 等待所有照片都上传完毕
      Promise.all(uploadTasks)
        .then(() => {
          wx.hideLoading();
          console.log(`INFO: ${tempFiles.length} 张照片已全部成功提交到后端`);

          // 根据是否跳过问卷，给出不同的提示
          setTimeout(() => {
            const aiMsg = this.data.isQuestionnaireSkipped 
              ? `一共 ${tempFiles.length} 张照片已为您存档入库！\n\n⚠️ 蓝博士发现您跳过了问卷，需要补充问卷数据才能出具精准分析报告哦~` 
              : `一共 ${tempFiles.length} 张照片已为您存档入库！\n\n第三步：点击下方按钮生成深度肤质报告。`;
            
            this.setData({
              messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: aiMsg, isTyping: false }]
            });
            this.scrollToBottom();
          }, 500);
        })
        .catch((err) => {
          wx.hideLoading();
          console.error('ERROR: 部分或全部照片上传失败', err);
          wx.showToast({ title: '网络波动，部分照片上传失败', icon: 'none' });
        });
    }
  });
},

  skipPhoto() {
    this.setData({
      messages: [...this.data.messages, { id: Date.now(), role: 'user', content: `⏭️ 跳过照片上传` }],
      currentStep: 2
    });
    this.scrollToBottom();

    setTimeout(() => {
       const aiMsg = this.data.isQuestionnaireSkipped 
         ? '好的，已为您跳过照片上传！\n\n⚠️ 提示：需要补充问卷调查数据才能为您出具分析报告哦~' 
         : '好的，已为您跳过照片上传！\n\n第三步：请点击下方按钮生成深度肤质报告。';

       this.setData({
          messages: [...this.data.messages, { id: Date.now(), role: 'ai', content: aiMsg, isTyping: false }]
       });
       this.scrollToBottom();
    }, 500);
  },

  // ======== 第三步：生成报告 ========
  generateAnalysis() {
    this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: '🧠 请生成深度肤质分析报告。' }] });
    this.requestAIStream('analyze', '请结合档案生成深度报告。');
  },

  // ======== 第四步：生成方案 ========
  generatePlan() {
    this.setData({ messages: [...this.data.messages, { id: Date.now(), role: 'user', content: '📋 请为我定制专属护肤方案。' }] });
    this.requestAIStream('generate_plan', '请生成专属方案表格。');
  },

  resetChat() {
    this.setData({
      messages: [{ id: 'init', role: 'ai', content: '已为您重置档案，您可以随时开启全新诊断！', isTyping: false }],
      currentStep: 0, 
      subjectName: '',
      answers: {},
      isQuestionnaireSkipped: false
    });
  }
});
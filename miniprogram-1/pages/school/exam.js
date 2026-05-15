const app = getApp();

Page({
  data: {
    status: 'select', // 页面状态：select(选卷), testing(考试中), result(成绩与错题)
    // 固定的考试分类字典（与后端一致）
    courseTypes: [
      { id: 1, name: "皮肤学" },
      { id: 2, name: "四维三阶问题肌" },
      { id: 3, name: "五维筋膜" },
      { id: 4, name: "品牌篇" },
      { id: 5, name: "产品篇" },
      { id: 6, name: "各类皮肤问题家居解决方案" }
    ],
    currentCourseId: null,
    currentCourseName: '',
    
    questions: [], // 试卷题目列表
    userAnswers: {}, // 用户的作答数据：{"题目ID": "选项A/B/C或数组"}
    
    examResult: null, // 成绩信息
    resultList: [] // 错题本解析列表
  },

  onLoad() {
    this.checkAuth();
  },

  checkAuth() {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    if (!accessToken) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
    }
  },

  // 1. 开始考试（抽卷）
  startExam(e) {
    const courseId = e.currentTarget.dataset.id;
    const courseName = e.currentTarget.dataset.name;
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;

    wx.showLoading({ title: '生成绝密试卷中...' });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/exam_questions/generate_paper/?course_type=${courseId}&limit=10`,
      method: 'GET',
      header: { 'Authorization': `Bearer ${accessToken}` },
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          this.setData({
            status: 'testing',
            currentCourseId: courseId,
            currentCourseName: courseName,
            questions: res.data.data.questions,
            userAnswers: {} // 清空历史作答
          });
        } else {
          wx.showToast({ title: res.data.msg || '暂无题目', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  },

  // 2. 单选题/判断题 选中事件
  onSingleChange(e) {
    const qid = e.currentTarget.dataset.qid;
    const val = e.detail.value;
    this.setData({
      [`userAnswers.${qid}`]: val
    });
  },

  // 3. 多选题 选中事件
  onMultiChange(e) {
    const qid = e.currentTarget.dataset.qid;
    const valArray = e.detail.value; // 多选返回的是数组，如 ['A', 'C']
    this.setData({
      [`userAnswers.${qid}`]: valArray
    });
  },

  // 4. 交卷与后台判题
  submitExam() {
    const { questions, userAnswers, currentCourseId } = this.data;
    
    // 校验是否全部做完（可选拦截）
    if (Object.keys(userAnswers).length < questions.length) {
      wx.showModal({
        title: '提示',
        content: '您还有题目未作答，确定要提前交卷吗？',
        success: (res) => {
          if (res.confirm) {
            this.doSubmit(currentCourseId, userAnswers);
          }
        }
      });
    } else {
      this.doSubmit(currentCourseId, userAnswers);
    }
  },

  doSubmit(courseType, answers) {
    const accessToken = wx.getStorageSync('accessToken') || app.globalData.accessToken;
    wx.showLoading({ title: 'AI系统批改中...' });

    wx.request({
      url: `${app.globalData.baseUrl}/app01/exam_records/`,
      method: 'POST',
      header: { 
        'content-type': 'application/json',
        'Authorization': `Bearer ${accessToken}` 
      },
      data: {
        course_type: courseType,
        answers: answers // 格式: {"1": "A", "2": ["A", "C"]}，后端会自动解析对比
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data.code === 200) {
          const resultData = res.data.data;
          
          // 将后端的 user_answers 对象转为数组，方便前台 wx:for 循环渲染错题本
          const answerDict = resultData.user_answers;
          const resultList = Object.keys(answerDict).map(key => answerDict[key]);

          this.setData({
            status: 'result',
            examResult: resultData,
            resultList: resultList
          });
        } else {
          wx.showToast({ title: res.data.msg || '交卷失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常，交卷失败', icon: 'none' });
      }
    });
  },

  // 返回重选科目
  backToSelect() {
    this.setData({
      status: 'select',
      questions: [],
      userAnswers: {},
      examResult: null,
      resultList: []
    });
  }
});
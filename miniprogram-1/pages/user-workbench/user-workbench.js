const app = getApp();

// 辅助函数：智能提取中文拼音首字母
function getInitial(name) {
  if (!name) return '#';
  let ch = name.charAt(0);
  if (/[a-zA-Z]/.test(ch)) return ch.toUpperCase();
  if (!/[\u4e00-\u9fa5]/.test(ch)) return '#';
  
  // 拼音首字母对应的中文边界字符 (无 I, U, V)
  const letters = 'ABCDEFGHJKLMNOPQRSTWXYZ'.split('');
  const zh = '阿八嚓哒妸发旮哈讥咔垃痳拏噢妑七呥扨它穵夕丫帀'.split('');
  
  for (let i = 0; i < zh.length; i++) {
    if (ch.localeCompare(zh[i], 'zh-Hans-CN') < 0) {
      if (i === 0) return '#';
      return letters[i - 1];
    }
  }
  return 'Z';
}

Page({
  data: {
    allProfiles: [],       // 原始所有数据
    groupedProfiles: [],   // 按 A-Z 分组后的数据
    filteredGroups: [],    // 搜索过滤后的分组数据
    
    expandedId: '',        // 当前展开的档案 ID
    searchValue: '',       
    loading: true,

    // A-Z 导航相关
    alphabet: ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','#'],
    scrollToLetter: '',    // 控制 scroll-view 滚动到的 ID
    currentLetter: '',     // 当前选中的字母
    showLetterToast: false // 是否显示中央大字母弹窗
  },

  onLoad() {
    this.fetchSkinProfiles();
  },

  fetchSkinProfiles() {
    this.setData({ loading: true });
    
    app.request({
      url: '/app01/api/skin-profiles/', 
      method: 'GET'
    }).then(res => {
      let data = res.data.results || res.data || [];
      
      data.forEach(profile => {
        profile.initial = getInitial(profile.subject_name); // 提取首字母
        
        if (profile.photo_records && profile.photo_records.length > 0) {
          profile.photo_records.forEach(pr => {
            pr.full_url = pr.face_image.startsWith('http') 
              ? pr.face_image 
              : `${app.globalData.baseUrl}${pr.face_image}`;
            
            const d = new Date(pr.uploaded_at);
            const pad = n => n < 10 ? '0' + n : n;
            pr.display_date = `${d.getFullYear()}.${pad(d.getMonth()+1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
          });
          profile.photo_records.sort((a, b) => new Date(a.uploaded_at) - new Date(b.uploaded_at));
        }
      });

      // 执行分组与排序
      const groups = this.groupData(data);

      this.setData({ 
        allProfiles: data, 
        groupedProfiles: groups, 
        filteredGroups: groups,
        loading: false 
      });
    }).catch(err => {
      console.error('获取档案失败', err);
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  // 将扁平数据按首字母 A-Z 分组
  groupData(data) {
    let groupMap = {};
    data.forEach(item => {
      const letter = item.initial;
      if (!groupMap[letter]) groupMap[letter] = [];
      groupMap[letter].push(item);
    });

    let groups = [];
    this.data.alphabet.forEach(letter => {
      if (groupMap[letter] && groupMap[letter].length > 0) {
        // 组内再按拼音升序
        groupMap[letter].sort((a, b) => a.subject_name.localeCompare(b.subject_name, 'zh-Hans-CN'));
        groups.push({ letter: letter, list: groupMap[letter] });
      }
    });
    return groups;
  },

  // 搜索逻辑
  onSearchInput(e) {
    const keyword = e.detail.value.trim().toLowerCase();
    this.setData({ searchValue: keyword });

    if (!keyword) {
      this.setData({ filteredGroups: this.data.groupedProfiles });
      return;
    }

    const filteredData = this.data.allProfiles.filter(p => 
      p.subject_name.toLowerCase().includes(keyword)
    );
    this.setData({ filteredGroups: this.groupData(filteredData) });
  },

  // 折叠展开
  toggleExpand(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ expandedId: this.data.expandedId === id ? '' : id });
  },

  // 图片预览
  previewImage(e) {
    const { url, profileid } = e.currentTarget.dataset;
    const currentProfile = this.data.allProfiles.find(p => p.id === profileid);
    if (currentProfile && currentProfile.photo_records) {
      wx.previewImage({
        current: url,
        urls: currentProfile.photo_records.map(pr => pr.full_url)
      });
    }
  },

  // ================= 字母侧边栏滑动交互 =================
  onAlphaTouchStart(e) {
    this.handleAlphaTouch(e);
    this.setData({ showLetterToast: true });
  },

  onAlphaTouchMove(e) {
    this.handleAlphaTouch(e);
  },

  onAlphaTouchEnd() {
    this.setData({ showLetterToast: false });
  },

  handleAlphaTouch(e) {
    const touchY = e.touches[0].clientY;
    
    // 动态获取字母导航条的位置信息，计算当前划到了哪个字母
    wx.createSelectorQuery().select('.alphabet-sidebar').boundingClientRect((rect) => {
      if (!rect) return;
      const itemHeight = rect.height / this.data.alphabet.length;
      let index = Math.floor((touchY - rect.top) / itemHeight);
      
      // 越界保护
      if (index < 0) index = 0;
      if (index >= this.data.alphabet.length) index = this.data.alphabet.length - 1;
      
      const letter = this.data.alphabet[index];
      
      if (this.data.currentLetter !== letter) {
        this.setData({ currentLetter: letter });
        
        // 检查列表中是否有这个字母的分组，有的话才触发滚动
        const hasGroup = this.data.filteredGroups.some(g => g.letter === letter);
        if (hasGroup) {
          this.setData({ scrollToLetter: `letter-${letter}` });
        }
      }
    }).exec();
  }
});
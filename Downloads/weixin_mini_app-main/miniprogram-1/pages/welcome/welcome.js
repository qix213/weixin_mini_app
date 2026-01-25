// pages/welcome/welcome.js
Page({
  /**
   * 页面的初始数据
   */
  data: {
   second:4
  },
doJump(){
  //跳首页
  wx.switchTab({
    url: '/pages/index/index',
  })
  },
  onLoad(options){
    var instance=setInterval(()=>{
      if(this.data.second<=0){
        clearInterval(instance)
        wx.switchTab({
          url: '/pages/index/index',
        })
      }else{this.setData({
        second: this.data.second - 1
      })
    }

    },1000)
    
  }

})
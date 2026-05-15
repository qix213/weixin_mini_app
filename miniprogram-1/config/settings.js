// config.js
// 🌟 这里不要再写域名了，交给 app.js 统一处理协议头和域名
const rootPath = '/app01'; 

module.exports = {
  welcome: rootPath + '/welcome/',
  banner: rootPath + '/banner/', 
  category: rootPath + '/categories/', 
  goods_detail: rootPath + '/goods/',
  // 图片显示的基础地址
  base: 'https://www.lansik2026.com', 
}
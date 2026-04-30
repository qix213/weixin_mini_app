// 🌟 临时修改为公网 IP，等备案通过后再换回域名
const rootUrl = 'https://101.42.20.250/app01'

module.exports = {
  welcome: rootUrl + '/welcome/',
  banner: rootUrl + '/banner/', 
  category: rootUrl + '/categories/', 
  goods_detail: rootUrl + '/goods/',
  base : 'https://101.42.20.250', // 🌟 这里也同步修改为 IP
}
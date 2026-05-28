const app = getApp();

// 🗺️ 全国主要城市坐标字典（前端临时智能匹配用）
// 后期建议直接从后端的 Order 表中提取 sender_address 进行经纬度转换
const CITY_COORDS = {
  "北京": { lat: 39.9042, lng: 116.4074 },
  "上海": { lat: 31.2304, lng: 121.4737 },
  "广州": { lat: 23.1291, lng: 113.2644 },
  "深圳": { lat: 22.5431, lng: 114.0579 },
  "青岛": { lat: 36.0671, lng: 120.3826 },
  "杭州": { lat: 30.2741, lng: 120.1551 },
  "成都": { lat: 30.5728, lng: 104.0668 },
  "武汉": { lat: 30.5928, lng: 114.3055 },
  "西安": { lat: 34.3416, lng: 108.9398 },
  "重庆": { lat: 29.5630, lng: 106.5516 }
};

Page({
  data: { 
    loading: true, 
    order_sn: "", 
    waybillCode: "", 
    latestStatus: "查询中...",
    senderCity: "发货地",
    receiverCity: "收货地",
    trackList: [],
    
    showMap: false,
    latitude: 39.908823,
    longitude: 116.397470,
    scale: 6, 
    markers: [],
    polylines: []
  },

  onLoad(options) {
    if (options.order_sn) {
      this.setData({ order_sn: options.order_sn });
      // 🚀 核心改动：先查轨迹(提取城市)，成功后再查GIS画地图，确保数据有先后顺序
      this.getTrackData();
    } else {
      wx.showToast({ title: "参数错误", icon: "error" });
    }
  },

  // 1. 获取轨迹并提取城市
  getTrackData() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd/trace/query/`,
      method: "GET",
      header: app.getRequestHeader ? app.getRequestHeader() : {},
      data: { order_sn: that.data.order_sn },
      success(res) {
        if (res.data.code === 200) {
          const latestStatus = res.data.latest_status || '运输中';
          const originalList = res.data.data?.data?.traceDetails || [];
          
          let filteredList = [];
          let lastLoc = "";
          let lastAddedAction = "";

          const getCityName = (site, remark) => {
            if (remark && remark.includes('地址：')) {
              let addrMatch = remark.match(/地址：(?:.*?省|.*?自治区)?([^省市]+市)/);
              if (addrMatch) return addrMatch[1].replace('市', '');
            }
            const longCities = ['哈尔滨', '乌鲁木齐', '石家庄', '张家口', '秦皇岛', '连云港', '齐齐哈尔', '牡丹江', '防城港', '平顶山', '六盘水', '攀枝花', '驻马店'];
            for (let c of longCities) {
              if (site.includes(c)) return c;
            }
            return site ? site.substring(0, 2) : "未知";
          };

          let sCity = "发货地";
          let rCity = "收货地";

          if (originalList.length > 0) {
            for (let i = originalList.length - 1; i >= 0; i--) {
              let site = originalList[i].operateSite || "";
              if (site && !site.includes("路由") && !site.includes("系统")) {
                sCity = getCityName(site, originalList[i].operationRemark);
                break;
              }
            }
            for (let i = 0; i < originalList.length; i++) {
              let site = originalList[i].operateSite || "";
              if (site && !site.includes("路由") && !site.includes("系统")) {
                rCity = getCityName(site, originalList[i].operationRemark);
                break;
              }
            }

            for (let i = originalList.length - 1; i >= 0; i--) {
              let item = originalList[i];
              let site = item.operateSite || "未知站点";
              let title = item.operationTitle || "";
              let remark = item.operationRemark || "";

              let currentLoc = site;
              if (site.includes("路由系统")) {
                let routeMatch = remark.match(/当前位于【(.*?)】/);
                currentLoc = routeMatch ? routeMatch[1] : "干线高速运输";
              }

              let isFirst = (i === originalList.length - 1);
              let isLast = (i === 0);
              let isLocChanged = (currentLoc !== lastLoc);
              let isKeyAction = /(派件|揽收|签收|妥投)/.test(title);
              let isLeaving = /(离开|发往)/.test(remark);

              let keep = false;
              if (isFirst || isLast || isKeyAction || isLocChanged || (isLeaving && lastAddedAction !== 'leaving')) {
                keep = true;
              }

              if (keep) {
                filteredList.unshift(item);
                lastLoc = currentLoc;
                lastAddedAction = isLeaving ? 'leaving' : 'other';
              }
            }
          }

          that.setData({
            trackList: filteredList,
            senderCity: sCity,
            receiverCity: rCity,
            waybillCode: `JD物流（${latestStatus}）`,
            latestStatus: latestStatus,
            loading: false
          });

          // 🚀 城市提取完毕，去画地图！
          that.getGisTrackData();

        } else {
          wx.showToast({ title: res.data.msg || "轨迹查询失败", icon: "none" });
          that.setData({ loading: false });
        }
      }
    });
  },

  // 2. 根据城市画线
  getGisTrackData() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd/waybill/gis/track/`,
      method: "GET",
      header: app.getRequestHeader ? app.getRequestHeader() : {},
      data: { order_sn: that.data.order_sn },
      success(res) {
        if (res.data.code === 200) {
          const coreData = res.data.data?.data || {}; 
          const gisList = coreData.waybillGisDtoList || [];
          
          if (gisList.length > 0) {
            const lat = parseFloat(gisList[0].lat);
            const lng = parseFloat(gisList[0].lng);
            const vehicleName = coreData.gpsSourceName || "运输专线";

            let mapMarkers = [];
            let mapPolylines = [];

            // 💡 智能匹配起点城市坐标
            const senderCityName = that.data.senderCity;
            let startLat = lat - 1.5; // 兜底：如果字典没有，回退到视觉偏移
            let startLng = lng - 1.5;

            // 如果字典里有匹配的城市，使用真实坐标！
            for (let cityKey in CITY_COORDS) {
              if (senderCityName.includes(cityKey)) {
                startLat = CITY_COORDS[cityKey].lat;
                startLng = CITY_COORDS[cityKey].lng;
                break;
              }
            }

            // 📍 起点
            mapMarkers.push({
              id: 2, 
              latitude: startLat, 
              longitude: startLng,
              width: 20, 
              height: 20,
              callout: { 
                content: ` ${senderCityName}揽收 `, color: "#FFF", bgColor: "#1C2B33", 
                fontSize: 12, padding: 6, borderRadius: 10, display: "ALWAYS", textAlign: "center" 
              }
            });

            // 📍 货车
            mapMarkers.push({
              id: 1,
              latitude: lat,
              longitude: lng,
              width: 32,
              height: 32,
              callout: {
                content: ` 🚚 ${vehicleName} `, color: "#FFFFFF", bgColor: "#00A0B0", 
                fontSize: 13, padding: 8, borderRadius: 12, display: "ALWAYS", textAlign: "center"
              }
            });

            mapPolylines.push({
              points: [
                { latitude: startLat, longitude: startLng },
                { latitude: lat, longitude: lng }
              ],
              color: "#00CFD6",    
              width: 6,            
              arrowLine: true,     
              borderWidth: 1,
              borderColor: "#00A0B0"
            });

            that.setData({
              showMap: true,
              latitude: (startLat + lat) / 2, 
              longitude: (startLng + lng) / 2,
              markers: mapMarkers,
              polylines: mapPolylines
            });
          }
        }
      }
    });
  }
});
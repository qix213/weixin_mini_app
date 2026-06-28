const app = getApp();

// 🗺️ 全国主要城市坐标字典
const CITY_COORDS = {
  "北京": {
    lat: 39.9042,
    lng: 116.4074
  },
  "上海": {
    lat: 31.2304,
    lng: 121.4737
  },
  "广州": {
    lat: 23.1291,
    lng: 113.2644
  },
  "深圳": {
    lat: 22.5431,
    lng: 114.0579
  },
  "青岛": {
    lat: 36.0671,
    lng: 120.3826
  },
  "杭州": {
    lat: 30.2741,
    lng: 120.1551
  },
  "成都": {
    lat: 30.5728,
    lng: 104.0668
  },
  "武汉": {
    lat: 30.5928,
    lng: 114.3055
  },
  "西安": {
    lat: 34.3416,
    lng: 108.9398
  },
  "重庆": {
    lat: 29.5630,
    lng: 106.5516
  }
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
    promiseTime: "",
    showMap: false,
    latitude: 39.908823,
    longitude: 116.397470,
    scale: 6,
    markers: [],
    isTimelineExpanded: false,
    polylines: []
  },

  onLoad(options) {
    if (options.order_sn) {
      this.setData({
        order_sn: options.order_sn
      });
      this.getOrderDetail();
    } else {
      wx.showToast({
        title: "参数错误",
        icon: "error"
      });
    }
  },

  // 地址智能解析器（从收发货地址中拆出城市）
  extractCityFromAddress(info) {
    if (!info) return "";
    if (info.city && info.city.trim() !== '') return info.city.replace('市', '');

    let fullText = info.full_address || info.address || info.detail || "";
    if (!fullText) return "";

    let parts = fullText.split(/\s+/);
    for (let p of parts) {
      if (p.endsWith('市')) return p.replace('市', '');
    }

    let match = fullText.match(/(?:.*?省|.*?自治区)?([^省市\s]+市)/);
    if (match) return match[1].replace('市', '');

    const topCities = ['北京', '上海', '天津', '重庆'];
    for (let c of topCities) {
      if (fullText.includes(c)) return c;
    }
    return "";
  },

  // 1. 获取订单详情（获取精确收发货城市）
  getOrderDetail() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/order/detail/`,
      method: "GET",
      header: app.getRequestHeader ? app.getRequestHeader() : {},
      data: {
        order_sn: that.data.order_sn
      },
      success(res) {
        if (res.data.code === 200) {
          const orderData = res.data.data || {};
          let sCity = that.extractCityFromAddress(orderData.sender_info);
          let rCity = that.extractCityFromAddress(orderData.receiver_info);

          that.setData({
            orderSenderCity: sCity,
            orderReceiverCity: rCity
          });
        }
      },
      complete() {
        that.getTrackData();
      }
    });
  },

  // 2. 获取物流轨迹与状态
  getTrackData() {
    const that = this;
    wx.request({
      url: `${app.globalData.baseUrl}/app01/jd/trace/query/`,
      method: "GET",
      header: app.getRequestHeader ? app.getRequestHeader() : {},
      data: {
        order_sn: that.data.order_sn
      },
      success(res) {
        if (res.data.code === 200) {
          const originalList = res.data.data?.data?.traceDetails || res.data.data?.traceDetails || [];

          // 🌟 核心优化：智能提炼最新物流状态，不被后端的“未知状态”带跑偏
          let latestStatus = res.data.latest_status || "运输中";
          let promiseTime = res.data.promise_time || "";
          if (originalList.length > 0) {
            const topTrace = originalList[0]; // 获取最新一条记录
            const remarkText = topTrace.operationRemark || "";
            const catName = topTrace.categoryName || "";

            // 如果后端外层给的是未知，或者没有提供，前端通过最新轨迹智能识别
            if (latestStatus === "未知状态" || latestStatus === "运输中") {
              if (remarkText.includes("运输") || remarkText.includes("发车") || remarkText.includes("发往")) {
                latestStatus = "运输中";
              } else if (catName) {
                latestStatus = catName;
              }
            }
          }

          let filteredList = [];
          let lastLoc = "";
          let lastAddedAction = "";
          let currentTruckCity = ""; // 记录大卡车当前所在的文本城市

          const getCityNameFromSite = (site, remark) => {
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

          let trackSCity = "";
          let trackRCity = "";

          if (originalList.length > 0) {
            // 🌟 智能捕捉大卡车当前被文本标注的城市位置（如：从“当前位于【河北衡水市】”中抠出“衡水”）
            const remarkForTruck = originalList[0].operationRemark || "";
            const truckMatch = remarkForTruck.match(/当前位于【(.*?)】/);
            if (truckMatch) {
              currentTruckCity = truckMatch[1].replace('市', '');
            }

            for (let i = originalList.length - 1; i >= 0; i--) {
              let site = originalList[i].operateSite || "";
              if (site && !site.includes("路由") && !site.includes("系统")) {
                trackSCity = getCityNameFromSite(site, originalList[i].operationRemark);
                break;
              }
            }
            for (let i = 0; i < originalList.length; i++) {
              let site = originalList[i].operateSite || "";
              if (site && !site.includes("路由") && !site.includes("系统")) {
                trackRCity = getCityNameFromSite(site, originalList[i].operationRemark);
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

          let finalSenderCity = that.data.orderSenderCity || trackSCity || "发货地";
          let finalReceiverCity = that.data.orderReceiverCity || trackRCity || "收货地";

          that.setData({
            trackList: filteredList,
            senderCity: finalSenderCity,
            receiverCity: finalReceiverCity,
            currentTruckCity: currentTruckCity, // 存入卡车所在城市
            waybillCode: `JD物流（${latestStatus}）`,
            latestStatus: latestStatus,
            promiseTime: promiseTime,
            loading: false
          });

          that.getGisTrackData();

        } else {
          wx.showToast({
            title: res.data.msg || "轨迹查询失败",
            icon: "none"
          });
          that.setData({
            loading: false
          });
        }
      }
    });
  },

  // 3. 获取并绘制地图 GIS 轨迹线
// 3. 获取并绘制地图 GIS 轨迹线 (支持妥投后持续显示)
getGisTrackData() {
  const that = this;
  wx.request({
    url: `${app.globalData.baseUrl}/app01/jd/waybill/gis/track/`,
    method: "GET",
    header: app.getRequestHeader ? app.getRequestHeader() : {},
    data: {
      order_sn: that.data.order_sn
    },
    success(res) {
      if (res.data.code === 200) {
        const coreData = res.data.data?.data || res.data.data || {};
        const gisList = coreData.waybillGisDtoList || [];

        let truckLat, truckLng;
        // 判断当前是否已经是妥投/签收状态
        const isDelivered = /(签收|完成|妥投)/.test(that.data.latestStatus);

        // 🌟 1. 优先尝试获取硬件实时 GPS 坐标
        if (gisList.length > 0) {
          const firstPoint = gisList[0];
          truckLat = parseFloat(firstPoint.lat || firstPoint.latitude);
          truckLng = parseFloat(firstPoint.lng || firstPoint.longitude);
        }

        // 🌟 2. 核心修复：如果没获取到 GPS（比如妥投后被京东清空了）
        // 我们强制去字典里找“收货地”的坐标，作为最后的位置
        if (isNaN(truckLat) || isNaN(truckLng)) {
          for (let cityKey in CITY_COORDS) {
            if (that.data.receiverCity.includes(cityKey)) {
              truckLat = CITY_COORDS[cityKey].lat;
              truckLng = CITY_COORDS[cityKey].lng;
              break;
            }
          }
        }

        // 如果连收货地匹配都失败了，实在没坐标，只能放弃画图
        if (isNaN(truckLat) || isNaN(truckLng)) return;

        // 🌟 3. 匹配起点和终点的视觉坐标
        let startLat = truckLat - 1.5;
        let startLng = truckLng - 1.5;
        let endLat = truckLat + 1.5;
        let endLng = truckLng + 1.5;

        for (let cityKey in CITY_COORDS) {
          if (that.data.senderCity.includes(cityKey)) {
            startLat = CITY_COORDS[cityKey].lat;
            startLng = CITY_COORDS[cityKey].lng;
          }
          if (that.data.receiverCity.includes(cityKey)) {
            endLat = CITY_COORDS[cityKey].lat;
            endLng = CITY_COORDS[cityKey].lng;
          }
        }

        let mapMarkers = [];

        // 📍 标记一：起点
        mapMarkers.push({
          id: 2,
          latitude: startLat,
          longitude: startLng,
          width: 20, height: 20,
          callout: {
            content: ` 起点 `, color: "#FFF", bgColor: "#1C2B33",
            fontSize: 12, padding: 6, borderRadius: 10, display: "ALWAYS", textAlign: "center"
          }
        });

        // 📍 标记二：终点
        mapMarkers.push({
          id: 3,
          latitude: endLat,
          longitude: endLng,
          width: 20, height: 20,
          callout: {
            content: ` 终点 `, color: "#FFF", bgColor: "#FF4D4F",
            fontSize: 12, padding: 6, borderRadius: 10, display: "ALWAYS", textAlign: "center"
          }
        });

        // 📍 标记三：动态位置（如果妥投了，变成绿色勾号）
        let truckContent = isDelivered ? ` ✅ 已送达 ` : ` 🚚 当前位置 `;
        let truckBgColor = isDelivered ? "#07c160" : "#00A0B0";

        mapMarkers.push({
          id: 1,
          latitude: truckLat,
          longitude: truckLng,
          width: 32, height: 32,
          callout: {
            content: truckContent, color: "#FFFFFF", bgColor: truckBgColor,
            fontSize: 13, padding: 8, borderRadius: 12, display: "ALWAYS", textAlign: "center"
          }
        });

        // 〰️ 画线：起点 -> 当前/送达位置 -> 终点
        let mapPolylines = [{
          points: [
            { latitude: startLat, longitude: startLng },
            { latitude: truckLat, longitude: truckLng },
            { latitude: endLat, longitude: endLng }
          ],
          color: "#00CFD6", width: 6, arrowLine: true, borderWidth: 1, borderColor: "#00A0B0"
        }];

        // 🌟 4. 先渲染数据，再自动调焦
        that.setData({
          showMap: true,
          latitude: truckLat,
          longitude: truckLng,
          markers: mapMarkers,
          polylines: mapPolylines
        }, () => {
          const mapCtx = wx.createMapContext('jdMap', that);
          mapCtx.includePoints({
            padding: [100, 60, 100, 60],
            points: [
              { latitude: startLat, longitude: startLng },
              { latitude: truckLat, longitude: truckLng },
              { latitude: endLat, longitude: endLng }
            ],
            success: () => {
              console.log("📍 [地图智能调节] 已自动缩放包含所有关键节点");
            }
          });
        });
      }
    }
  });
},
  toggleTimeline() {
    this.setData({
      isTimelineExpanded: !this.data.isTimelineExpanded
    });
  }
});
const http = require('http')

http.get('http://localhost:8080/otp/routers/default/plan?fromPlace=33.58259,130.36059&toPlace=33.60182,130.41501&time=1:02pm&date=4-14-2019&mode=TRANSIT,WALK&maxWalkDistance=5000&arriveBy=false', (res) => {
  const { statusCode } = res;
  const contentType = res.headers['content-type'];

  let error;
  if (statusCode !== 200) {
    error = new Error('Request Failed.\n' +
                      `Status Code: ${statusCode}`);
  } else if (!/^application\/json/.test(contentType)) {
    error = new Error('Invalid content-type.\n' +
                      `Expected application/json but received ${contentType}`);
  }
  if (error) {
    console.error(error.message);
    // consume response data to free up memory
    res.resume();
    return;
  }

  res.setEncoding('utf8');
  let rawData = '';
  res.on('data', (chunk) => { rawData += chunk; });
  res.on('end', () => {
    try {
      const parsedData = JSON.parse(rawData);
      const timeoptions = { hour: 'numeric', minute: 'numeric'}
      for (let i=0; i<3; i++) {
        console.log('プラン' + (i+1))
        console.log('【概要】')
        console.log('　所要時間: ' + Math.round(parsedData.plan.itineraries[i].duration/60) + '分' + parsedData.plan.itineraries[i].duration%60 + '秒')
        console.log('　開始時刻: ' + new Date(parsedData.plan.itineraries[i].startTime).toLocaleTimeString('ja-JP', timeoptions))
        console.log('　到着時刻: ' + new Date(parsedData.plan.itineraries[i].endTime).toLocaleTimeString('ja-JP', timeoptions))
        console.log('　運賃: ' + parsedData.plan.itineraries[i].fare.fare.regular.cents + '円')
        console.log('')
        console.log('【詳細】')
        for (let j=0; j< parsedData.plan.itineraries[i].legs.length; j++) {
          console.log('　' + new Date(parsedData.plan.itineraries[i].legs[j].startTime) .toLocaleTimeString('ja-JP', timeoptions)
            + '発　' + parsedData.plan.itineraries[i].legs[j].from.name)
          console.log('　' + new Date(parsedData.plan.itineraries[i].legs[j].endTime ).toLocaleTimeString('ja-JP', timeoptions)
            + '着　' + parsedData.plan.itineraries[i].legs[j].to.name)
          console.log('　モード: ' + parsedData.plan.itineraries[i].legs[j].mode)

        }
        console.log('')
      };
    } catch (e) {
      console.error(e.message);
    }
  });
}).on('error', (e) => {
  console.error(`Got error: ${e.message}`);
});

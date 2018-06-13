
#!-*-coding:utf-8 -*-
#@TIME    : 2018/6/13/0013 12:04
#@Author  : Nogo


import requests
import time
import json
from collections import defaultdict


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3355.4 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://exchange.fcoin.com/clearing/trade',
    'TOKEN': 'iONKuCZlA3BHAxNqpDZ2ngx-AAYOcvfEjBId2DKy1m36glP2UfjsXHuae8INo1c6uXh4PabjG0zC3oaxlyEaRQ==',
}

req = requests.Session()
req.cookies.set('__zlcmid', 'mrhPJng2Tm7S5i')
req.cookies.set('_ga', 'GA1.2.442455607.1528631467')
req.cookies.set('_gid', 'GA1.2.1663950489.1528631467')
req.cookies.set('prd-token', '"iONKuCZlA3BHAxNqpDZ2ngx-AAYOcvfEjBId2DKy1m36glP2UfjsXHuae8INo1c6uXh4PabjG0zC3oaxlyEaRQ=="')

req.cookies.set('u', 'ganchu')



tradeList = defaultdict(lambda:None)
nowTime = lambda: int(round(time.time() * 1000))
timestamp = nowTime()
temp_timestamp = None
url = 'https://exchange.fcoin.com/api/web/v1/accounts/trade-finances?hasMore=true&before=%s&limit=100'
stop = False
while not stop:

    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp/1000)))

    if temp_timestamp:
        if temp_timestamp == timestamp:
            break
        else:
            timestamp = temp_timestamp

    rep = req.get(url % timestamp, headers=headers,)
    content = rep.json()
    if content['status'] == 0:
        data = content['data']
        for item in data:
            temp_timestamp = item['created_at']
            if item['type'] == 'Fee':
                currency = item['currency']
                timeArray = time.localtime(temp_timestamp/1000)
                if timeArray.tm_mday == 10:
                    stop = True
                trade = tradeList[timeArray.tm_mday]
                if trade:
                    if currency in trade:
                        trade[currency] += float(item['amount'])
                    else:
                        trade[currency] = float(item['amount'])
                else:
                    tradeList[timeArray.tm_mday] = {currency : float(item['amount'])}
    time.sleep(0.1)
for day,data in tradeList.items():
    print(day,json.dumps(data))



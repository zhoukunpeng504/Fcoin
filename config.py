
#!-*-coding:utf-8 -*-
#@TIME    : 2018/6/11/0011 10:17
#@Author  : Nogo


#秘钥
key = 'ca5ebbf96d8246e2b446ffccd6b3dadf'
secret = '41f1d72cda2245b3b288f6f76a864d1f'


#精度和每次挂单量，如果amount为0， 则为梭哈， 一单卖完 一单买完的套路
btc = {'name': 'btcusdt', 'coin': 'btc', 'price_decimal': 2, 'amount_decimal': 4, 'amount': 0.001}
bch = {'name': 'bchusdt', 'coin': 'bch', 'price_decimal': 2, 'amount_decimal': 4, 'amount': 0.001}
ltc = {'name': 'ltcusdt', 'coin': 'ltc', 'price_decimal': 2, 'amount_decimal': 4, 'amount': 0.001}
eth = {'name': 'ethusdt', 'coin': 'eth', 'price_decimal': 2, 'amount_decimal': 4, 'amount': 0.001}
etc = {'name': 'etcusdt', 'coin': 'etc', 'price_decimal': 2, 'amount_decimal': 4, 'amount': 0.001}
ft = {'name': 'ftusdt', 'coin': 'ft', 'price_decimal': 6, 'amount_decimal': 2, 'amount': 6}
btm = {'name': 'btmusdt', 'coin': 'btm', 'price_decimal': 4, 'amount_decimal': 1, 'min_amount': 5}

#交易对，仅支持以上USDT交易对
symbol = ft

#抱团模式：固定价格刷单(等于0就是市价，大于0固定该价格)
fix_price = 0

#当固定价格有效时,买入前判断市价与固定价的差价，在范围帐内则下单
diff_price = 0.02


#持仓币种最大量
limit_amount = 1000000


#买单超时(s)
delay = 20




#!-*-coding:utf-8 -*-
#@TIME    : 2018/6/11/0011 10:17
#@Author  : Nogo


btc = {'name': 'btcusdt', 'coin': 'btc', 'price_precision': 2, 'amount_precision': 4, 'min_amount': 0.001}
ltc = {'name': 'ltcusdt', 'coin': 'ltc', 'price_precision': 2, 'amount_precision': 4, 'min_amount': 0.001}
eth = {'name': 'ethusdt', 'coin': 'eth', 'price_precision': 2, 'amount_precision': 4, 'min_amount': 0.001}
etc = {'name': 'etcusdt', 'coin': 'etc', 'price_precision': 2, 'amount_precision': 4, 'min_amount': 0.001}
ft = {'name': 'ftusdt', 'coin': 'ft', 'price_precision': 2, 'amount_precision': 0, 'min_amount': 1}
btm = {'name': 'btmusdt', 'coin': 'btm', 'price_precision': 2, 'amount_precision': 1, 'min_amount': 1}


#买单超时(s)
delay = 20

#秘钥
key = ''
secret = ''

#交易对
symbol = ltc

#抱团模式：固定价格刷单(等于0就是市价，大于0固定该价格)
fix_price = 100.04

#当固定价格有效时,买入前判断市价与固定价的差价，在范围帐内则下单
diff_price = 0.02

#★买卖深度前3挂单数量总和
total_amount = 5000

#当★满足时的挂单量
max_amount = 0.5

#当★不满足时的挂单量
min_amount = 0.5

#持仓币种最大量
limit_amount = 3

#暂时无用
ft_base_amount = 0


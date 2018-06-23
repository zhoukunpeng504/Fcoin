# !-*-coding:utf-8 -*-
# @TIME    : 2018/6/11/0011 15:32
# @Author  : Nogo

import math
import time
import logging
from collections import defaultdict
from threading import Thread

from fcoin import Fcoin
from WSS.fcoin_client import fcoin_client
from balance import balance
import config
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

class market_app():
    '''
    订阅数据：历史成交trade,市价ticker
    挂单条件：保存最新50个成交价格，排序取中间30个数据求和平均值与市价比较,差值在diff_price参数范围内则下单
    说明：
        1、运行脚本前手动清空持仓，脚本成交一个买单就按不小于买入价挂出。对挂出的卖单只做状态查询无其他操作。
        2、设置好最大持仓量limit_amount，防止在盘口巨大波动时连续吃单
        3、卖单长时间不成交需要手动清仓
    '''

    def __init__(self):
        self.client = fcoin_client()
        #self.client.stream.stream_depth.subscribe(self.depth)
        #self.client.stream.stream_klines.subscribe(self.candle)
        self.client.stream.stream_ticker.subscribe(self.ticker)      # 订阅市价数据 ，数据写入到self.market_price
        self.client.stream.stream_marketTrades.subscribe(self.trade) # 订阅交易数据，数据写入到self.market_trade_list
        self.fcoin = Fcoin()
        self.fcoin.auth(config.key, config.secret)

        self.buy_price = None  # 买1价
        self.buy_amount = None  # 买1量
        self.sell_price = None  # 卖1价
        self.sell_amount = None  # 卖1量
        self.ts = None  # 深度更新时间

        self.market_price = None  # 市价
        self.market_trade_list = None
        self.total_bids = 0
        self.total_asks = 0

        self.filled_buy_order_list = []
        self.order_list = defaultdict(lambda: None)  #所有订单
        self.buy_order_id = None
        self.dic_balance = defaultdict(lambda: None)
        self.time_order = time.time()

        self.price_list = []
        self.candle_list = []
        self._init_log()


    # 日志初始化
    def _init_log(self):
        self._log = logging.getLogger(__name__)
        self._log.setLevel(level=logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(message)s')  # 格式

        '''
        保存文档
        '''
        handler = logging.FileHandler("app.log")
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        self._log.addHandler(handler)

        '''
        控制台显示
        '''
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self._log.addHandler(console)

    # 精度控制，直接抹除多余位数，非四舍五入
    def digits(self, num, digit):
        site = pow(10, digit)
        tmp = num * site
        tmp = math.floor(tmp) / site
        return tmp


    # 市价
    def ticker(self, data):
        self.ts = time.time()
        self.market_price = data['ticker'][0]

    # 交易
    def trade(self, data):
        self.ts = time.time()
        price = float(data['price'])
        if self.market_trade_list:
            self.market_trade_list.append(price)
        else:
            self.market_trade_list = [price]

        if len(self.market_trade_list) > 100:
            self.market_trade_list.pop(0)


    # 刷单流程
    def process(self):

        if self.market_trade_list and len(self.market_trade_list) < 100:
            self._log.info('成交数据[%s]' % (len(self.market_trade_list)))
            return

        if self.ts and time.time() - self.ts < 10 and self.market_price:
            # 如果当前大盘数据已更新，且更新时间在10秒内，且，查询到大盘价格

            price = self.market_price if config.fix_price == 0 else config.fix_price #交易价格
            '''
            从待下单列表中， 逐个尝试挂卖单
            '''
            success_item_list = []   # 成功挂出的订单
            for item in self.filled_buy_order_list:  # 尝试对卖单进行挂出
                amount = self.digits(item['amount'], config.symbol['amount_precision'])
                price = self.digits(max(item['price'], price), config.symbol['price_precision'])
                order = [amount, price]
                if amount >= config.symbol['min_amount']:
                    success, data = self.fcoin.sell(config.symbol['name'], price, amount)  # 卖
                    if success:
                        success_item_list.append(item)
                        self.order_list[data['data']] = order
                        self._log.info('挂卖单成功[%s:%s]' % (amount, price))


            '''
            从待下单列表中，删除已成功挂出去的卖单
            '''
            for item in success_item_list:
                self.filled_buy_order_list.remove(item)

            keys = []
            for key in self.order_list.keys():
                success, data = self.fcoin.get_order(key)
                if success:
                    state = data['data']['state']
                    if state == 'filled':
                        keys.append([0, key])
                    elif state in ('partial_canceled', 'canceled'):
                        keys.append([1, key])

            '''
            打印卖单的状态
            '''
            for tag, key in keys:
                self.order_list.pop(key)
                if tag == 0:
                    self._log.info('已经成交：' + key)
                else:
                    self._log.info('已经撤单：' + key)


            '''
            不存在已下单的买单。
            '''
            if not self.buy_order_id:
                '''
                查询余额度
                '''
                self.dic_balance = self.get_balance()

                '''
                判断币种持仓量，到设定值停止买入。
                '''
                coin = self.dic_balance[config.symbol['coin']]
                if coin and coin.balance > config.limit_amount:
                    self._log.info('%s余额度达到最大值[%s]' % (config.symbol['coin'], coin.balance))
                    return

                '''
                如果未到设定值，尝试挂买单
                '''
                usdt = self.dic_balance['usdt']
                if usdt:

                    tmp_list = self.market_trade_list.copy()
                    tmp_list.sort()
                    avg = sum(tmp_list[10:-10])/(len(tmp_list)-20)
                    diff = abs(avg - self.market_price)
                    '''
                    如果当前市场价格的平均值 大于设定值，则不下单
                    '''
                    if config.diff_price < diff:
                        self._log.info('固定价格模式差价异常[%-0.2f]' % diff)
                        return

                    '''
                    否则， 下单
                    '''
                    # 如果不固定价格，则按照市价，如果固定就按照固定价
                    price = self.market_price if config.fix_price == 0 else config.fix_price

                    # 根据余额  及 价格，计算下单量
                    if usdt.available > price * config.max_amount:
                        amount = config.max_amount if self.total_bids > config.total_amount and self.total_asks > config.total_amount else config.min_amount
                    else:
                        amount = usdt.available / price

                    # 小数点精度处理
                    amount = self.digits(amount, config.symbol['amount_precision'])

                    # 如果本次下单量大于配置中的最小交易量，则进行交易
                    if amount >= config.symbol['min_amount']:
                        price = self.digits(price, config.symbol['price_precision'])
                        success, data = self.fcoin.buy(config.symbol['name'], price, amount)  # 买
                        if success:
                            self.time_order = time.time()
                            self.buy_order_id = data['data']  # 记录买单的ID
                            self._log.info('挂买单成功[%s:%s]' % (amount, price))
                    # 否则，不交易，并记录LOG
                    else:
                        self._log.info('usdt不足[%s]' % (usdt.available))
                else:
                    self._log.info('查询余额错误')
            else:
                '''
                存在已下单的买单， 查询订单状态
                '''
                success, data = self.fcoin.get_order(self.buy_order_id)
                if success:
                    state = data['data']['state']
                    amount = float(data['data']['filled_amount']) - float(data['data']['fill_fees'])
                    price = float(data['data']['price'])

                    if amount > 0 and state in ('filled', 'partial_canceled'):
                        self.filled_buy_order_list.append({'price': price, 'amount': amount})

                    if state == 'filled':
                        self.buy_order_id = None
                        self._log.info('买单已成交')

                    elif state == 'canceled' or state == 'partial_canceled':
                        self.buy_order_id = None
                        self._log.info('买单已撤单')

                    elif state not in ('pending_cancel'):
                        '''
                        买单 超时， 尝试撤单。
                        '''
                        if time.time() - self.time_order >= config.delay:
                            self.fcoin.cancel_order(self.buy_order_id)
                            self._log.info('%s秒超时撤单' % config.delay)
        else:
            self._log.info('等待WebSocket数据……')

    # 主循环
    def loop(self):

        #配置检查，如果最大挂单量 小于 币种配置最小挂单量  或者最小挂单量小于币种配置最小挂单量，认为配置错误
        if config.max_amount < config.symbol['min_amount'] or config.min_amount < config.symbol['min_amount']:
            self._log.info('max_amount,min_amount ≥ 规定的最小数量[%s]' % (config.symbol['min_amount']))
            return
        # 开始运行
        # 连接到wss服务器
        self.client.start()

        while not self.client.isConnected:
            self._log.info('waitting……')
            time.sleep(1)

        #self.client.subscribe_depth(config.symbol['name'], 'L20')
        #self.client.subscribe_candle(config.symbol['name'], 'M1')

        # 订阅特定币种 价格 及交易信息
        self.client.subscribe_ticker(config.symbol['name'])
        self.client.subscribe_trade(config.symbol['name'])
        while True:
            try:
                self.process()
            except Exception as error:
                self._log.info('未知错误')
            time.sleep(1)

    # 获取余额
    def get_balance(self):
        dic_balance = defaultdict(lambda: None)
        success, data = self.fcoin.get_balance()
        if success:
            for item in data['data']:
                dic_balance[item['currency']] = balance(float(item['available']), float(item['frozen']),
                                                        float(item['balance']))
        return dic_balance

    # # 获取订单
    # def get_orders(self, symbol, states, limit=1):
    #     '''
    #     :param symbol:
    #     :param states: submitted/partial_filled/partial_canceled/canceled/pending_cancel/filled
    #     :return:
    #     '''
    #     success, data = self.fcoin.list_orders(symbol=symbol, states=states, limit=limit)
    #     if success:
    #         return data['data']
    #     else:
    #         print(data)
    #         return None


if __name__ == '__main__':
    run = market_app()
    thread = Thread(target=run.loop)
    thread.start()
    thread.join()
    print('done')

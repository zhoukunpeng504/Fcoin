# !-*-coding:utf-8 -*-
# @TIME    : 2018/6/11/0011 15:32
# @Author  : Nogo

import math
import time
import logging
from collections import defaultdict
from threading import Thread
import fcoin
from balance import Balance
import config
import sys
import traceback
from fcoin.cons import *
import copy
from fcoin.dataapi import DataAPI


reload(sys)
sys.setdefaultencoding("utf-8")


class AutoMarket(object):
    '''
    订阅数据：历史成交trade,市价ticker
    挂单条件：保存最新50个成交价格，排序取中间30个数据求和平均值与市价比较,差值在diff_price参数范围内则下单
    说明：
        1、运行脚本前手动清空持仓，脚本成交一个买单就按不小于买入价挂出。对挂出的卖单只做状态查询无其他操作。
        2、设置好最大持仓量limit_amount，防止在盘口巨大波动时连续吃单
        3、卖单长时间不成交需要手动清仓
    '''

    def __init__(self):

        api = fcoin.authorize(config.key, config.secret)
        self.fcoin_api = api
        currencies = self.fcoin_api.symbols()
        self.symbles = {}
        print "支持的usdt交易币种信息如下："
        for i in currencies.itertuples():
            if i.quote_currency == "usdt":
                self.symbles[i.name] = [i.amount_decimal, i.price_decimal]
        for i, j in self.symbles.items():
            print "币种：%s,价格精度：%s 数量精度:%s" % (i, j[0], j[1])
        if config.symbol["name"] not in self.symbles:
            raise Exception("币种配置错误！！")
        _ = self.symbles[config.symbol["name"]]
        if config.symbol["price_decimal"] > _[1]:
            raise Exception("price_decimal配置错误，允许的范围是1-%s"%_[1])
        if config.symbol["amount_decimal"] > _[0]:
            raise Exception("amount_decimal配置错误，允许的范围是1-%s"%_[0])

        "fix 官方库下单的的bug"

        DataAPI._old_signed_request = DataAPI.signed_request

        def signed_request(self,method,url,**params):
            while 1:
                if url == "orders":
                    url = HTORD%SERVER
                try:
                    result =  DataAPI._old_signed_request(self,method,url,**params)
                    assert  result != None
                except Exception as e :
                    print "调用api%s发生错误！%s,正在重试"%(url,str(e))
                    time.sleep(0.5)
                else:
                    return result

        DataAPI.signed_request = signed_request

        self.buy_order_id = None
        self.filled_buy_order_list = []
        self.order_list = {}
        self._init_log()

    @property
    def real_market_price(self):
        "获取实时大盘价格"
        result = self.fcoin_api.get_ticker(config.symbol["name"])['data']["ticker"][0]
        return result

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

    # 刷单流程
    def process(self):

        price = self.real_market_price if config.fix_price == 0 else config.fix_price  # 交易价格
        price = self.digits(price, config.symbol["price_decimal"])
        '''
         如果不存在已下单的买单，则尝试下买单
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
            如果未到设定持仓量，尝试挂买单
            '''
            usdt = self.dic_balance['usdt']
            if usdt:
                if config.fix_price:
                    diff = abs(price - config.fix_price)
                    '''
                    如果当前市场价格的平均值 大于设定值，则不下单
                    '''
                    if config.diff_price < diff:
                        self._log.info('固定价格模式差价异常[%-0.2f]' % diff)
                        return
                '''
                下单
                '''

                # 根据余额  及 价格，计算下单量,按照配置里面的下单量走
                if usdt.available > price * config.symbol["amount"]:
                    amount = config.symbol["amount"]
                    amount = self.digits(amount, config.symbol['amount_decimal'])
                    result = self.fcoin_api.buy(config.symbol["name"], str(price), str(amount))
                    if result["status"] == 0 and result["data"]:
                        self.time_order = time.time()
                        self.buy_order_id = result['data']  # 记录买单的ID
                        self._log.info('挂买单成功[%s:%s]' % (amount, price))
                else:
                    self._log.info('usdt不足[%s]' % (usdt.available))
            else:
                self._log.info('查询余额错误')
        else:
            '''
            存在已下单的买单， 查询订单状态
            '''
            result = self.fcoin_api.get_order(self.buy_order_id)
            if result["status"] == 0:
                state = result['data']['state']
                amount = float(result['data']['filled_amount']) - float(result['data']['fill_fees'])
                price = float(result['data']['price'])

                if amount > 0 and state in ('filled', 'partial_filled'):
                    self.filled_buy_order_list.append({'price': price,
                                                       'amount': amount})

                if state == 'filled':
                    self.buy_order_id = None
                    self._log.info('买单已成交')

                if state == "partial_filled":
                    self._log.info('买单已部分成交')

                elif state == 'canceled' or state == 'partial_canceled':
                    self.buy_order_id = None
                    self._log.info('买单已撤单')

                elif state not in ('pending_cancel'):
                    '''
                    买单 超时， 尝试撤单。
                    '''
                    if time.time() - self.time_order >= config.delay:
                        self.fcoin_api.cancel_order(self.buy_order_id)
                        self._log.info('%s秒超时尝试撤单' % config.delay)

        '''
        从已下单列表中， 逐个尝试把买到的币挂出去卖掉
        '''
        success_item_list = []  # 成功挂出的订单
        for item in self.filled_buy_order_list:
            amount = self.digits(item['amount'], config.symbol['amount_decimal'])
            price = self.digits(max(item['price'], price), config.symbol['price_decimal'])
            order = [amount, price]
            result = self.fcoin_api.sell(config.symbol['name'], str(price), str(amount))  # 卖
            if result["status"] == 0:
                success_item_list.append(item)
                self.order_list[result["data"]] = order
                self._log.info('挂卖单成功[%s:%s]' % (amount, price))

        '''
        从待下单列表中，删除已成功挂出去的卖单
        '''
        for item in success_item_list:
            self.filled_buy_order_list.remove(item)

        keys = []
        for key in self.order_list.keys():
            result = self.fcoin_api.get_order(key)
            if result["status"] == 0:
                state = result['data']['state']
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
                self._log.info('卖单已经成交：' + key)
            else:
                self._log.info('卖单已经撤单：' + key)

    # 主循环
    def loop(self):
        # 开始运行
        while True:
            try:
                self.process()
            except Exception as error:
                print str(error)
                traceback.print_exc()
                self._log.info('未知错误')
            time.sleep(1)

    # 获取余额
    def get_balance(self):
        dic_balance = defaultdict(lambda: None)
        data = self.fcoin_api.get_balance()
        for item in data['data']:
            dic_balance[item['currency']] = \
                Balance(float(item['available']), float(item['frozen']),float(item['balance']))
        return dic_balance


if __name__ == '__main__':
    run = AutoMarket()
    thread = Thread(target=run.loop)
    thread.start()
    thread.join()
    print('start~~...')

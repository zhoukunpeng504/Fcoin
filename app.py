
#!-*-coding:utf-8 -*-
#@TIME    : 2018/6/10/0010 11:20
#@Author  : Nogo

import time
import math
from threading import Thread
import logging
from collections import defaultdict


from fcoin import Fcoin
from balance import balance
from db import mongodb
import config
class app():
    def __init__(self):
        self.key = config.key
        self.secret = config.secret

        self._log = None
        self.dic_balance = defaultdict(lambda: None)
        self.order_list = defaultdict(lambda: None)
        self.stop = False

        self.buy_order_id = None
        self.sell_order_id = None
        self.time_order = time.time()

        self.db = mongodb()
        self.fcoin = Fcoin()
        self.fcoin.auth(self.key, self.secret)
        self._init_log()

    def _init_log(self):
        self._log = logging.getLogger(__name__)
        self._log.setLevel(level=logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(message)s')

        handler = logging.FileHandler("app.log")
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        self._log.addHandler(handler)


        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self._log.addHandler(console)

    #查询订单
    def get_orders(self, symbol, states, limit=1):
        '''
        :param symbol:
        :param states: submitted/partial_filled/partial_canceled/canceled/pending_cancel/filled
        :return:
        '''
        success, data = self.fcoin.list_orders(symbol=symbol, states=states, limit=limit)
        if success:
            return data['data']
        else:
            print(data)
            return None
    #获取余额
    def get_blance(self):
        dic_blance = defaultdict(lambda: None)
        success, data = self.fcoin.get_balance()
        if success:
            for item in data['data']:
                dic_blance[item['currency']] = balance(float(item['available']), float(item['frozen']),float(item['balance']))
        return dic_blance
    #精度
    def digits(self,num, digit):
        site = pow(10, digit)
        tmp = num * site
        tmp = math.floor(tmp) / site
        return tmp
    #过程
    def process(self):
        if self.buy_order_id is None and self.sell_order_id is None:
            success, data = self.fcoin.get_market_depth('L20', config.symbol)
            if success:
                bids = data['data']['bids']  # 买
                asks = data['data']['asks']  # 卖
                total_bids = 0
                total_asks = 0

                for i in range(3):
                    total_bids += bids[2*i - 1]
                    total_asks += asks[2*i - 1]

                buy_price = bids[0]
                buy_amount = bids[1]

                sell_price = asks[0]
                sell_amount = asks[1]

                usdt = self.dic_balance['usdt']
                btc = self.dic_balance['btc']
                amount = 0
                price = 0
                order = None
                if btc:
                    r = self.db.get('buy',buy_price)
                    if r:
                        amount = self.digits(r['amount'], 4)
                        order = {'id': r['_id'], 'amount': amount, 'price': r['price']}

                    #if btc.available >= 0.001 and amount < 0.001:
                    #    amount = self.digits(btc.available, 4)

                    if amount >= 0.001:
                        price = self.digits(sell_price, 2)
                        success, data = self.fcoin.sell(config.symbol, price, amount)#卖
                        if success:
                            self.time_order = time.time()
                            self.sell_order_id = data['data']
                            self._log.info('挂卖单成功[%s:%s]' % (amount, price))
                            if order:
                                self.order_list[self.sell_order_id] = order
                            return
                if usdt:

                    if btc and btc.available >= config.limit_account:
                        self.dic_balance = self.get_blance()
                        self._log.info('余额度超过%s个BTC,停止买入[%s]' % (config.limit_account, btc.available))
                        return

                    if usdt.available > buy_price * config.max_amount:
                        amount = config.max_amount if total_bids > config.total_amount and total_asks > config.total_amount else config.min_amount
                    else:
                        amount = usdt.available/buy_price
                    amount = self.digits(amount, 4)
                    price = self.digits(buy_price, 2)
                    success, data = self.fcoin.buy(config.symbol, price, amount)#买
                    if success:
                        self.time_order = time.time()
                        self.buy_order_id = data['data']
                        self._log.info('挂买单成功[%s:%s]' % (amount, price))

                else:
                    self._log.info('余额错误')
                    self.dic_balance = self.get_blance()
        else:
            if self.sell_order_id:
                success, data = self.fcoin.get_order(self.sell_order_id)
                if success:
                    state = data['data']['state']
                    amount = float(data['data']['filled_amount'])

                    if state in ('filled','partial_canceled'):
                        order = self.order_list[self.sell_order_id]
                        if order:
                            self.db.update( order['id'], amount)

                    if state == 'filled':
                        self.sell_order_id = None
                        self._log.info('卖单已成交')
                        self.dic_balance = self.get_blance()

                    elif state == 'canceled' or state == 'partial_canceled':
                        self.sell_order_id = None
                        self._log.info('卖单已撤单')
                        self.dic_balance = self.get_blance()

                    elif state not in ('pending_cancel'):
                        if time.time() - self.time_order >= 15:
                            self.fcoin.cancel_order(self.sell_order_id)
                            self._log.info('15秒超时撤单')

            if self.buy_order_id:
                success, data = self.fcoin.get_order(self.buy_order_id)
                if success:
                    state = data['data']['state']
                    amount = float(data['data']['filled_amount']) - float(data['data']['fill_fees'])
                    price = float(data['data']['price'])

                    if amount > 0 and state in ('filled','partial_canceled'):
                        self.db.add('buy', price, amount)

                    if state == 'filled':
                        self.buy_order_id = None
                        self._log.info('买单已成交')
                        self.dic_balance = self.get_blance()

                    elif state == 'canceled' or state == 'partial_canceled':

                        self.buy_order_id = None
                        self._log.info('买单已撤单')
                        self.dic_balance = self.get_blance()

                    elif state not in ('pending_cancel'):
                        if time.time() - self.time_order >= 15:
                            self.fcoin.cancel_order(self.buy_order_id)
                            self._log.info('15秒超时撤单')

    def task(self):

        dic = self.get_orders(config.symbol, 'submitted', 20)
        for item in dic:
            self.fcoin.cancel_order(item['id'])
        self.dic_balance = self.get_blance()

        self.loop()

    def loop(self):
        while not self.stop:
            self.process()
            time.sleep(1)



if __name__ == '__main__':
    run = app()
    thread = Thread(target=run.task)
    thread.start()
    thread.join()
    print('done')




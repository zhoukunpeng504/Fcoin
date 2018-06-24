
#!-*-coding:utf-8 -*-
#@TIME    : 2018/6/11/0011 15:36
#@Author  : Nogo

import logging
import json
from WebSocketClient import Connection
from stream import stream
log = logging.getLogger(__name__)

def is_connected(func):
    def wrapped(self, *args, **kwargs):
        if self._client and self.isConnected:
            return func(self, *args, **kwargs)
        else:
            log.error("Cannot call %s() on unestablished connection!",func.__name__)
            return None
    return wrapped

class fcoin_client(object):

    def __init__(self, log_level= logging.DEBUG):
        self._client = Connection(
            url='wss://api.fcoin.com/v2/ws',
            onOpen=self._onOpen,
            onMessage=self._onMessage,
            onClose=self._onClose,
            onError=self._onError,
            log_level=log_level,
            reconnect_interval=10
        )
        self.stream = stream()
        self.channel_config = []
        self.channel_directory = {}
        self._response_handlers = {}
        self._data_handlers = {'depth': self.stream.raiseDepth,       # 深度查询
                               'candle': self.stream.raiseKline,
                               'ticker': self.stream.raiseTicker,     # 行情
                               'trade': self.stream.raiseMarketTrades}

    @property
    def isConnected(self):
        return self._client.isConnected.is_set()

    def start(self):
        self._client.start()

    def _onOpen(self):
        if len(self.channel_config) > 0:
            for item in self.channel_config:
                self._subscribe(item)

    def _onMessage(self, msg):
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            # Something wrong with this data, log and discard
            return
        if isinstance(data, dict):
            if 'topics' in data:
                self._response_handler(data['topics'])
            elif 'type' in data:
                type = data.pop('type')
                self._data_handler(type, data)


        else:
            pass
    def _onClose(self):
        print "has cossed"
        pass

    def _onError(self, errorMsg):
        print "error",errorMsg
        pass

    @is_connected
    def send(self, data):
        print(data)
        self._client.send(data)

    @is_connected
    def _subscribe(self,channel):
        #{"cmd":"sub","args":["ticker.btcusdt"],"id":"1"}

        if channel not in self.channel_config:
            self.channel_config.append(channel)

        if not isinstance(channel, list):
            channel = [channel]
        q = {'cmd': 'sub', 'args': channel, 'id': '1'}
        payload = json.dumps(q)
        self.send(payload)

    def subscribe_depth(self, symbol, level):
        channel = 'depth.%(level)s.%(symbol)s' % {'symbol': symbol, 'level': level}
        self._subscribe(channel)

    def subscribe_ticker(self, symbol):
        channel = 'ticker.%(symbol)s' % {'symbol': symbol}
        self._subscribe(channel)

    def subscribe_candle(self, symbol, resolution):
        channel = 'candle.%(resolution)s.%(symbol)s' % {'symbol': symbol, 'resolution': resolution}
        self._subscribe(channel)

    def subscribe_trade(self, symbol):
        channel = 'trade.%(symbol)s' % {'symbol': symbol}
        self._subscribe(channel)

    def _system_handler(self, data):
        pass

    def _response_handler(self, data):
        # {"id":"1","type":"topics","topics":["depth.L20.btcusdt"]}
        # {"id":"1","type":"topics","topics":["depth.L20.btcusdt","ticker.btcusdt"]}
        for item in data:
            channel = item.split('.')[0]
            if channel:
                self.channel_directory[channel] = self._data_handlers[channel]

    def _data_handler(self, type, data):
        try:
            channel = type.split('.')[0]
            self.channel_directory[channel](data)
        except KeyError:
            pass

def t(data): #订阅数据回调函数
    print(data)

if __name__ == '__main__':
    c = fcoin_client()
    c.stream.stream_depth.subscribe(t) #订阅
    c.start()
    import time
    time.sleep(5)
    c.subscribe_trade('ftusdt')

    while 1:
        pass
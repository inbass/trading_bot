
# coding: utf-8

# In[1]:


# import
import requests
import pymongo
from pymongo import MongoClient
import time
import json
import pprint
import pandas as pd
from pandas.io.json import json_normalize
from datetime import timezone, timedelta, datetime
import logging
import logging.handlers
import pickle
logger = logging.getLogger("crumbs")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s > %(message)s')
file_max_bytes = 10 * 1024 * 1024
fileHandler = logging.handlers.RotatingFileHandler(filename='./CoinTracker_Binance_Past.log', maxBytes=file_max_bytes, backupCount=10)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)
logger.info("CoinTracker_Binance_Past Re-started")


# In[2]:


base_url = 'https://api.binance.com'
symbol = 'BTCUSDT'
apis = {'ping':{'url': '/api/v1/ping','param':0},
        'time':{'url':'/api/v1/time','param':0},
        'exchangeInfo':{'url':'/api/v1/exchangeInfo','param':0},
        'depth':{'url':'/api/v1/depth','param':{'symbol':symbol}},
        'trades':{'url':'/api/v1/trades','param':{'symbol':symbol}},
        'aggTrades':{'url':'/api/v1/aggTrades','param':{'symbol':symbol}},
        'klines':{'url':'/api/v1/klines','param':{'symbol':symbol,'interval':'1m'}},
        '24hr':{'url':'/api/v1/ticker/24hr','param':{'symbol':symbol}},
        'price':{'url':'/api/v1/ticker/price','param':{'symbol':symbol}},
        'bookTicker':{'url':'/api/v3/ticker/bookTicker','param':{'symbol':symbol}},
       }
url_db = 'mongodb://mongo-7a3e43c9-1.bf9bfd39.cont.dockerapp.io:32794'
symbols = ['BTCUSDT','ETHUSDT','NEOUSDT','BNBUSDT','LTCUSDT','BCCUSDT']
intervals = ['1m','3m','5m','15m','30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']


# In[3]:


def kline_past(api_name,symbol,interval,etime,db):
    # 각 symbol마다, 각 interval마다 항상 최신 2개를 불러와서 opentime 기준으로 index찾은 다음 overwrite 하면 됨
    now = etime
    etime = etime
    li = []
    while 1:
        time.sleep(1)
        # Load candlestick
        param = {'symbol':symbol,'interval':interval,'limit':500,'endTime':etime}
        url_api = base_url+apis[api_name]['url']
        r = requests.get(url_api,params=param)
        klines = r.json()
        count = len(klines)
        if count<1:
            logger.info('{symbol}_{interval} : no more klines before {etime}.'.format(symbol=symbol,interval=interval,etime=etime))
            break
        else:
            logger.info('{symbol}_{interval} : {count} klines are found before {etime}.'.format(symbol=symbol,interval=interval,etime=etime,count=str(count)))            
        # # Update Klines
        for idx,kline in enumerate(klines):
            k = {}
            # {o_time:opentime,o_price:open,...}
            k['o_t'] = kline[0]
            k['o_p'] = kline[1]
            k['h_p'] = kline[2]
            k['l_p'] = kline[3]
            k['c_p'] = kline[4]
            k['v'] = kline[5]
            k['c_t'] = kline[6]
            k['qa_v'] = kline[7]
            k['n_t'] = kline[8]
            k['ta_v'] = kline[9]
            k['tq_v'] = kline[10]
            k['i'] = kline[11]
            k['T'] = now
            k['clsd'] = 1
            if idx==0: etime = int(k['o_t'])-1
            li.append(k)
    result = sorted(li, key=lambda k: k['o_t']) 
    return result


# In[4]:


# past klines update
try:
    latest_bulk_time = int(time.time())*1000
    client = MongoClient(url_db)
    # Previous Binance DB Delete
    client.drop_database('Binance')
    db = client.Binance
    api_name='klines'
    latest_time={}
    for symbol in symbols:        
        for interval in intervals:
            # DB & collection define
            col_name = api_name+'_'+symbol+'_'+interval
            col = db[col_name]
            # past klines update
            list_to_update = kline_past(api_name=api_name,symbol=symbol,interval=interval,etime=latest_bulk_time,db=db)
            col.insert_many(list_to_update)
            count = len(list_to_update)
            logger.info('{symbol}_{interval} : {count} klines are inserted.'.format(symbol=symbol,interval=interval,etime=latest_bulk_time,count=str(count)))            
            latest_time[symbol+'_'+interval]= latest_bulk_time
    with open('latest_time.txt', 'w') as outfile:  
        json.dump(latest_time, outfile)
    client.close()
except Exception as e:
    logger.exception('error')


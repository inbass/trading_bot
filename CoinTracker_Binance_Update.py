
# coding: utf-8

# In[ ]:


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
fileHandler = logging.handlers.RotatingFileHandler(filename='./CoinTracker_Binance_Update.log', maxBytes=file_max_bytes, backupCount=10)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)
logger.info("CoinTracker_Binance_Update Re-started")


# In[ ]:


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

s_intervals = ['1m','3m','5m']
m_intervals = ['15m','30m', '1h', '2h']
l_intervals = ['4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']


# In[ ]:


# all coin (s_intervals) : 10초에 한번 kline update =  2w * 6회/min * 6 coins *  3 intervals = 216 weight/min
# all coin (l_intervals) : 1분에 한번 kline update = 2w * 1회/min * 6 coins * 12 intervals = 144 weight/min


# In[ ]:


def kline_update(api_name,symbol,interval,db,stime):
    # 각 symbol마다, 각 interval마다 항상 최신 2개를 불러와서 opentime 기준으로 index찾은 다음 overwrite 하면 됨
    # DB & collection define
    col_name = api_name+'_'+symbol+'_'+interval
    col = db[col_name]
    # # Load candlestick
    param = {'symbol':symbol,'interval':interval,'startTime':stime}
    url_api = base_url+apis[api_name]['url']
    r = requests.get(url_api,params=param)
    now = int(time.time()*1000)
    klines = r.json()
    latest_time = stime
    count = len(klines)
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
        if idx<(len(klines)-1): 
            k['clsd'] = 1
        else: 
            k['clsd'] = 0
            latest_time = k['o_t']
        # # db update, upsert=True
        col.update_one({'o_t': k['o_t']},{"$set": k},upsert=True)
    if count > 0:
        logger.info('{count} klines inserted. db : {col_name} until {latest_time}'.format(count = str(count),col_name=col_name,latest_time=datetime.fromtimestamp(latest_time/1000)))
    return latest_time


# In[ ]:


# kline update continuously
period = 0
count = 0
time_file = 'latest_time.txt'
while 1:
    try:
        time.sleep(period)
        start = time.time()
        etime = int(start*1000)
        with open(time_file,'r') as f:
            latest_time = json.load(f)
        count+=1
        client = MongoClient(url_db)
        db = client.Binance
        # short interval every 10 sec
        for symbol in symbols:        
            for interval in s_intervals:        
                latest_time[symbol+'_'+interval] = kline_update(api_name='klines',symbol=symbol,interval=interval,db=db,stime=latest_time[symbol+'_'+interval])

        # midium interval every 1 min
        if count%6 == 0:
            for symbol in symbols:        
                for interval in m_intervals:        
                    latest_time[symbol+'_'+interval] = kline_update(api_name='klines',symbol=symbol,interval=interval,db=db,stime=latest_time[symbol+'_'+interval])
        
        # long interval every 1 hour
        if count%360 == 0:
            for symbol in symbols:        
                for interval in l_intervals:        
                    latest_time[symbol+'_'+interval] = kline_update(api_name='klines',symbol=symbol,interval=interval,db=db,stime=latest_time[symbol+'_'+interval])

        client.close()
        end = time.time()
        duration = end-start
        logger.info('api request duration : {duration}'.format(duration=end-start))
        with open(time_file, 'w') as outfile:  
            json.dump(latest_time, outfile)
        period = int(10-duration)
        if period < 1: period = 0
#         if count > 10: break
    except Exception as e:
        logger.exception('error')
        continue


# In[ ]:


## rate limit : 1200/min
## 24hr rate : 243 / min


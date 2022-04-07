from re import A
import requests
import pyupbit

from urllib.parse import urlencode
from time import sleep
import pandas
import hashlib
from CoinUtill import *
from Log import *
from upbit.client import Upbit
from datetime import datetime, timedelta
#코인관련 정보 클래스


class CoinEvent:

    #현재 보유잔고 
    def get_myBalance(self):

        # 유틸값 가져옴 
        utilInfo = CoinUtill()

        headers  = utilInfo.get_authHeader()
        requestURL = utilInfo.get_requestURL()

        # 통신요청 
        res = requests.get(requestURL+'accounts', headers=headers)
        return res.json()

    #현재 나의 코인별 수익정보 
    def get_myProfitInfo(self,items):

         coinNm = str(items["unit_currency"])+"-"+str(items["currency"])
         #print(coinNm)
         curPrice = float(CoinEvent.get_cur_coin_price(self,coinNm))
         buyPrice = float(items["avg_buy_price"])
         profit   = curPrice-buyPrice
         profitPercent = round((profit/buyPrice)*100,2)

         profitInfo = {
             "coinName"      : coinNm,
             "curPrice"      : curPrice,
             "buyPrice"      : buyPrice,
             "profit"        : profit,
             "profitPercent" : profitPercent
         }

         return profitInfo

    def getMyProfit(self, coinName):
        #현재 내 보유목록 조회
        myWallet = self.get_myBalance()      
        #print(myWallet) 
        for myItem in myWallet:
            #KRW 붙어야함 
            if(str(myItem["unit_currency"])+"-"+str(myItem["currency"]) == coinName):
                
                coinNm = str(myItem["unit_currency"])+"-"+str(myItem["currency"])
                #print(coinNm)
                curPrice = float(CoinEvent.get_cur_coin_price(self,coinNm))
                buyPrice = float(myItem["avg_buy_price"])
                profit   = curPrice-buyPrice
                profitPercent = round((profit/buyPrice)*100,2)
                balance = float(myItem["balance"])

                profitInfo = {
                    "coinName"      : coinNm,
                    "curPrice"      : curPrice,
                    "buyPrice"      : buyPrice,
                    "profit"        : profit,
                    "profitPercent" : profitPercent,
                    "balance"       : balance
                }
                return profitInfo


    #코인 티커의 현재가 조회
    def get_cur_coin_price(self, coinName):
        log = Log().initLogger()

        try:
            price = pyupbit.get_current_price([coinName])
        except Exception as Err:
            #print('[[[[[[Error]]]]]] get_cur_coin_price Error>>>'+str(Err))
            log.debug('[[[[[[Error]]]]]] get_cur_coin_price Error>>>'+str(Err))
        return price

    #거래량 차이 확인
    def get_diff_vol(self, coinName,interval,count):
        #봉의 정보 
        df = pyupbit.get_ohlcv(coinName, interval=interval, count=count)
        #sleep(0.1)
        #거래량 차이만 추림
        diffVolume = df["volume"].diff()

        log = Log().initLogger()
        #log.debug('서칭 코인>>>'+coinName)
        #log.debug('탕스>>>'+str(diffVolume))
        #log.debug("차이>>"+str(diffVolume.iloc[-1] + diffVolume.iloc[-2]))

        # print('서칭 코인>>>'+coinName)
        # print('탕스>>>'+str(diffVolume))
        #print("서칭 코인! >>>"+coinName)
        #print("차이>>"+str(diffVolume.iloc[-1] + diffVolume.iloc[-2]))
        return diffVolume.iloc[-1] + diffVolume.iloc[-2]

    #당일 고,저,시,종가 확인
    def get_cur_info(self,coinName):
        preDiffRange = 0
        dfPreAndCur = pyupbit.get_ohlcv(coinName, count=2)
        #sleep(2)
        coinInfo ={}

        log = Log().initLogger()
        #print(dfPreAndCur)
        try:
            openPrice  = dfPreAndCur.iloc[1]["open"]
            highPrice  = dfPreAndCur.iloc[1]["high"]
            lowPrice   = dfPreAndCur.iloc[1]["low"]
            closePrice = dfPreAndCur.iloc[1]["close"]
            volume     = dfPreAndCur.iloc[1]["volume"]
            value      = dfPreAndCur.iloc[1]["value"]

            #딕셔너리로 담고 리턴
            coinInfo = {
                "coinName"   : coinName,
                "openPrice"  : openPrice,
                "highPrice"  : highPrice,
                "lowPrice"   : lowPrice,
                "closePrice" : closePrice,
                "volume"     : volume,
                "value"      : value
            }
        except Exception as Err:
            #print('[[[[[[Error]]]]]] get_cur_info Error>>>'+str(Err))
            log.debug('[[[[[[Error]]]]]] get_cur_info Error>>>'+str(Err))
        return coinInfo        

    #현재 총알 얼마나 있는지 확인
    def getMyChongal(self):
        
        #현재 내 잔고
        myWallet = self.get_myBalance()       
        myChongal = myWallet[0]["balance"]

        return myChongal


    #이미 보유 코인인지 확인
    def checkBuyCoin(self,coinName):
        
        hasFlag = False

        #현재 내 보유목록 조회
        myWallet = self.get_myBalance()      
        #print(myWallet) 
        for myItem in myWallet:
            #KRW 붙어야함 
            if(str(myItem["unit_currency"])+"-"+str(myItem["currency"]) == coinName):
                print('이미 보유한 코인이다!!')
                hasFlag = True
                return hasFlag

        return hasFlag

    #보유자산 전부매도
    def allSelCoin(self):
        log = Log().initLogger()
        log.debug("전량매도!")

        #print("전량매도!")
        myWallet = self.get_myBalance()       
       
        for myItem in myWallet:
            #원화 빼고 전량 매도 
            if(myItem["currency"] != "KRW") :
                self.buyAndGazzza('KRW-'+myItem["currency"],"ask",myItem["balance"],0,"market")

    #직전 RSI 차이 
    def get_pre_RIS_val(self,coinName,minuteType,index,index2):
        
        coinPricecInfo = pyupbit.get_ohlcv(coinName, interval=minuteType)
        #print("RSI 차이2>>>"+str(coinPricecInfo))
        before_coin_RIS = self.colculrate_rsi(coinPricecInfo, 14)
        #5분봉기준 rsi 차이
        #print("분봉차이1----->>>"+before_coin_RIS[index])
        #print("분봉차이2----->>>"+before_coin_RIS[index2])

        return before_coin_RIS[index] - before_coin_RIS[index2]

    #주문 (매수 / 매도)
    def buyAndGazzza(self, coinName, sideGubun, vol, price, ord_type):   
         # 유틸값 가져옴 
        utilInfo = CoinUtill()

        headers    = utilInfo.get_authHeader()
        requestURL = utilInfo.get_requestURL()
        access_key = utilInfo.get_accessKey()
        secret_key = utilInfo.get_secretKey()
        
        # print('coinName>>>'+coinName)
        # print('sideGubun>>>'+sideGubun)
        # print('vol>>>'+str(vol))
        # print('price>>>'+str(price))
        # print('ord_type>>>'+ord_type)
        query = {}

        if(sideGubun == "bid"):
            #매수
            query = {
                'market'   : coinName
                ,'side'    : sideGubun #bid 매수, ask 매도 
                ,'price'   : price # 시장가에서는 주문투입 가격만큼삼 ->5000원 어치 시장가 
                ,'ord_type': ord_type, #price 시장가주문 매수, market 시장가 주문 매도 
            }
        else:
            #매도
            query = {
                'market': coinName,
                'side': sideGubun,
                'volume': vol, #수량 
                'ord_type': ord_type,
            }

        query_string = urlencode(query).encode()

        #해쉬값으로 변경 
        m = hashlib.sha512()
        m.update(query_string)
        query_hash = m.hexdigest()

        #최종 request 값 설정 
        payload = {
            'access_key': access_key,
            'nonce': str(uuid.uuid4()),
            'query_hash': query_hash,
            'query_hash_alg': 'SHA512',
        }

        jwt_token = jwt.encode(payload, secret_key)
        authorize_token = 'Bearer {}'.format(jwt_token)
        headers = {"Authorization": authorize_token}

        res = requests.post(requestURL + "orders", params=query, headers=headers)
        log = Log().initLogger()
        log.debug(res.json())
        #print(res.json())

#지금까지 거래내역 리스트 뽑아오기 
    def getMyPaymentList(self):

        # 유틸값 가져옴 
        utilInfo = CoinUtill()        
        
        access_key = utilInfo.get_accessKey()
        secret_key = utilInfo.get_secretKey()

        curTime = (datetime.today()).strftime("%Y%m%d")+str("0900")
        beforeTime = (datetime.today() - timedelta(1)).strftime("%Y%m%d")+str("0900")
        
        #upbit.client 라는 것으로 추출 -> uuid 빼내서 재요청해야 정상적인 값을 가져온다,.  
        client = Upbit(access_key, secret_key) 
        orders = client.Order.Order_info_all(page=1, limit=100, states=["done", "cancel"])['result'] 
        df = pandas.DataFrame(orders)

        #전체 주문 History 요청 -> 요청폼 만들고 
        _order_info_all = []


        page = 1
        while True:
                orders = client.Order.Order_info_all(page=page, limit=100, states=["done", "cancel"])['result']
                _order_info_all = _order_info_all + orders
                page += 1
                if len(orders) < 100:
                    break
        _order_info_all = [order for order in _order_info_all if order['trades_count'] > 0]
        
        order_history_df = pandas.DataFrame(columns=["주문시간", "마켓", "종류", "거래수량", "거래단가", "거래금액", "수수료", "정산금액"])

        # 개별 주문에 대한 Detailed info 요청 및 업데이트 -> 실제요청
        for i, order in enumerate(_order_info_all):
                detailed_order = client.Order.Order_info(uuid=order['uuid'])['result']
                
                #2022-03-19T21:15 -> 202203192115
                #202203190900 <= ??? <= 202203200900 범위만 
                operDate = detailed_order["created_at"][0:16].replace("-","").replace("T","").replace(":","")
                
                #전일9시 - 익일9시까지
                if(operDate >= beforeTime  and operDate <= curTime):
                #if(operDate >= '202203180900' and operDate <= '202203190900'):

                    if 'trades' in detailed_order and detailed_order['trades']:
                        df_trades = pandas.DataFrame(detailed_order['trades'])
                        df_trades = df_trades.astype({'funds': float,
                                                    'price': float,
                                                    'volume': float})
                        fund = df_trades['funds'].sum()
                        trading_price = df_trades['price'].sum() / detailed_order['trades_count']
                        trading_volume = df_trades['volume'].sum()
                        order['fund'] = fund
                        order['trading_price'] = trading_price
                        order['trading_volume'] = trading_volume
                        if order['side'] == 'ask':  # 매도시 최종금액 = 정산금액 - 수수료
                            order['executed_fund'] = order['fund'] - float(order['paid_fee'])
                        else:  # 매수시 최종금액 = 정산금액 + 수수료
                            order['executed_fund'] = order['fund'] + float(order['paid_fee'])
                    # single dict to df로 변환
                    df = pandas.DataFrame([order])
                    df.loc[(df.side == 'bid'), 'side'] = '매수'
                    df.loc[(df.side == 'ask'), 'side'] = '매도'

                    df.drop(['uuid', 'ord_type', 'price', 'state', 'trades_count', 'volume', 'executed_volume',
                            'remaining_volume', 'reserved_fee', 'remaining_fee', 'locked'], axis=1, inplace=True)
                    df.rename(columns={'side': '종류', 'trading_price': '거래단가', 'market': '마켓', 'created_at': '주문시간',
                                    'paid_fee': '수수료', 'fund': '거래금액', 'trading_volume': '거래수량',
                                    'executed_fund': '정산금액'}, inplace=True)
                    df = df.reindex(columns=['주문시간', '마켓', '종류', '거래수량', '거래단가', '거래금액', '수수료', '정산금액'])
                    #df['주문시간'] = pandas.to_datetime(df['주문시간'])
                    df = df.astype({'수수료': float})
                    
                    order_history_df = pandas.concat([order_history_df, df], ignore_index=True)
                    order_history_df.sort_values(by=['마켓'])
                    #df.to_excel(tomorrowTime+".xlsx") 
                    
                #curTime 이전으로 가면, 그때까지 값 리턴
                elif(operDate <beforeTime):
                        order_history_df.to_excel("손익결과_"+beforeTime+"_"+curTime+".xlsx")
                        return
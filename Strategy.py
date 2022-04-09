import pyupbit
from datetime import datetime, timedelta
from CoinEvent import *
from CoinUtill import CoinUtill
import asyncio
import pandas
#코인전략
#1.전일의 고가와 저가의 차이인 Range 를 구한다. (Range = 전일고가- 전일저가)
#2.당일 "장중 가격 > 당일시가 + Range * K" 를 만족하는 시점에 매수한다. (K는 0~1 사이의 값으로 가장 효율적인 값을 찾아야 한다.)
#3.익일 시가에 매도한다.

class Strategy:

    #전일 고가 - 전일 저가 = Range값 구하기
    #interval 옵션 분5 5분봉 count는 영업일 기준일자 가져올 날짜순
    #어제 , 오늘 시,고,저,종가 확인 -> 어제 고가 저가 비교하기 위해서 count 2     
    def get_pre_Range(self,coinName):
        preDiffRange = 0
        dfPreAndCur = pyupbit.get_ohlcv(coinName, count=2)
        preHighPrice =  dfPreAndCur.iloc[0]["high"]
        preLowPrice  = dfPreAndCur.iloc[0]["low"]
        preDiffRange = preHighPrice - preLowPrice

        return preDiffRange

    #장중 가격 > 당일시가 + Range * K 계산
    #역산으로 K값 추출하고 그 바탕으로 기준값 리턴
    def get_Basic_Price(self,coinName,Range,curPrice):
        
        #해당코인의 현재가 정보추출
        curInfo = CoinEvent.get_cur_info(self,coinName)
        
        openPrice = curInfo["openPrice"]
        
        #절대값 -> 소숫점 짜르기
        Kcalculate = self.get_Kvalue(coinName)
        #kval = round(Kcalculate,1)
        #고정값으로 할때
        #kval = 0.5
        basicPriceValue = openPrice + (Range * Kcalculate)

        return basicPriceValue

    def get_Kvalue(self,coinName):

        #K값 20일치 종목 데이터
        #k =  1 - (절대값 (시가) - 종가) / 고가 - 저가
        #해당코인의 현재가 정보추출
        df = pyupbit.get_ohlcv(coinName,"day",count=20)
        #print(df)
        kvalue = 1 - (abs(df['open'] - df['close']) / (df['high'] - df['low']))
        #추세 평균값
        #print(round(kvalue.mean(),0))
        
        avgKvalue = round(kvalue.mean(),1)
        return avgKvalue
        
#RSI 지표계산 
    #RSI 30이하 - 매수 , 70이상 - 매도
    #* RSI = A / (A+B) x 100
    #- A : N일간의 주가 상승폭의 합계 14일 
    #- B : N일간의 주가 하락폭의 합계 

    #해당코인 14일간 종가기준 RSI지수 구하기
    def colculrate_rsi(self,ohlc: pandas.DataFrame, period: int = 14): 
        #14일간의 종가에 대한, 차이 diff()함수를 통해 구하고, 양 / 음 나눠서 각각 데이터 프레임에 저장
        delta = ohlc["close"].diff() 
        ups, downs = delta.copy(), delta.copy()
        ups[ups < 0] = 0 
        downs[downs > 0] = 0

        #지수 이동평균 지수 보정값 구하고 -> 잘모르겠음 퍼옴
        AU = ups.ewm(com = period-1, min_periods = period).mean()
        AD = downs.abs().ewm(com = period-1, min_periods = period).mean()

        RS = AU/AD 
        #데이터 프레임값으로 리턴
        return pandas.Series(100 - (100/(1 + RS)), name = "RSI")

    #현재 해당코인 RSI 지수 구하기
    def get_cur_coin_RIS(self,coinName,interval):
        log = Log().initLogger()

        try:
            coinPricecInfo = pyupbit.get_ohlcv(coinName, interval=interval)
            #sleep(0.25)  
            #14일간 ris지수 데이터프레임에서 제일 마지막꺼 가져옴 (-1은 뒤에서 첫번째)
            cur_coin_RIS = self.colculrate_rsi(coinPricecInfo, 14).iloc[-1]
            #print(datetime.now(), now_rsi)
        except Exception as err:
            log.debug('[[[[[[Error]]]]]] get_cur_coin_RIS Error>>>'+str(err))
            #print('[[[[[[Error]]]]]] get_cur_coin_RIS Error>>>'+str(err))
        finally:
            #14일간 ris지수 데이터프레임에서 제일 마지막꺼 가져옴 (-1은 뒤에서 첫번째)
            return self.colculrate_rsi(coinPricecInfo, 14).iloc[-1]

    #이동평균선 값 구하기
    def get_maVal(self, coinName , day):
        coinInfo = pyupbit.get_ohlcv(coinName, count=day)
        #mean은 그룹화된 값의 평균
        #rolling은 갯수만큼 그룹화
        #마지막 행이 평균계산값이라서 -1
        maVal =coinInfo['close'].rolling(window=day).mean()[-1]
        return maVal

    #코인 구매시 투입 가격 산정
    def get_order_coin_price(self):

        orderPrice = 0
        #내 총알이 5만원 이하 일때 만원씩 투자
        #이상이면 2만원씩 투자 
        if(float(CoinEvent().getMyChongal()) < 50000):
           orderPrice = CoinUtill().get_limitMoney()
        else:
           orderPrice = CoinUtill().get_orderMoney()
            
        return orderPrice     

#급등 코인 구분 
    async def get_bigShort_coinList(self,coinName):
        #100시간전 배디 종가 상승 & 거래량 20프로 상승 
        bigShortFlag = False
        log = Log().initLogger()

        try:
            df = pyupbit.get_ohlcv(coinName,"minute30")
            await asyncio.sleep(0.2)
            firstClose = float(df.iloc[0]['close'])
            firstVolume = float(df.iloc[0]['volume'])

            curClose = float(df.iloc[-1]['close'])
            curVolume = float(df.iloc[-1]['volume'])
            diffPercent = float(((curClose-firstClose)/curClose))*100
            
            #전일대비 상위권 코인 + 거래량 20프로 많은거
            if(diffPercent > 0):
                #print('coinName >>'+coinName)
                #print('급등할예정 높음')
                log.debug('coinName >>'+coinName)
                log.debug('급등할예정 높음')
                bigShortFlag = True
        except Exception as Err:
            #print('get_bigShort_coinList Error>>>'+str(Err))   
            log.debug('get_bigShort_coinList Error>>>'+str(Err))
        finally:
            return bigShortFlag

    #구매코인 찾기
    async def goFindCoin(self,coinName):
        #print("goFindCoin")
        log = Log().initLogger()            
        try:
            #코인전략
            #1.Range 구하기
            #Strategy = Strategy()
            #print(Strategy.get_pre_Range("KRW-BTC"))
            curTime = (datetime.today()).strftime("%Y%m%d %H:%M:%S")
            #print("[[[[[[[[[[  코인 서칭 중.......탕스]]]]]]]]]]]]]"+ str(curTime))

            Range = self.get_pre_Range(coinName)

            #2. 장중 가격 > 당일시가 + Range * K
            curPrice = CoinEvent.get_cur_coin_price(self,coinName)
            # 계산된 기준값
            #거래대금 거래량 X 현재가 = 거래대금 
            basicPriceValue = self.get_Basic_Price(coinName,Range,curPrice)
            #sleep(0.2)
            #현재 코인RSI 지수 
            #curCoinRSI = self.get_cur_coin_RIS(coinName)
            #sleep(0.3)

            #5, 14일 이동평균값
            maV5 = self.get_maVal(coinName,5)
            maV14 = self.get_maVal(coinName,14)

            # print('coinName>>>'+coinName)
            # print('Range>>>'+str(Range))
            # print("현재가격>>>"+str(curPrice))
            # print("RSI 지수 >>>>>>"+str(curCoinRSI)) 
            # print("이평선 5일>>>"+str(self.get_maVal(coinName,5)))
            # print("이평선 14일>>>"+str(self.get_maVal(coinName,14)))

            
            #print("코인 서칭 진행중..시간 >>>"+str(curTime)) #1~3초
           
            # 조건식에 걸리면 매수
            #if(curPrice >= basicPriceValue):
            #직전 RSI 차이 
            coinPricecInfo = pyupbit.get_ohlcv(coinName, interval="minute1")
            #print("RSI 차이2>>>"+str(coinPricecInfo))
            before_coin_RIS = self.colculrate_rsi(coinPricecInfo, 14)
            #5분봉기준 rsi 차이
            
            log.debug("1분전 차이>>>"+str(before_coin_RIS[-1] - before_coin_RIS[-2]))
            log.debug("2분전 차이>>>"+str(before_coin_RIS[-2] - before_coin_RIS[-3]))
            log.debug("3분전 차이>>>"+str(before_coin_RIS[-3] - before_coin_RIS[-4]))
            #log.debug("4분전 차이>>>"+str(before_coin_RIS[-1] - before_coin_RIS[-4]))
            log.debug("4분전 차이>>>"+str(before_coin_RIS[-4] - before_coin_RIS[-5]))
            log.debug("5분전 차이>>>"+str(before_coin_RIS[-5] - before_coin_RIS[-6]))

            # print("1분봉 1,2분 차이>>>"+str(before_coin_RIS[-1] - before_coin_RIS[-2]))
            # print("1분봉 2,3분 차이 >>>"+str(before_coin_RIS[-2] - before_coin_RIS[-3]))
            # print("1분봉 3,4분 차이 >>>"+str(before_coin_RIS[-3] - before_coin_RIS[-4]))
            # print("5분봉 1,2분 차이 >>>"+str(before_coin_RIS[-1] - before_coin_RIS[-4]))
            
            
            #주문갯수
            targetPrice = round(basicPriceValue,1)
            orderVolumn = round((self.get_order_coin_price()/targetPrice),0)

            #로켓급등
            rocketChart = False

            # -- +  + + 그래프 
            if(before_coin_RIS[-1] - before_coin_RIS[-2] >0 #1 +
            and before_coin_RIS[-2] - before_coin_RIS[-3] >= 0 #2 + 
            #거래량 차이 이상일때 산다.
            and CoinEvent().get_diff_vol(coinName,"minute1",5) >= 20000
            and before_coin_RIS[-3] - before_coin_RIS[-4] <= 0 #3  + 
            and before_coin_RIS[-4] - before_coin_RIS[-5] <= 0 #4 - 
            and before_coin_RIS[-5] - before_coin_RIS[-6] < 0 #5 - 
            ):
                #1분봉기준 rsi 차이
                log.debug("급등이네!!!!")
                #print("급등이네!!!!")
                rocketChart = True
                log.debug("-1>>>"+str(before_coin_RIS[-1]))
                log.debug("-2>>>"+str(before_coin_RIS[-2]))
                log.debug("-3>>>"+str(before_coin_RIS[-3]))
                log.debug("-4>>>"+str(before_coin_RIS[-4]))

            endTime = (datetime.today()).strftime("%H%M")
            
            
            
            #이미 보유한 코인인지 아닌지
            if CoinEvent().checkBuyCoin(coinName):
                log.debug("이미 보유! 추매 로직선정 >>>"+str(curPrice))
                #이평선 5, 14보다 현재가가 높으면서 5 > 14인경우 매수 거름 통과
                if(curPrice > maV5 and curPrice > maV14 and maV5 >= maV14):
                    #구매가 대비 -0.5이하로 떨어지면 추매 
                    chuMadPer = float(((curPrice - basicPriceValue)/basicPriceValue)*100)
                    
                    if(chuMadPer) >= 0.7:
                        log.debug("0.7 상승시추매 >>>>>>"+str(curPrice))
                        #시장가로 주문
                        CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")


            else :
                log.debug("신규 코인 구매 로직선정 >>>>>>"+str(curPrice))
                #9시 급등장이 많아서 9시 9시 10분사이 걸리는거 아니면, 급등차트
                if(int(endTime) >= 900 and int(endTime) <= 905 or rocketChart):
                    log.debug("curPrice>>>"+str(curPrice))
                    log.debug("maV5>>>"+str(maV5))
                    log.debug("maV14>>>"+str(maV14))

                    #이평선 5, 14보다 현재가가 높으면서 5 > 14인경우 매수 거름 통과
                    if(curPrice > maV5 and curPrice > maV14 and maV5 >= maV14):
                        #캐치하고 몇초뒤로 하면 좀 떨어진 가격에 삼
                        sleep(8)
                        log.debug("8초뒤..!")
                        #한번더 상황을 보고 양이면 투자
                        if CoinEvent().get_diff_vol(coinName,"minute1",5) > 0:
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")    

                            log.debug("급등 + 이평선걸리는거 무조건 사고 빠진다")
                            log.debug("1분봉 1,2분 차이>>>"+str(before_coin_RIS[-1] - before_coin_RIS[-2]))
                            log.debug("1분봉 2,3분 차이 >>>"+str(before_coin_RIS[-2] - before_coin_RIS[-3]))
                            log.debug("거래량 차이 >>>"+str(CoinEvent().get_diff_vol(coinName,"minute1",5)))
                            log.debug("5분봉 1,2분 차이 >>>"+str(before_coin_RIS[-1] - before_coin_RIS[-4]))
                            log.debug("curPrice >>>"+str(curPrice))
                            log.debug("maV5 >>>"+str(maV5))
                            log.debug("maV14 >>>"+str(maV14))


                        # print("급등 + 이평선걸리는거 무조건 사고 빠진다")
                        # print("1분봉 1,2분 차이>>>"+str(before_coin_RIS[-1] - before_coin_RIS[-2]))
                        # print("1분봉 2,3분 차이 >>>"+str(before_coin_RIS[-2] - before_coin_RIS[-3]))
                        # print("5분봉 1,2분 차이 >>>"+str(before_coin_RIS[-1] - before_coin_RIS[-4]))

                        #시장가로 주문

                #적정가 거의 근처오면 산다. 반등칠 가능성큼
                elif (curPrice >= basicPriceValue):
                    if curPrice <= 100:
                        if(curPrice - basicPriceValue) <= 0.1:
                            log.debug("[[[[[[[[[[[[ 적정가 근처 ]]]]]]]]]]]")
                            log.debug('------------------------------------------------')
                            log.debug('코인명>>>'+coinName)
                            log.debug('장중가격>>>'+str(curPrice))
                            log.debug('적정가>>>'+str(basicPriceValue))
                            sleep(7)
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")           
                            sleep(7)
                    else :
                        if(curPrice - basicPriceValue) <= 5:
                            log.debug("[[[[[[[[[[[[ 적정가 근처 ]]]]]]]]]]]")
                            log.debug('------------------------------------------------')
                            log.debug('코인명>>>'+coinName)
                            log.debug('장중가격>>>'+str(curPrice))
                            log.debug('적정가>>>'+str(basicPriceValue))
                            sleep(7)
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")                   
                            sleep(7)
                else :
                    #너무비싼코인은 못사니까 만원 이하 코인에서
                    #5,703,226,143 이상 볼륨만
                    curOrderVol = CoinEvent.get_cur_info(self,coinName)["volume"] * curPrice             

                    #print("                 ")
                    #print("[[[[[[[[[[[[ 코인 서칭 !! 1차 거름 ]]]]]]]]]]]")                    
                    #print("[[[[[[[[[[[[ *** 변동성 돌파 전략 *** ]]]]]]]]]]]")                    
                    # print('coinName>>>'+coinName)
                    # print('curPrice>>>'+str(curPrice))
                    # print('basicPriceValue>>>'+str(basicPriceValue))
                    # print("RSI 지수 >>>>>>"+str(curCoinRSI)) 
                    # print("[[[[[[[[[[[[ 코인 서칭 !! 1차 거름 ]]]]]]]]]]]]")                    
                    # print("                 ")

                    #이평선 5, 14보다 현재가가 높으면 매수 거름 통과 ,정배열
                    if(curPrice > maV5 and curPrice > maV14 and maV5 >= maV14):
                        #print("                 ")
                        #print("[[[[[[[[[[[[ 코인 서칭 !! 2차 거름 통과 ]]]]]]]]]]]")    
                        #print("[[[[[[[[[[[[ *** 현재가격 높음 (이평선대비) *** ]]]]]]]]]]]")  
                        #총알이 만원이상일때 , 현재가격 만원이하코인중, 구매액 5천만원이상 , RSI 지수 30미만 
                        if(float(CoinEvent().getMyChongal()) >= CoinUtill().get_limitMoney() and curPrice <= CoinUtill().get_limitMoney() and curOrderVol >= 5000000000 and self.get_cur_coin_RIS(coinName,"minute240") <=28):
                            #시장가로 주문
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")                         

                            log.debug("[[[[[[[[[[[[ 코인 서칭 !! 최종 거름 통과 ]]]]]]]]]]]")
                            log.debug('------------------------------------------------')
                            log.debug('코인명>>>'+coinName)
                            log.debug('장중가격>>>'+str(curPrice))
                            log.debug("basicPriceValue>>>"+str(round(basicPriceValue,1)))
                            log.debug("매수!")
                            log.debug('매수가격>>>>'+str(targetPrice))
                            log.debug('주문수량>>>>'+str(orderVolumn))
                            log.debug('------------------------------------------------')
                            
                            
                            # print("[[[[[[[[[[[[ 코인 서칭 !! 최종 거름 통과 ]]]]]]]]]]]")    
                            # print('------------------------------------------------')
                            # print('코인명>>>'+coinName)
                            # print('장중가격>>>'+str(curPrice))
                            # print("basicPriceValue>>>"+str(round(basicPriceValue,1)))
                            # print("매수!")


                            # print('매수가격>>>>'+str(targetPrice))
                            # print('주문수량>>>>'+str(orderVolumn))
                            # print('------------------------------------------------')

                    else:
                        #print("[[[[[[[[[[[[ 코인 서칭 !! 2차 거름 미통과 ]]]]]]]]]]]]")
                        log.debug("[[[[[[[[[[[[ 코인 서칭 !! 2차 거름 미통과 ]]]]]]]]]]]]")
        except Exception as err:
            #print('[[[[[[goFindCoin]]]]]] Error>>>'+str(err))
            log.debug('[[[[[[goFindCoin]]]]]] Error>>>'+str(err))

    #현재 보유코인 팔지 여부
    async def checkSellMyCoin(self,hastickers):
        log = Log().initLogger()
        myInfo = CoinEvent.get_myBalance(self)
        #log.debug('myInfo>>'+str(myInfo))

        #익절 ,손절 퍼센트
        sellPercent =  CoinUtill().get_sellPercent()
        minusPercent = CoinUtill().get_minusPercent()
        basicSellPercent = 0.0

        minusPercentSecond = CoinUtill().get_minusPercentSecond()
        sellPercentSecond =  CoinUtill().get_sellPercentSecond()
        basicMinusPercent = 0.0

        #print("checkSellMyCoin")
        for items in myInfo:
            coinNm = str(items["unit_currency"])+"-"+str(items["currency"])            

            #내가산 코인이 있을때만 비교
            if(hastickers == coinNm):
                log.debug('hastickers>>'+hastickers)
                #내가산 코인 구매가
                buyPrice = items["avg_buy_price"]
                
                #코인가격 100원 이하면 퍼센트 다르게함 
                if(float(buyPrice) < 100):
                    basicSellPercent = sellPercentSecond
                    basicMinusPercent = minusPercentSecond
                else :
                    basicSellPercent = sellPercent
                    basicMinusPercent = minusPercent

                try:
                    #현재 나의 해당 코인 수익정보
                    myWallet = CoinEvent.get_myProfitInfo(self,items)
                    coinProfit = myWallet["profitPercent"]
                    ProfitWon = round(myWallet["profit"],0)
                    
                    # print("                 ")
                    # print("[[[[[[[[[[[[ 보유 코인 정보]]]]]]]]]]]]")
                    # print(" *** 코인명 :: "+str(coinNm) +" [[[ 수익률 ]]] >>>"+str(coinProfit)+"%"+" [[[ 손익 ]]] >>>"+str(ProfitWon)+"원")
                    #현재 코인RSI 지수 
                    #curCoinRSI = self.get_cur_coin_RIS(coinNm)

                    # print("RSI 지수 >>>>>>"+str(curCoinRSI)) 
                    # print("[[[[[[[[[[[[ 보유 코인 정보]]]]]]]]]]]]")
                    # print("                 ")

                    MA5 = self.get_maVal(coinNm,5)
                    MA14 = self.get_maVal(coinNm,14)

                    log = Log().initLogger()
                        
                    # +프로 먹으면 익절 
                    if coinProfit > basicSellPercent:
                        CoinEvent.buyAndGazzza(self,coinNm,"ask",items["balance"],0,"market")
                        log.debug("                 ")
                        log.debug('+++++$$$$$ 익절!')
                        log.debug("coinProfit>>>>"+str(coinProfit))
                        log.debug("basicSellPercent>>>>"+str(basicSellPercent))
                        log.debug("ProfitWon>>>>"+str(ProfitWon))
                        log.debug('+++++$$$$$ 익절!')
                        log.debug("                 ")
                        
                        # print("                 ")
                        # print('+++++$$$$$ 익절!')
                        # print("coinProfit>>>>"+str(coinProfit))
                        # print("get_sellPercent>>>>"+str(basicSellPercent))
                        # print("ProfitWon>>>>"+str(ProfitWon))
                        # print('+++++$$$$$ 익절!')
                        # print("                 ")

                    elif coinProfit <= -0.5 and coinProfit > basicMinusPercent:
                        curPrice = CoinEvent.get_cur_coin_price(self,coinNm)
                        #이평선보다 높으면서, 상승세인경우 추매
                        if(curPrice > MA5 and curPrice > MA14 and MA5 >= MA14 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2) >= 0):
                            log.debug("-0.5 ~ -0.89 이지만 상승세면, 추매 >>>>>>"+str(curPrice))
                            CoinEvent.buyAndGazzza(self,coinNm,"bid",orderVolumn,self.get_order_coin_price(),"price")

                    # -프로 이하면 손절 
                    elif coinProfit <= basicMinusPercent:
                            CoinEvent.buyAndGazzza(self,coinNm,"ask",items["balance"],0,"market")
                        
                            log.debug("                 ")
                            log.debug('-----$$$$$ 손절ㅠㅠ')
                            log.debug("coinProfit>>>>"+str(coinProfit))
                            log.debug("basicMinusPercent>>>>"+str(basicMinusPercent))
                            log.debug("ProfitWon>>>>"+str(ProfitWon))
                            log.debug('-----$$$$$ 손절ㅠㅠ')
                            log.debug("                 ")
                            
                        #  print("                 ")
                        #  print('-----$$$$$ 손절ㅠㅠ') 
                        #  print("coinProfit>>>>"+str(coinProfit))
                        #  print("get_sellPercent>>>>"+str(basicMinusPercent))
                        #  print("ProfitWon>>>>"+str(ProfitWon))
                        #  print('-----$$$$$ 손절ㅠㅠ') 
                        #  print("                 ")

                    # 과매수 지점 -> 매도 해야함 & 분봉차이값 - 전환될때 판다  ,1분봉 5분봉 둘다봄 , 손익도 봄
                    elif self.get_cur_coin_RIS(coinNm,"minute240") >= 70 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2) < 0 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-2,-3) < 0 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute5",-1,-2) < 0 and coinProfit <= basicMinusPercent:
                        CoinEvent.buyAndGazzza(self,coinNm,"ask",items["balance"],0,"market")
                        
                        log.debug("                 ")
                        log.debug("1 조건>>>>"+str(self.get_cur_coin_RIS(coinNm,"minute240")))
                        log.debug("2 조건>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2)))
                        log.debug("3 조건>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-2,-3)))
                        log.debug("4 조건>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute5",-1,-2)))
                        log.debug("ProfitWon>>>>"+str(ProfitWon))
                        log.debug("과매수 지점 도달!!! [[[매도]]!!!!")
                        log.debug("                 ")

                        # print("                 ")
                        # print("1, 2>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2)))
                        # print("2, 3>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-2,-3)))
                        # print("1, 2>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute5",-1,-2)))                                
                        # print("ProfitWon>>>>"+str(ProfitWon))
                        # print("과매수 지점 도달!!! [[[매도]]!!!!")
                        # print("                 ")
                
                    # RIS , 일평선 14가 더 높거나, 음봉뜰때  
                    elif MA5 <= MA14 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2) < 0 and CoinEvent.get_pre_RIS_val(self,coinNm,"minute5",-1,-2) < 0 and coinProfit <= -0.89:
                        CoinEvent.buyAndGazzza(self,coinNm,"ask",items["balance"],0,"market")
                        
                        log.debug("                 ")
                        log.debug("MA5 조건>>>>"+str(MA5))
                        log.debug("MA14 조건>>>>"+str(MA14))
                        log.debug("2 조건>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2)))
                        log.debug("3 조건>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-2,-3)))
                        log.debug("ProfitWon>>>>"+str(ProfitWon))
                        log.debug("매도지점이긴함 [[[매도]]!!!!")
                        log.debug("                 ")

                        # print("                 ")
                        # #print("curCoinRSI>>>>"+str(curCoinRSI))
                        # print("1, 2>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-1,-2)))
                        # print("2, 3>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute1",-2,-3)))
                        # print("1, 2>>>>"+str(CoinEvent.get_pre_RIS_val(self,coinNm,"minute5",-1,-2)))                                
                        # print("ProfitWon>>>>"+str(ProfitWon))
                        # print("매도지점이긴함 [[[매도]]!!!!")
                        # print("                 ")
                
                    # 보유한 코인 RSI 2이하면 추매하자
                    elif self.get_cur_coin_RIS(coinNm,"minute240") <= 27:
                        
                        #print("과매도 지점 도달!!! [[[추미애 가즈아]]!!!!")
                        
                        #구매시 range를 통해 구매갯수 추출하여 추미애
                        Range = self.get_pre_Range(coinNm)
                        curPrice = CoinEvent.get_cur_coin_price(self,coinNm)
                        basicPriceValue = self.get_Basic_Price(coinNm,Range,curPrice)
                        targetPrice = round(basicPriceValue,1)
                        orderVolumn = round((self.get_order_coin_price()/targetPrice),0)

                        CoinEvent.buyAndGazzza(self,coinNm,"bid",orderVolumn,self.get_order_coin_price(),"price")

                        log.debug("                 ")
                        log.debug("과매도 지점 도달!!! [[[추미애 가즈아]]!!!!")
                        log.debug("                 ")

                        sleep(7)

                
                except Exception as Err:
                    #print('[[[[[[Error]]]]]] checkSellMyCoin Error>>>'+str(Err))
                    log.debug('[[[[[[Error]]]]]] checkSellMyCoin Error>>>'+str(Err))

                # finally:
                #     await asyncio.sleep(0.2)   

    #변동성 돌파전략
    def goBuyCoin(self,coinName):

        try:

          log = Log().initLogger()
          Range = self.get_pre_Range(coinName)
          curPrice = CoinEvent.get_cur_coin_price(self,coinName)
          basicPriceValue = self.get_Basic_Price(coinName,Range,curPrice)
          kvalue = self.get_Kvalue(coinName)
          #주문갯수
          targetPrice = round(basicPriceValue,1)
          orderVolumn = round((self.get_order_coin_price()/targetPrice),0)
    
          MA5 = self.get_maVal(coinName,5)
          MA14 = self.get_maVal(coinName,14)

          #보유 코인인경우
          if CoinEvent().checkBuyCoin(coinName):
            #    log.debug("이미 구매한 코인 서칭중....")
            #    log.debug("coinName>>>"+coinName)
            #    log.debug("basicPriceValue>>>"+str(basicPriceValue))
            #    log.debug("curPrice>>>"+str(curPrice))
               
               myCoinInfo = CoinEvent().getMyProfit(coinName)
               coinProfit = myCoinInfo["profitPercent"]

            #    log.debug(" wallet percent>>>"+str(coinProfit))

               if(basicPriceValue > curPrice):
                  #lossPercent = float(((curPrice - basicPriceValue)/basicPriceValue))*100
                  #log.debug("lossPercent>>>"+str(lossPercent))
                  if(coinProfit < -2 and coinProfit >= -3):
                      log.debug("예상치보다 떨어지면, 추매")
                      log.debug("구매했던 코인명>>>"+coinName)
                      log.debug("손실 퍼센트::>>>"+str(coinProfit))
                      CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")
                  elif(coinProfit <-3.5 ):
                      log.debug("이러다 다죽어222!!!!! 손절 ㅠ")
                      log.debug("구매했던 코인명>>>"+coinName)
                      log.debug("손실 퍼센트::>>>"+str(coinProfit))
                      CoinEvent.buyAndGazzza(self,coinName,"ask",myCoinInfo["balance"],0,"market")  
                  elif(coinProfit >= 3.5):
                      log.debug("예상치보다 많이오름, 익절!")
                      log.debug("구매했던 코인명>>>"+coinName)
                      log.debug("손실 퍼센트::>>>"+str(coinProfit))
                      CoinEvent.buyAndGazzza(self,coinName,"ask",myCoinInfo["balance"],0,"market")  

               else:
                  #가능성 적지만, 오르면 팔고 내리면 팔고 
                  if(coinProfit >= 3.5):
                      log.debug("예상치보다 많이오름, 익절!")
                      log.debug("구매했던 코인명>>>"+coinName)
                      log.debug("손실 퍼센트::>>>"+str(coinProfit))
                      CoinEvent.buyAndGazzza(self,coinName,"ask",myCoinInfo["balance"],0,"market")

                  elif(coinProfit <-3.5 ):
                      log.debug("이러다 다죽어!!!!! 손절 ㅠ")
                      log.debug("구매했던 코인명>>>"+coinName)
                      log.debug("손실 퍼센트::>>>"+str(coinProfit))
                      CoinEvent.buyAndGazzza(self,coinName,"ask",myCoinInfo["balance"],0,"market")
                      
          else:
              #log.debug("첫 구매할 코인 서칭중....")
              if(curPrice >= basicPriceValue):
                # log.debug("구매할 코인명>>>"+coinName)
                # log.debug("현재가격>>"+str(curPrice))
                # log.debug("변동성지수 기준가격>>"+str(basicPriceValue))
                # log.debug("변동성 지수 >>"+str(kvalue))
                # log.debug("차이>>"+str(curPrice-basicPriceValue))
                
                diff = curPrice-basicPriceValue
                
                #100이하는 0.5 차이면 삼
                if(curPrice < 100 and curPrice >= 1):
                    if(diff <= 0.05):
                        if(curPrice > MA5 and curPrice > MA14 and MA5 >= MA14):
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")
                #100 이상은 5차이나면 삼 
                elif(curPrice >= 100) :
                    if(diff <= 2):
                        if(curPrice > MA5 and curPrice > MA14 and MA5 >= MA14):
                            #시장가로 주문
                            CoinEvent().buyAndGazzza(coinName,"bid",orderVolumn,self.get_order_coin_price(),"price")

        except Exception as Err:
            log.debug('[[[[[[Error]]]]]] goBuyCoin Error>>>'+str(Err))


        
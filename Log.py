#로깅 처리
import logging
from datetime import datetime
import os

class Log:

    def initLogger(self):
        curDays = (datetime.today()).strftime("%Y%m%d")
        #로그 객체 선언
        logger = logging.getLogger(__name__)
        #이미 핸들러 있으면 바로 리턴 해서 중복안나게함
        if len(logger.handlers) > 0:
            #현재날짜 파일있는지 확인
            #if(os.path.isfile("buyAndSell_"+curDays+".log") == True):
            return logger # Logger already exists

        #로그 레벨 설정 
        logger.setLevel(level=logging.DEBUG)

        #로그 파일화 
        filehandler = logging.FileHandler('./buyAndSell_'+curDays+".log")
        logger.addHandler(filehandler)

        # formatter 생성
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s|%(filename)s:%(lineno)s] >> %(message)s')
        filehandler.setFormatter(formatter)


        return logger
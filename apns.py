import datetime
import time

import requests, urllib3
import pynvml
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

pynvml.nvmlInit()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fmt = logging.Formatter(fmt="%(asctime)s - %(levelname)-6s - %(filename)-8s : %(lineno)-4s line | %(message)s",
                        datefmt="%a %d %b %Y %H:%M:%S")

sh = logging.StreamHandler()
fh = logging.FileHandler('log.txt', mode='a', encoding=None, delay=False)

sh.setFormatter(fmt)
fh.setFormatter(fmt)
logger.addHandler(sh)
logger.addHandler(fh)


def all2list(x):
    if type(x) in [tuple, list, set] and all(type(i) is str for i in x):
        return list(x)
    elif type(x) == str:
        return [x]
    else:
        raise TypeError(f"The type of {x} isn't available")


def gpu_is_free():
    deviceCount = pynvml.nvmlDeviceGetCount()  # 设备数
    gpuUsed = 0
    for i in range(deviceCount):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)

        computeProcess = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)  # 获取计算模式程序的pid
        logger.debug(f"The {i} GPU, Num of Process: {len(computeProcess)}")
        if len(computeProcess) != 0:
            gpuUsed += 1
            continue

        memInfo = pynvml.nvmlDeviceGetMemoryInfo(handle)
        logger.debug(f"The {i} GPU, Mem Used: {memInfo.used / memInfo.total}")
        if memInfo.used / memInfo.total > 3e-2:
            gpuUsed += 1
            continue

        gpuUtilRate = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        logger.debug(f"The {i} GPU, Util Rates:{gpuUtilRate}")
        if gpuUtilRate > 5:
            gpuUsed += 1

    if gpuUsed > 1:
        return False
    return True


def getIP():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # s.connect(("8.8.8.8", 80))
        s.connect(('10.255.255.255', 1))
        ip, port = s.getsockname()
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class APNS():
    def __init__(self, base, sendMsgNumInHourLim=4):
        self.barksList = all2list(base)
        self.last_stat = 0
        self.sendMsgNum = 0
        self.sendMsgNumInHourLim = sendMsgNumInHourLim

        self.scheduler = BlockingScheduler(timezone="Asia/Shanghai")

        self.scheduler.add_job(self.sendGPU2bark, 'interval', minutes=1)
        self.scheduler.add_job(self.clearSendMsgNum, 'interval', minutes=40)
        self.scheduler.add_job(self.send2time, 'cron', hour="10-17/2")

        logger.info(f"Bark keys: {self.barksList}")
        # self.start()

    def add_job(self, func, trigger='interval', **karges):
        self.scheduler.add_job(func, trigger=trigger, **karges)

    def send2bark(self, key, title, content, len=0):
        if len > 10:
            return
        bark_url = "https://api.day.app/" + str(key)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'

        try:
            msg = "{0}/{1}/{2}/?isArchive=1".format(bark_url, title, content)
            proxies = {"http": None, "https": None}
            res = requests.get(msg, verify=False, proxies=proxies)
            logger.info(f'Send MSG to Barks, {key, title, content}')
        except Exception as e:
            logger.error('Reason:', e)
            time.sleep(0.2)
            self.send2bark(key, title, content, len + 1)

    def send2all(self, title, content):
        for key in self.barksList:
            self.send2bark(key, title, content)

    @staticmethod
    def getTime():
        return datetime.datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

    def sendGPU2bark(self):
        stat = gpu_is_free()
        logger.info(f'GPU stat: {bool(stat)}')

        info = None
        if self.last_stat == 0 and stat == 1:
            info = "GPU可用"
        if self.last_stat == 1 and stat == 0:
            info = "GPU占用中"

        if info and self.sendMsgNum < self.sendMsgNumInHourLim:
            self.send2all(getIP(), info)
            self.sendMsgNum += 1

        self.last_stat = stat

    def clearSendMsgNum(self):
        self.sendMsgNum = 0

    def send2time(self):
        self.send2all("当前时间", self.getTime())
        # print("当前时间",self.getTime())

    def start(self):
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        self.stop()

    def stop(self):
        pynvml.nvmlShutdown()
        self.scheduler.shutdown()


if __name__ == '__main__':
    # print(getIP())
    # exit()
    a = APNS(['nseg8Kgy4gjbuRNW4etA2E'])
    a.send2all("hello",'zk')
    print(a.getTime())
    print(gpu_is_free())
    a.start()

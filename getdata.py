import serial
from logging import getLogger

logger = getLogger(__name__)

def connection(dev_port, id, password):
    ser = serial.Serial(dev_port, 115200)

    #パスワード設定
    logger.info("パスワード設定")
    ser.write(("SKSETPWD C " + password + "\r\n").encode())
    ser.readline()
    ser.readline()

    #ID設定
    logger.info("ID設定")
    ser.write(("SKSETRBID " + id + "\r\n").encode())
    ser.readline()
    ser.readline()

    scan_duration = 4
    scan_result = {}

    while not "Channel" in scan_result:
        ser.write(("SKSCAN 2 FFFFFFFF " + str(scan_duration) + "\r\n").encode())

        while(True):
            line = ser.readline()
            if line.startswith("EVENT 22".encode()):
                #SCAN終了
                break

            elif line.startswith("  ".encode()):
                cols = line.decode().strip().split(":")
                scan_result[cols[0]] = cols[1]
        
        scan_duration += 1

        #scan失敗
        if 7 < scan_duration and not "Channel" in scan_result:
            ser.close()
            return None,None

    #channel設定
    ser.write(("SKSREG S2 " + scan_result["Channel"] + "\r\n").encode())
    ser.readline()
    ser.readline()

    #Pan ID設定
    ser.write(("SKSREG S3 " + scan_result["Pan ID"] + "\r\n").encode())
    ser.readline()
    ser.readline()


    #IPV6リンクローカルアドレス取得
    ser.write(("SKLL64 " + scan_result["Addr"] + "\r\n").encode())
    ser.readline()
    ipv6_addr = ser.readline().decode().strip()

    #PANA 接続開始
    ser.write(("SKJOIN " + ipv6_addr + "\r\n").encode())
    ser.readline()
    ser.readline()

    while True:
        line = ser.readline()
        if line.startswith("EVENT 24".encode()):
            ser.close()
            return None,None
        
        elif line.startswith("EVENT 25".encode()):
            break

    #タイムアウト設定
    ser.timeout = 8
    ser.readline()
    

    return ser, ipv6_addr


def get_data(ser, addr, on_receive):
    #瞬間電力取得
    CMD = b"\x10\x81\x12\x34\x05\xFF\x01\x02\x88\x01\x62\x01\xE7\x01\x01"
    
    command = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(addr, len(CMD))
    ser.write((command).encode() + CMD)
    ser.readline()
    ser.readline()
    ser.readline()
    line = ser.readline()

    if line.startswith("ERXUDP".encode()):
        cols = line.decode().strip().split(" ")
        result = cols[8]
        seoj = result[8:8+6]
        ESV = result[20:20+2]

        #瞬間電力値
        power = int(line[-8:], 16)
        on_receive(power)

if __name__ == "__main__":
    import time
    import threading
    import os
    import dotenv
    import datetime

    INTERVAL = 10

    #環境設定読み込み
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    dotenv.load_dotenv(dotenv_path=env_path)
    B_ROUTE_ID = os.getenv("B_ROUTE_ID")
    B_ROUTE_PASSWORD = os.getenv("B_ROUTE_PASSWORD")
    DEV_PORT = os.getenv("DEV_PORT")

    #接続
    ser, ipv6_addr = connection(DEV_PORT, B_ROUTE_ID, B_ROUTE_PASSWORD)

    #接続に成功
    if ser:
        func = lambda x: print("%s 瞬間電力値: %sW" % (datetime.datetime.now(), x))
        
        base_time = time.time()
        next_time = 0        
        while True:
            try:
                t = threading.Thread(target=get_data, args=(ser, ipv6_addr, func))
                t.start()

                #スレッド終了まで待機する
                t.join()

                #スリープ時間計算
                next_time = ((base_time - time.time()) % INTERVAL) or INTERVAL
                time.sleep(next_time)

            except Exception as e:
                ser.close()
                break
                
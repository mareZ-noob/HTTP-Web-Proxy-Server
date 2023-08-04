import codecs
import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta

# Start Define

# Host, Port
PROXY_PORT = int(8888)
PROXY_HOST = str("127.0.0.1")
MY_HOST = str("mareZ-noob")
HTTP_PORT = int(80)

# Folders, files, paths
CONFIG_FILE = str("config.json")
CACHE_DIRECTORY = str("cache")
CURRENT_PATH = os.getcwd()
CACHE_FOLDER_PATH = os.path.join(CURRENT_PATH, CACHE_DIRECTORY)
NOT_FOUND_PAGE = str("index.html")

# Time
CACHE_EXPIRATION_TIME = timedelta(minutes=15)
CURRENT_DATE_TIME = datetime.now()
CURRENT_TIME = time.strftime("%H:%M:%S", time.localtime())

# Limitation
MAX_CONNECTION = int(10)
MAX_RECEIVE = int(4096)

# End Define


def CreateServer(host: str, port: int):
    try:
        tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcpSerSock.bind((host, port))
        tcpSerSock.listen(MAX_CONNECTION)
    except TimeoutError as error:
        print(error)
        print("Creating server failed !")
        time.sleep(2)
        exit(0)
    except ConnectionError as error:
        print(error)
        print("Creating server failed !")
        time.sleep(2)
        exit(0)
    return tcpSerSock


def CreateClient(host: str, post: int):
    try:
        tcpCliSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpCliSock.connect((host, post))
    except TimeoutError as error:
        print(error)
        print("Creating client failed !")
        time.sleep(2)
        exit(0)
    except ConnectionError as error:
        print(error)
        print("Creating client failed !")
        time.sleep(2)
        exit(0)
    return tcpCliSock


def NotFound(tcpSock: socket):
    data = b""
    try:
        f = open(NOT_FOUND_PAGE, "rb")
        data = f.read()
    except IOError:
        data = b"403 Not Found"
    header = b"HTTP/1.1 403 Not Found\r\n\r\n"
    res = header + data + b"\r\n\r\n"
    tcpSock.send(res)


def CacheExpiredList():
    CacheList = []
    for file in os.listdir(CACHE_FOLDER_PATH):
        modifyTime = datetime.fromtimestamp(
            os.path.getmtime(os.path.join(CACHE_DIRECTORY, file))
        )

        if CURRENT_DATE_TIME - modifyTime > CACHE_EXPIRATION_TIME:
            CacheList.append(file)
    print(CacheList)
    return CacheList


def WhiteListing():
    datas = []
    with codecs.open(filename=CONFIG_FILE, mode="r", encoding="utf-8") as ifs:
        datas = json.load(ifs)

    i = 0
    white_listing = []
    while True:
        try:
            white_listing.append(datas[i]["allow_host"])
            i += 1
        except IndexError:
            break

    return white_listing


def TouchGrass(web: str):
    datas = []
    with codecs.open(filename=CONFIG_FILE, mode="r", encoding="utf-8") as ifs:
        datas = json.load(ifs)

    # Check if web in config file
    check = int(-1)
    for data in datas:
        if data["allow_host"] == web:
            check = 1
    if check == -1:
        return check

    flag = int(1)  # 1 -> Deactivate server | 0 -> Activate server
    for data in datas:
        if data["allow_host"] == web:
            time_start = str(data["time_start"])
            time_end = str(data["time_end"])
            if time_start <= CURRENT_TIME and CURRENT_TIME <= time_end:
                flag = 0

    return flag


def readRequest(sock: socket):
    data = b""
    try:
        data = sock.recv(MAX_RECEIVE)
    except TimeoutError as error:
        print(error)
        return b""

    return data


def readResponse(sock: socket):
    data = b""
    try:
        while 1:
            part = sock.recv(MAX_RECEIVE)
            if len(part) > 0:
                data += part
            else:
                break
    except TimeoutError as error:
        print(error)

    return data


def parseRequest(message: str):
    data = {}
    method = ""
    url = ""
    version = ""
    host = ""
    protocol = "http"

    if "localhost" in message:
        method = message.split("\r\n")[0].split()[0]
        url = message.split("\r\n")[0].split()[1]
        version = message.split("\r\n")[0].split()[2]
        filename = message.split()[1].partition("/")[2]
        host = filename.replace("www.", "", 1)

        data = {
            "Method": method,
            "Protocol": protocol,
            "Url": url,
            "Filename": filename,
            "Version": version,
            "Host": host,
        }
    else:
        method = message.split("\r\n")[0].split()[0]
        url = message.split("\r\n")[0].split()[1]
        version = message.split("\r\n")[0].split()[2]
        host = message.split("\r\n")[1].split()[1]

        data = {
            "Method": method,
            "Protocol": protocol,
            "Url": url,
            "Version": version,
            "Host": host,
        }

    return data


def MainProcess(tcpCliSock: socket):
    message = readRequest(tcpCliSock)
    print(message.decode("ISO-8859-1"))
    if message == b"":
        tcpCliSock.close()
        exit(0)

    req = parseRequest(message.decode("ISO-8859-1"))
    print(req)
    for key, value in req.items():
        print(key, ":", value)
    if req["Method"] != "GET" and req["Method"] != "POST" and req["Method"] != "HEAD":
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    # Localhost
    # check = False
    # white_list = WhiteListing()

    # for list in white_list:
    #     if list == req["Filename"]:
    #         check = True

    # if check == False:
    #     NotFound(tcpCliSock)
    #     tcpCliSock.close()
    #     return

    # if TouchGrass(req["Filename"]) == -1 or TouchGrass(req["Filename"]) == 1:
    #     NotFound(tcpCliSock)
    #     tcpCliSock.close()
    #     return

    check = False
    white_list = WhiteListing()

    for list in white_list:
        if list == req["Host"]:
            check = True

    if check is False:
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    if TouchGrass(req["Host"]) == -1 or TouchGrass(req["Host"]) == 1:
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    c = CreateClient(req["Host"], HTTP_PORT)
    c.send(message)
    response = readResponse(c)
    print(response)
    tcpCliSock.send(response)

    tcpCliSock.close()
    c.close()


def main():
    if not os.path.exists(CACHE_DIRECTORY):
        os.makedirs(CACHE_DIRECTORY)
    tcpSerSock = CreateServer(PROXY_HOST, PROXY_PORT)
    while True:
        try:
            tcpCliSock, addr = tcpSerSock.accept()
            print()
            print("Received connection from IP: %s - Port: %d:" % (addr[0], addr[1]))
            threadsocket = threading.Thread(target=MainProcess, args=(tcpCliSock,))
            threadsocket.start()
            threadsocket.join()
        except KeyboardInterrupt:
            print()
            print("Disconnected !")
            tcpSerSock.close()
            break


if __name__ == "__main__":
    main()

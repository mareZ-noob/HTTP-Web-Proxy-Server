import codecs
import hashlib
import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta

# Start Define

# Host, Port
PROXY_PORT = 8888
PROXY_HOST = "127.0.0.1"
HTTP_PORT = 80

# Folders, files, paths
CONFIG_FILE = "config.json"
CACHE_DIRECTORY = "cache"
CACHE_FOLDER_PATH = os.path.join(os.getcwd(), CACHE_DIRECTORY)
NOT_FOUND_PAGE = "index.html"

# Time
CACHE_EXPIRATION_TIME = timedelta(minutes=15)
CURRENT_DATE_TIME = datetime.now()
CURRENT_TIME = time.strftime("%H:%M:%S", time.localtime())

# Limitation
MAX_CONNECTION = 100
MAX_RECEIVE = 4096

# Methods permission
ALLOW_METHOD = ["GET", "POST", "HEAD"]

# Images
SUPPORTED_IMAGE_EXTENSIONS = [
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "webp",
    "svg",
    "ico",
    "tiff",
    "tif",
    "jp2",
    "svgz",
]

# White-listing dictionary
WHITE_LIST = {}

# Config datas
JSON_DATAS = []

# End Define


def CreateClient(host: str, post: int):
    try:
        tcpCliSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpCliSock.connect((host, post))
    except (TimeoutError, ConnectionError) as error:
        print(error)
        print("Creating client failed.")
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


def LoadDatas():
    global JSON_DATAS
    with codecs.open(filename=CONFIG_FILE, mode="r", encoding="utf-8") as ifs:
        JSON_DATAS = json.load(ifs)


def WhiteListing():
    global WHITE_LIST
    for data in JSON_DATAS:
        WHITE_LIST[data["allow_host"]] = data


def CheckWebsite(web: str):
    # Check if web in config file
    check = -1
    for data in JSON_DATAS:
        if data["allow_host"] == web:
            check = 1
    if check == -1:
        return check

    flag = 1  # 1 -> Deactivate server | 0 -> Activate server
    for data in JSON_DATAS:
        if data["allow_host"] == web:
            time_start = str(data["time_start"])
            time_end = str(data["time_end"])
            if time_start <= CURRENT_TIME and CURRENT_TIME <= time_end:
                flag = 0

    return flag


def parseRequest(message: str):
    protocol = "http"
    file_extension = "None"

    method = message.split("\r\n")[0].split()[0]
    url = message.split("\r\n")[0].split()[1]
    if url.split(".")[-1] in SUPPORTED_IMAGE_EXTENSIONS:
        file_extension = url.split(".")[-1]
    version = message.split("\r\n")[0].split()[2]
    host = message.split("\r\n")[1].split()[1]

    return {
        "Method": method,
        "Protocol": protocol,
        "Url": url,
        "Image Extension": file_extension,
        "Version": version,
        "Host": host,
    }


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


def MainProcess(tcpCliSock: socket):
    # Read a request
    message = tcpCliSock.recv(1000000)

    # print(message.decode("ISO-8859-1"))
    if message == b"":
        tcpCliSock.close()
        return

    req = parseRequest(message.decode("ISO-8859-1"))
    # # print(req)
    for key, value in req.items():
        print(key, ":", value)

    if req["Method"] not in ALLOW_METHOD:
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    if CheckWebsite(req["Host"]) == -1:
        print("You don't currently have permission to access this page.")
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return
    elif CheckWebsite(req["Host"]) == 1:
        print("This page isn't in working hours")
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    filename = hashlib.sha224(req["Url"].encode("ISO-8859-1")).hexdigest()
    image_path = os.path.join(CACHE_FOLDER_PATH, os.path.basename(filename))
    if req["Image Extension"] in SUPPORTED_IMAGE_EXTENSIONS:
        if os.path.exists(image_path):
            # If the image is in the cache, serve it directly
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
            file_extension = req["Image Extension"]
            header = f"HTTP/1.1 200 OK\r\nContent-Type: image/{file_extension}\r\n\r\n"
            tcpCliSock.send(header.encode("ISO-8859-1") + image_data)
        else:
            c = CreateClient(req["Host"], HTTP_PORT)
            c.send(message)
            response = b""
            while True:
                response = c.recv(MAX_RECEIVE)
                if not response:
                    break
                tcpCliSock.send(response)

            with open(image_path, "wb") as image_file:
                image_file.write(response)

            tcpCliSock.send(response)

            c.close()
    else:
        # tmp = message.decode("ISO-8859-1").split("\r\n")[2]
        # message = message.decode("ISO-8859-1").replace(tmp + "\r\n", "")

        # tmp1 = message.split("\r\n")[4]
        # message = message.replace(tmp1 + "\r\n", "")
        # print()
        # print(message)

        c = CreateClient(req["Host"], HTTP_PORT)
        c.send(message)
        response = b""
        while True:
            response = c.recv(MAX_RECEIVE)
            if not response:
                break
            tcpCliSock.send(response)

        tcpCliSock.send(response)

        c.close()


def main():
    if not os.path.exists(CACHE_DIRECTORY):
        os.makedirs(CACHE_DIRECTORY)
    # Create server
    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.bind((PROXY_HOST, PROXY_PORT))
    tcpSerSock.listen(MAX_CONNECTION)

    # Load datas
    LoadDatas()

    # Create white listing host
    WhiteListing()

    while True:
        try:
            tcpCliSock, addr = tcpSerSock.accept()
            print()
            print("Received connection from IP: %s - Port: %d:" % (addr[0], addr[1]))
            thread = threading.Thread(target=MainProcess, args=(tcpCliSock,))
            thread.start()
            thread.join()
        except KeyboardInterrupt:
            print()
            print("Disconnected.")
            tcpSerSock.close()
            break


if __name__ == "__main__":
    main()

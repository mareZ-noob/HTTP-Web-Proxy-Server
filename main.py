import codecs
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
    except (TimeoutError, ConnectionError, BrokenPipeError) as error:
        print(error)
        print("Creating client failed.")
        exit(0)
    return tcpCliSock


def NotFound(tcpSock: socket):
    data = b""
    try:
        f = open(NOT_FOUND_PAGE, "rb")
        data = f.read()
    except (IOError, FileNotFoundError) as error:
        print(error)
        data = b"403 Not Found"
    header = b"HTTP/1.1 403 Not Found\r\n"
    res = header + data + b"\r\n\r\n"
    tcpSock.send(res)


def LoadDatas():
    global JSON_DATAS
    try:
        with codecs.open(filename=CONFIG_FILE, mode="r", encoding="utf-8") as ifs:
            JSON_DATAS = json.load(ifs)
    except (IOError, FileNotFoundError) as error:
        print(error)


def WhiteListing():
    global WHITE_LIST
    try:
        for data in JSON_DATAS:
            WHITE_LIST[data["allow_host"]] = data
    except (IOError, FileNotFoundError, SyntaxError, IndexError) as error:
        print(error)


def CheckWebsite(web: str):
    # Check if web in config file
    check = -1
    for data in JSON_DATAS:
        if data["allow_host"] in web:
            check = 1
    if check == -1:
        return check

    flag = 1  # 1 -> Deactivate server | 0 -> Activate server
    for data in JSON_DATAS:
        if data["allow_host"] in web:
            time_start = str(data["time_start"])
            time_end = str(data["time_end"])
            if time_start <= CURRENT_TIME and CURRENT_TIME <= time_end:
                flag = 0

    return flag


def parseRequest(message: str):
    protocol = ""
    if message.find("http") != -1:
        protocol = "http"

    method = message.split("\r\n")[0].split()[0]
    url = message.split("\r\n")[0].split()[1]
    version = message.split("\r\n")[0].split()[2]
    host = message.split("\r\n")[1].split()[1]
    path = filename = ""
    if url.find("://") != -1:
        path = url.partition("://")[2]
        file = path.partition("/")[2]
        filename = "/" + file
    return {
        "Method": method,
        "Protocol": protocol,
        "Url": url,
        "Version": version,
        "Host": host,
        "File": filename,
    }


def saveCache(message: str, response: bytes):
    req = parseRequest(message)
    check = False
    for img in SUPPORTED_IMAGE_EXTENSIONS:
        if img in req["File"]:
            check = True

    if check is False:
        return
    filePath = req["Host"] + req["File"]
    imgPath = os.path.join(CACHE_FOLDER_PATH, filePath)
    # Image extensions to .dat
    filename = os.path.basename(imgPath)
    httpHeaderFile = filename.replace(filename.split(".")[-1], "") + "txt"
    httpHeaderPath = imgPath.replace(filename, httpHeaderFile)

    folder = imgPath.replace("/" + filename, "")
    if not os.path.exists(folder):
        os.makedirs(folder)

    # response = httpHeader + "\r\n\r\n" + image
    httpHeader, EOL, image = response.decode("ISO-8859-1").partition("\r\n\r\n")
    print("New cache.")
    with open(file=httpHeaderPath, mode="wb") as f:
        f.write(httpHeader.encode("ISO-8859-1"))
    with open(file=imgPath, mode="wb") as f:
        f.write(image.encode("ISO-8859-1"))


def loadCache(message: str):
    req = parseRequest(message)
    check = False
    for img in SUPPORTED_IMAGE_EXTENSIONS:
        if img in req["File"]:
            check = True

    if check is False:
        return False, b""

    filePath = req["Host"] + req["File"]
    imgPath = os.path.join(CACHE_FOLDER_PATH, filePath)
    # Image extensions to .dat
    filename = os.path.basename(imgPath)
    httpHeaderFile = filename.replace(filename.split(".")[-1], "") + "txt"
    httpHeaderPath = imgPath.replace(filename, httpHeaderFile)

    image = httpHeader = b""
    if os.path.exists(imgPath) is False:
        return False, image
    if os.path.exists(httpHeaderPath) is False:
        return False, httpHeader
    modifyTime = datetime.fromtimestamp(os.path.getmtime(imgPath))
    if CURRENT_DATE_TIME - modifyTime > CACHE_EXPIRATION_TIME:
        return False, b""

    with open(imgPath, "rb") as f:
        image = f.read()
    with open(httpHeaderPath, "rb") as f:
        httpHeader = f.read()

    return True, image + "\r\n\r\n" + httpHeader


def handle_content_length(connection: socket, content_length: int):
    data = b""
    while len(data) < content_length:
        chunk = connection.recv(min(content_length - len(data), MAX_RECEIVE))
        if not chunk:
            break
        data += chunk
    return data


def handle_chunked_encoding(connection: socket):
    data = b""
    while True:
        chunk_header = connection.recv(MAX_RECEIVE).decode("ISO-8859-1").strip()
        chunk_size = int(chunk_header, 16)

        if chunk_size == 0:
            break

        chunk = b""
        while len(chunk) < chunk_size:
            remaining_bytes = chunk_size - len(chunk)
            chunk += connection.recv(min(remaining_bytes, MAX_RECEIVE))

        data += chunk
        # EOF
        connection.recv(2)

    return data


# def handleMethod(message: bytes):
#     # Load from cache
#     if loadCache(message.decode("ISO-8859-1"))[0] is True:
#         print("Cache loads successfully.")
#         return loadCache(message.decode("ISO-8859-1"))[1]
#     req = parseRequest(message.decode("ISO-8859-1"))

#     # Connect to web server
#     webServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     webServerSock.connect((req["Host"], HTTP_PORT))

#     request = message.decode("ISO-8859-1")
#     response = b""
#     if request.find("Transfer-Encoding: chunked") != -1:
#         # Use Connection: keep-alive
#         request = request + "\r\nConnection: keep-alive\r\n\r\n"
#         with open(file="hi.txt", mode="w") as f:
#             f.write(request)
#         webServerSock.send(request.encode())
#         response = handle_chunked_encoding(webServerSock)
#     elif request.find("Content-Length: ") != -1:
#         # Use Connection: keep-alive
#         tmp = request.split("Content-Length: ")[1]
#         length = tmp.split("\r\n")[0]
#         # request = request + "\r\nConnection: keep-alive\r\n\r\n"
#         with open(file="hello.txt", mode="w") as f:
#             f.write(request)
#         webServerSock.send(request.encode())
#         response = handle_content_length(webServerSock, int(length))
#     else:
#         # Use Connection: close
#         request = request + "\r\nConnection: close\r\n\r\n"
#         webServerSock.send(request.encode())

#         blocks = []
#         while True:
#             mess = webServerSock.recv(MAX_RECEIVE)
#             if not mess:
#                 break
#             blocks.append(mess)
#         response = b"".join(blocks)

#     saveCache(message.decode("ISO-8859-1"), response)
#     webServerSock.close()
#     return response


def handleMethod(message: bytes):
    # Load from cache
    if loadCache(message.decode("ISO-8859-1"))[0] is True:
        print("Cache loads successfully.")
        return loadCache(message.decode("ISO-8859-1"))[1]
    req = parseRequest(message.decode("ISO-8859-1"))

    # Connect to web server
    webServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    webServerSock.connect((req["Host"], HTTP_PORT))

    request = message.decode("ISO-8859-1")
    # Use Connection: close
    request = request + "\r\nConnection: close\r\n\r\n"
    webServerSock.send(request.encode())

    blocks = []
    while True:
        mess = webServerSock.recv(MAX_RECEIVE)
        if not mess:
            break
        blocks.append(mess)
    response = b"".join(blocks)

    saveCache(message.decode("ISO-8859-1"), response)
    webServerSock.close()
    return response

def MainProcess(tcpCliSock: socket):
    # Read a request
    message = tcpCliSock.recv(MAX_RECEIVE)

    if message == b"":
        tcpCliSock.close()
        return

    req = parseRequest(message.decode("ISO-8859-1"))
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
        print("This page isn't in working hours.")
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    response = handleMethod(message)
    tcpCliSock.sendall(response)
    tcpCliSock.close()


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
            # Create client to server
            tcpCliSock, addr = tcpSerSock.accept()
            print("\nReceived connection from IP: %s - Port: %d:" % (addr[0], addr[1]))
            thread = threading.Thread(target=MainProcess, args=(tcpCliSock,))
            thread.start()
            thread.join()
        except KeyboardInterrupt as error:
            print(error)
            print("\nDisconnected.")
            tcpSerSock.close()
            break


if __name__ == "__main__":
    main()

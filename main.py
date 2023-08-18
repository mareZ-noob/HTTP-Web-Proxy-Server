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
MAX_RECEIVE = 1024

# Methods permission
ALLOW_METHOD = ["GET", "POST", "HEAD"]

# Images supported
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

# Config datas
JSON_DATAS = []

# End Define


class bcolors:
    reset = "\033[0m"
    gray = "\033[1;90m"
    red = "\033[1;31m"
    green = "\033[1;32m"
    yellow = "\033[1;33m"
    blue = "\033[1;34m"
    magenta = "\033[1;35m"
    cyan = "\033[1;36m"
    white = "\033[1;37m"


def CreateClient(host: str, post: int):
    try:
        tcpCliSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpCliSock.connect((host, post))
    except (TimeoutError, ConnectionError, BrokenPipeError) as error:
        print(error)
        print(f"{bcolors.red}[*] Creating client failed.{bcolors.reset}")
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
    # Load json to JSON_DATAS
    global JSON_DATAS
    try:
        with codecs.open(filename=CONFIG_FILE, mode="r", encoding="utf-8") as ifs:
            JSON_DATAS = json.load(ifs)
    except (IOError, FileNotFoundError) as error:
        print(error)


def CheckWebsite(web: str):
    # Check if web in config file
    check = -1
    for data in JSON_DATAS:
        if data["allow_host"] in web:
            check = 1
    if check == -1:
        return check

    # Variable: flag = 1 -> 403 Not Found && flag = 0 -> Normal access
    flag = 1

    # Loop to find time start, time end of each website
    for data in JSON_DATAS:
        if data["allow_host"] in web:
            time_start = str(data["time_start"])
            time_end = str(data["time_end"])
            if time_start <= CURRENT_TIME and CURRENT_TIME <= time_end:
                flag = 0

    return flag


def parseRequest(message: str):
    # Parse received message from client
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

    # Check supported image extensions
    for img in SUPPORTED_IMAGE_EXTENSIONS:
        if img in req["File"]:
            check = True
    if check is False:
        return

    # Get image path and header path
    filePath = req["Host"] + req["File"]
    imgPath = os.path.join(CACHE_FOLDER_PATH, filePath)

    # Header to .txt
    filename = os.path.basename(imgPath)
    httpHeaderFile = filename.replace(filename.split(".")[-1], "") + "txt"
    httpHeaderPath = imgPath.replace(filename, httpHeaderFile)

    # Create folder for image file and header file
    folder = imgPath.replace("/" + filename, "")
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Idea: response = httpHeader + "\r\n\r\n" + image
    httpHeader, eol2, image = response.decode("ISO-8859-1").partition("\r\n\r\n")
    print(f"{bcolors.green}[*] New cache.{bcolors.reset}")
    with open(file=httpHeaderPath, mode="wb") as f:
        f.write(httpHeader.encode("ISO-8859-1"))
    with open(file=imgPath, mode="wb") as f:
        f.write(image.encode("ISO-8859-1"))


def loadCache(message: str):
    req = parseRequest(message)
    check = False

    # Check supported image extensions
    for img in SUPPORTED_IMAGE_EXTENSIONS:
        if img in req["File"]:
            check = True
    if check is False:
        return False, b""

    # Get image path and header path
    filePath = req["Host"] + req["File"]
    imgPath = os.path.join(CACHE_FOLDER_PATH, filePath)

    # Header as .txt
    filename = os.path.basename(imgPath)
    httpHeaderFile = filename.replace(filename.split(".")[-1], "") + "txt"
    httpHeaderPath = imgPath.replace(filename, httpHeaderFile)

    # Check if it exists cache images
    image = httpHeader = b""
    if os.path.exists(imgPath) is False:
        return False, image
    if os.path.exists(httpHeaderPath) is False:
        return False, httpHeader
    modifyTime = datetime.fromtimestamp(os.path.getmtime(imgPath))

    # Expired cache images
    if CURRENT_DATE_TIME - modifyTime > CACHE_EXPIRATION_TIME:
        return False, b""

    # Read cache images and header
    with open(imgPath, "rb") as f:
        image = f.read()
    with open(httpHeaderPath, "rb") as f:
        httpHeader = f.read()

    return True, image + b"\r\n\r\n" + httpHeader


def handleMethod(message: bytes):
    # Load from cache
    if loadCache(message.decode("ISO-8859-1"))[0] is True:
        print(f"{bcolors.green}[*] Cache loads successfully.{bcolors.reset}")
        return loadCache(message.decode("ISO-8859-1"))[1]
    req = parseRequest(message.decode("ISO-8859-1"))

    # Connect to web server
    webServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    webServerSock.connect((req["Host"], HTTP_PORT))

    # Use Connection: keep-alive (default on HTTP/1.1)
    request = message.decode()
    user_agent = message.decode().split("User-Agent: ")[1].split("\r\n")[0]
    accept_encoding = message.decode().split("Accept-Encoding: ")[1].split("\r\n")[0]
    request = request.replace("User-Agent: " + user_agent + "\r\n", "")
    request = request.replace("Accept-Encoding: " + accept_encoding + "\r\n", "")

    # Receive a part of response to split header and the remains
    print(f"{bcolors.magenta}[*] Receive response from web server.{bcolors.reset}")
    webServerSock.send(request.encode())
    response = webServerSock.recv(MAX_RECEIVE)
    part = response.decode("ISO-8859-1")
    header, eol2, body = part.partition("\r\n\r\n")

    full_response = b""
    if part.lower().find("transfer-encoding: chunked") != -1:
        # Idea: Loop until find the mark end of chunk: \r\n0\r\n\r\n
        print(f"{bcolors.blue}[*] Transfer-Encoding: chunked Case.{bcolors.reset}")
        data = b""
        while True:
            chunk = webServerSock.recv(MAX_RECEIVE)
            if chunk == b"":
                break
            if b"\r\n0\r\n\r\n" in chunk:
                data += chunk
                break
            data += chunk
        full_response = response + data
    elif part.lower().find("content-length: ") != -1:
        # Idea: Get the length of message then find the remains messages
        print(f"{bcolors.blue}[*] Content-Lenght: Case.{bcolors.reset}")
        tmp = part.lower().split("content-length: ")[1]
        length = int(tmp.split("\r\n")[0])
        remains = length - len(body)
        data = b""
        while remains > 0:
            chunk = webServerSock.recv(min(MAX_RECEIVE, remains))
            if chunk == b"":
                break
            data += chunk
            remains -= len(chunk)
            if remains == 0:
                break
        full_response = response + data

    saveCache(message.decode("ISO-8859-1"), full_response)
    webServerSock.close()
    return full_response


# Proxy
def MainProcess(tcpCliSock: socket):
    # Receive a message from client
    message = tcpCliSock.recv(MAX_RECEIVE)

    if message == b"":
        tcpCliSock.close()
        return

    req = parseRequest(message.decode("ISO-8859-1"))
    for key, value in req.items():
        print(key, ":", value)

    # Check method
    if req["Method"] not in ALLOW_METHOD:
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    # Website permission
    if CheckWebsite(req["Host"]) == -1:
        print(
            f"{bcolors.red}[*] You don't currently have permission to access this page.{bcolors.reset}"
        )
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return
    elif CheckWebsite(req["Host"]) == 1:
        print(f"{bcolors.red}[*] This page isn't in working hours.{bcolors.reset}")
        NotFound(tcpCliSock)
        tcpCliSock.close()
        return

    # Reply to client
    response = handleMethod(message)
    tcpCliSock.sendall(response)
    tcpCliSock.close()


def main():
    # Create cache folder
    if not os.path.exists(CACHE_DIRECTORY):
        os.makedirs(CACHE_DIRECTORY)

    # Create a server
    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.bind((PROXY_HOST, PROXY_PORT))
    tcpSerSock.listen(MAX_CONNECTION)

    # Load datas
    LoadDatas()

    while True:
        try:
            # Create client to server
            tcpCliSock, addr = tcpSerSock.accept()
            print(
                f"\n{bcolors.yellow}[*] Received connection from IP: %s - Port: %d:{bcolors.reset}"
                % (addr[0], addr[1])
            )

            # Create threading
            thread = threading.Thread(target=MainProcess, args=(tcpCliSock,))
            thread.start()
            thread.join()
        except KeyboardInterrupt as error:
            print(error)
            print(f"\n{bcolors.red}[*] Disconnected.{bcolors.reset}")
            tcpSerSock.close()
            break


if __name__ == "__main__":
    main()

import socket
import struct
from PIL import Image
import numpy
import io
import logging
import socketserver
from threading import Condition
from http import server
from kafka import KafkaProducer
import time
import cv2

input_topic = 'input'
output_topic = 'output'
brokers = "G01-01:2181,G01-02:2181,G01-03:2181,G01-04:2181,G01-05:2181,G01-06:2181,G01-07:2181,G01-08:2181," \
          "G01-09:2181,G01-10:2181,G01-11:2181,G01-12:2181,G01-13:2181,G01-14:2181,G01-15:2181,G01-16:2181"
producer = KafkaProducer(bootstrap_servers='G01-01:9092', compression_type='gzip', batch_size=163840,
                         buffer_memory=33554432, max_request_size=20485760)
server_socket = socket.socket()
# 绑定socket通信端口
server_socket.bind(('10.244.27.7', 23333))
server_socket.listen(0)

connection = server_socket.accept()[0].makefile('rb')

PAGE = """\
<html>
<head>
<title>camera MJPEG streaming demo</title>
</head>
<body>
<h1>PiCamera MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    # 获得图片长度
                    image_len = struct.unpack('<L', connection.read(struct.calcsize('<L')))[0]
                    print(image_len)
                    if not image_len:
                        break

                    image_stream = io.BytesIO()
                    # 读取图片
                    image_stream.write(connection.read(image_len))

                    image_stream.seek(0)

                    image = Image.open(image_stream)
                    cv2img = numpy.array(image, dtype=numpy.uint8)[:, :, ::-1]

                    # send image stream to kafka
                    print('imgshape', cv2img.shape)
                    producer.send(input_topic, value=cv2.imencode('.jpg', cv2img)[1].tobytes(), key=str(int(time.time() * 1000)).encode('utf-8'))
                    producer.flush()

                    imgbuffer = image_stream.getvalue()

                    # producer.send(input_topic, value=imgbuffer, key=str(int(time.time() * 1000)).encode('utf-8'))
                    # producer.flush()

                    # 写入http响应
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(imgbuffer))
                    self.end_headers()
                    self.wfile.write(imgbuffer)
                    self.wfile.write(b'\r\n')


            except Exception as e:
                logging.warning(
                    'errror streaming client %s: %s',
                    self.client_address, str(e))

        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


output = StreamingOutput()

try:
    address = ('10.244.27.7', 12345)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
except Exception as e:
    print(e)

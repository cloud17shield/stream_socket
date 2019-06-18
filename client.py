import socket
import struct
import time
import cv2

client_socket = socket.socket()
client_socket.connect(('202.45.128.135', 60108))

connection = client_socket.makefile('wb')

try:
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    while True:
        # 读取图片
        ret, frame = cap.read()
        frame = cv2.resize(frame, (400, 300), interpolation=cv2.INTER_CUBIC)
        # cv2.imshow("capture", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        # 转换为jpg格式
        img_str = cv2.imencode('.jpg', frame)[1].tobytes()
        # 获得图片长度
        s = struct.pack('<L', len(img_str))
        # print(s)
        # 将图片长度传输到服务端
        connection.write(s)
        connection.flush()
        # 传输图片流
        connection.write(img_str)
        connection.flush()
        # 限制帧数
        time.sleep(0.1)

except Exception as e:
    print(e)

finally:
    connection.close()
    client_socket.close()

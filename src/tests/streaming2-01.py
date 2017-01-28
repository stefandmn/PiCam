#!/usr/bin/python

import cv2
import threading
import traceback
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
from PIL import Image
import StringIO
import time

# Class: StreamHandler
class StreamHandler(BaseHTTPRequestHandler):
	# Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseHTTPRequestHandler.__init__(self, request, client_address, server)

	# Method: do_GET
	def do_GET(self):
		try:
			self.send_response(200)
			self.send_header("Connection", "close")
			self.send_header("Max-Age", "0")
			self.send_header("Expires", "0")
			self.send_header("Cache-Control", "no-cache, private")
			self.send_header("Pragma", "no-cache")
			self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--jpgboundary")
			self.end_headers()
			while True:
				if self._server.getData() is None:
					continue
				frameRGB = cv2.cvtColor(self._server.getData(), cv2.COLOR_BGR2RGB)
				jpg = Image.fromarray(frameRGB)
				buffer = StringIO.StringIO()
				jpg.save(buffer, 'JPEG')
				self.wfile.write("--jpgboundary\n")
				self.send_header("Content-type", "image/jpeg")
				self.send_header('Content-length',str(buffer.len))
				self.end_headers()
				jpg.save(self.wfile, 'JPEG')
				time.sleep(self._server.getSleep())
			return
		except BaseException as baseerr:
			self.send_error(500, 'Streaming Server Error: \n\n%s' % str(baseerr))
			traceback.print_exc()


# Class: StreamingServer
class StreamingServer(ThreadingMixIn, HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleep=0.02):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleep = sleep

	# Method: getFrame
	def getData(self):
		return self._frame

	# Method: getFrame
	def setData(self, frame):
		self._frame = frame

	# Method: getSleep
	def getSleep(self):
		return self._sleep

	# Method: setSleep
	def setSleep(self, sleep):
		self._sleep	= sleep


def main():
	capture = cv2.VideoCapture(0)
	capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 640) 
	capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
	capture.set(cv2.cv.CV_CAP_PROP_BRIGHTNESS, 0.5)
	capture.set(cv2.cv.CV_CAP_PROP_CONTRAST, 0.5)

	server = StreamingServer(('0.0.0.0', 9081), StreamHandler, frame=None, sleep=0.02)

	try:
		streamthread = threading.Thread(target=server.serve_forever)
		streamthread.daemon = True
		streamthread.start()
		print "Streaming server started.."
		while True:
			retval,image = capture.read()
			if not retval:
				break
			server.setData(image)
			time.sleep(0.02)
	except KeyboardInterrupt:
		capture.release()
		server.socket.close()


if __name__ == '__main__':
	main()


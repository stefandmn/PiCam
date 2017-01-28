#!/usr/bin/python

import threading
import traceback
import datetime
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
from PIL import Image
import StringIO
import numpy
import time
import cv2

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

class Motion:
	def __init__(self):
		# initialize the first frame in the video stream
		self.__gray = None
		self.__grsz = (320,240)

	def run(self, frame):
		# resize the frame, convert it to grayscale, and blur it
		gray = cv2.resize(frame, self.__grsz)
		gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
		gray = cv2.GaussianBlur(gray, (21, 21), 0)

		# if the first frame is None, initialize it
		if self.__gray is None:
			self.__gray = gray
			return

		# compute the absolute difference between the current frame and first frame
		frameDelta = cv2.absdiff(self.__gray, gray)
		thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

		# dilate the thresholded image to fill in holes, then find contours on thresholded image
		thresh = cv2.dilate(thresh, None, iterations=2)
		(cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
		self.__gray = gray
		
		# loop over the contours
		for c in cnts:
			xsize = numpy.size(frame, 1) / self.__grsz[0]
			ysize = numpy.size(frame, 0) / self.__grsz[1]
			
			# if the contour is too small, ignore it
			if cv2.contourArea(c) < 100:
				continue
			# compute the bounding box for the contour, draw it on the frame, and update the text
			(x, y, w, h) = cv2.boundingRect(c)
			cv2.rectangle(frame, (x * xsize, y * ysize), ( (x + w) * xsize, (y + h) * ysize), (0, 255, 0), 1)

		# draw the text and timestamp on the frame
		cv2.putText(frame, "CAM 01", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
		cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)


def main():
	motion = Motion()
	capture = cv2.VideoCapture(0)
	capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 640) 
	capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
	capture.set(cv2.cv.CV_CAP_PROP_BRIGHTNESS, 0.5)
	capture.set(cv2.cv.CV_CAP_PROP_CONTRAST, 0.5)

	try:			
		server = StreamingServer(('0.0.0.0', 9081), StreamHandler, frame=None, sleep=0.02)
		streamthread = threading.Thread(target=server.serve_forever)
		streamthread.daemon = True
		streamthread.start()
		print "Streaming and motion servers started.."
		while True:
			retval,image = capture.read()
			if not retval:
				break
			motion.run(image)
			server.setData(image)
			time.sleep(0.02)
	except KeyboardInterrupt:
		capture.release()
		server.socket.close()


if __name__ == '__main__':
	main()

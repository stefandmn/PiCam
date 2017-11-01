#!/usr/bin/env python

import cv
import time
import datetime
import threading
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn

class MyHandler(BaseHTTPRequestHandler):

	#Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseHTTPRequestHandler.__init__(self, request, client_address, server)
	
	#Method: do_GET
	def do_GET(self):
		try:
			self.send_response(200)
			self.send_header("Connection", "close")
			self.send_header("Max-Age", "0")
			self.send_header("Expires", "0")
			self.send_header("Cache-Control", "no-cache, private")
			self.send_header("Pragma", "no-cache")
			self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--BOUNDARYSTRING")
			self.end_headers()			
			while True:
				if self._server.getData() is None:
					continue
				JpegData = cv.EncodeImage(".jpeg", self._server.getData(), (cv.CV_IMWRITE_JPEG_QUALITY,75)).tostring()
				
				self.wfile.write("--BOUNDARYSTRING\r\n")
				self.send_header("Content-type", "image/jpeg")
				self.send_header("Content-Length", str(len(JpegData)))
				self.end_headers()
				
				self.wfile.write(JpegData)
				self.wfile.write("\r\n")
				
				time.sleep(self._server.getSleep())
			return
		except BaseException as baseerr:
			self.send_error(500,'PiCam Streaming Server Error: \r\n\r\n%s' % str(baseerr))

			
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):

	#Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleeptime=0.05):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleeptime = sleeptime

	#Method: getFrame
	def getFrame(self):
		return self._frame

	#Method: getFrame
	def setFrame(self, frame):
		self._frame = frame

	#Method: getTimesleep
	def getTimesleep(self):
		return self._sleeptime


class Motion:

	def __init__(self):
		self.capture = cv.CaptureFromCAM(0)
		cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_WIDTH, 640)
		cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
		self.sleeptime = 0.05
		#Start streaming
		self.server = ThreadedHTTPServer(('0.0.0.0', 8080), MyHandler, frame=None, sleeptime=self.sleeptime)
		streamthread = threading.Thread(target = self.server.serve_forever)
		streamthread.daemon = True
		streamthread.start()
		print 'Starting Streaming Server...'

	def run(self):
		try:
			first = True

			while True:
				color_image = cv.QueryFrame(self.capture)

				# Smooth to get rid of false positives
				cv.Smooth(color_image, color_image, cv.CV_GAUSSIAN, 3, 0)

				if first:
					difference = cv.CloneImage(color_image)
					temp = cv.CloneImage(color_image)
					grey_image = cv.CreateImage(cv.GetSize(color_image), cv.IPL_DEPTH_8U, 1)
					moving_average = cv.CreateImage(cv.GetSize(color_image), cv.IPL_DEPTH_32F, 3)
					cv.ConvertScale(color_image, moving_average, 1.0, 0.0)
					first = False
				else:
					cv.RunningAvg(color_image, moving_average, 0.020, None)

				# Convert the scale of the moving average.
				cv.ConvertScale(moving_average, temp, 1.0, 0.0)

				# Minus the current frame from the moving average.
				cv.AbsDiff(color_image, temp, difference)

				# Convert the image to grayscale.
				cv.CvtColor(difference, grey_image, cv.CV_RGB2GRAY)

				# Convert the image to black and white.
				cv.Threshold(grey_image, grey_image, 70, 255, cv.CV_THRESH_BINARY)

				# Dilate and erode to get people blobs
				cv.Dilate(grey_image, grey_image, None, 18)
				cv.Erode(grey_image, grey_image, None, 10)

				storage = cv.CreateMemStorage(0)
				contour = cv.FindContours(grey_image, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)

				points = []
				movementArea = 0

				while contour:
					bound_rect = cv.BoundingRect(list(contour))
					contour = contour.h_next()

					# Compute the bounding points to the boxes that will be drawn on the screen
					pt1 = (bound_rect[0], bound_rect[1])
					pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])

					# Add this latest bounding box to the overall area that is being detected as movement
					movementArea += ( ( pt2[0] - pt1[0] ) * ( pt2[1] - pt1[1] ) )
					points.append(pt1)
					points.append(pt2)
					cv.Rectangle(color_image, pt1, pt2, cv.CV_RGB(255,0,0), 1)

				if movementArea > 0:
					print 'MA: ' + repr(movementArea)
					#cv.SaveImage("/root/temp/samples/" + "photo" + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + ".png", color_image)

				#if len(points):
				#	center_point = reduce(lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), points)
				#	cv.Circle(color_image, center_point, 40, cv.CV_RGB(255, 255, 255), 1)
				#	cv.Circle(color_image, center_point, 30, cv.CV_RGB(255, 100, 0), 1)
				#	cv.Circle(color_image, center_point, 20, cv.CV_RGB(255, 255, 255), 1)
				#	cv.Circle(color_image, center_point, 10, cv.CV_RGB(255, 100, 0), 1)

				self.server.setFrame(color_image)
				time.sleep(0.01)
		except KeyboardInterrupt:
			print '^C received, Shutting down server'
			self.server.shutdown()
			self.server.server_close()
		

if __name__=="__main__":
	motion = Motion()
	motion.run()

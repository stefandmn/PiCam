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
				if self._server.getFrame() is None:
					continue
				JpegData = cv.EncodeImage(".jpeg", self._server.getFrame(), (cv.CV_IMWRITE_JPEG_QUALITY, 75)).tostring()
				
				self.wfile.write("--BOUNDARYSTRING\r\n")
				self.send_header("Content-type", "image/jpeg")
				self.send_header("Content-Length", str(len(JpegData)))
				self.end_headers()
				
				self.wfile.write(JpegData)
				self.wfile.write("\r\n")
				
				time.sleep(self._server.getSleeptime())
			return
		except BaseException as baseerr:
			self.send_error(500,'PiCam Streaming Server Error: \r\n\r\n%s' % str(baseerr))

			
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):

	#Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, sleeptime=0.05):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self.capture = cv.CaptureFromCAM(0)
		self.sleeptime = sleeptime

	#Method: getFrame
	def getFrame(self):
		return cv.QueryFrame(self.capture)
		
	#Method: getTimesleep
	def getSleeptime(self):
		return self.sleeptime


if __name__=="__main__":
	server = ThreadedHTTPServer(('0.0.0.0', 8080), MyHandler, sleeptime=0.01)
	print 'Starting Streaming Server...'
	server.serve_forever()

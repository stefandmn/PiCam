#!/usr/bin/python

__project__ = "Clue"
__module__ = "PiCam"
__author__ = "SDA"
__email__ = "damian.stefan@gmail.com"
__copyright__ = "Copyright (C) 2015-2016, AMSD"
__license__ = "GPL"
__version__ = "1.1.7"
__verbose__ = False

import os
import io
import cv
import sys
import time
import socket
import getopt
import datetime
import threading
import traceback
from PIL import Image
from picamera import PiCamera
from SocketServer import ThreadingMixIn, BaseRequestHandler, TCPServer
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


# Class: Camera
class Camera(threading.Thread):
	def __init__(self, id, motion=False, streaming=False):
		# Validate camera id input parameter
		if id is not None and str(id).startswith('#'):
			id = int(filter(str.isdigit, id))
		if id is None or not isinstance(id, int) or id < 0:
			raise RuntimeError('Invalid camera identifier: ' + id)
		# Initialize threading options
		threading.Thread.__init__(self)
		self.name = "Camera #" + str(id)
		self._stop = threading.Event()
		# Initialize class public variables (class parameters)
		self._id = id
		self._resolution = None
		self._framerate = None
		self._sleeptime = 0.05
		# Streaming properties
		self._s_sleep = 0.05
		self._s_port = 9080
		# Initialize class private variables
		self._exec = False
		self._lock = True
		self._frame = None
		# Define tools
		self._camera = None
		self._stream = None
		self._motion = None
		# Identify type of camera and initialize camera device
		self.setCameraOn()
		# Activate recording if was specified during initialization
		if motion:
			self._applyMotion()
		if streaming:
			self._applyStreaming()
		self.log("Service has been initialized")

	# Method: getId
	def getId(self):
		return self._id

	# Method: getFrame
	def getFrame(self):
		return self._frame

	# Method: setFrame
	def setFrame(self):
		if not self._lock and self._camera is not None:
			if isinstance(self._camera, PiCamera):
				byte_buffer = io.BytesIO()
				self._camera.capture(byte_buffer, format='jpeg', use_video_port=True)
				byte_buffer.seek(0)
				pil = Image.open(byte_buffer)
				self._frame = cv.CreateImageHeader(self._camera.resolution, cv.IPL_DEPTH_8U, 3)
				cv.SetData(self._frame, pil.tostring())
				cv.CvtColor(self._frame, self._frame, cv.CV_RGB2BGR)
			else:
				self._frame = cv.QueryFrame(self._camera)
			cv.PutText(self._frame, "CAM " + str(self.getId()).rjust(2, '0'), (5, 15), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .35, .35, 0.0, 1, cv.CV_AA), (255, 255, 255))

	# Method: _applyMotion
	def _applyMotion(self):
		self._motion = Motion(self)

	# Method: _runMotionDetection
	def _runMotionDetection(self):
		if self.isMotionEnabled():
			frame = self.getFrame()
			self._motion.detect(frame)

	# Method: isMotionActive
	def isMotionEnabled(self):
		return self._motion is not None

	# Method: _setStreaming
	def _applyStreaming(self):
		try:
			self._stream = StreamServer(('0.0.0.0', self._s_port), StreamHandler, frame=self.getFrame(), sleeptime=self._s_sleep)
			streamthread = threading.Thread(target=self._stream.serve_forever)
			streamthread.daemon = True
			streamthread.start()
			self.log("Streaming started on " + str(self._stream.server_address))
		except IOError as ioerr:
			self.log(["Streaming initialization failed:", ioerr])
			self._stream = None

	# Method: runStreaming
	def _runStreamingBroadcast(self):
		if self.isStreamingEnabled():
			try:
				if self._stream is not None:
					self._stream.setFrame(self.getFrame())
			except IOError as ioerr:
				self.log(["Sending streaming data failed:", ioerr])

	# Method: isStreaming
	def isStreamingEnabled(self):
		return self._stream is not None

	# Method: stop
	def stop(self):
		self._exec = False
		# Stop recording
		if self.isMotionEnabled():
			self.setMotionOff()
		# Stop streaming
		if self.isStreamingEnabled():
			self.setStreamingOff()
		# Stop camera
		self.setCameraOff()
		# Stop this thread
		self._stop.set()
		self.log("Service has been stopped")

	# Method: stopped
	def stopped(self):
		return self._stop.isSet()

	# Method: log
	def log(self, data):
		type, message = tomsg(data)
		if message != '':
			print "%s | %s %s > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, self.name, message)

	# Method: start
	def run(self):
		self._exec = True
		# Run surveillance workflow
		while self._exec:
			try:
				# Capture next frame
				self.setFrame()
				# If motion recording feature is active identify motion and save pictures
				self._runMotionDetection()
				# If the streaming is active send the picture through the streaming channel
				self._runStreamingBroadcast()
				# Sleep for couple of seconds or milliseconds
				time.sleep(self._sleeptime)
			except BaseException as baserr:
				self.log(["Camera workflow failed:", baserr])
				self.stop()

	# Method: setCameraOn
	def setCameraOn(self):
		if self._camera is None:
			try:
				self._lock = True
				if self._id == 0:
					self._camera = PiCamera()
					if self._resolution is not None:
						self._camera.resolution = self._resolution
					if self._framerate is not None:
						self._camera.framerate = self._framerate
				else:
					self._camera = cv.CaptureFromCAM(self._id - 1)
					if self._resolution is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
					if self._framerate is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Camera service initialization failed:", baseerr])
		else:
			self.log("Camera service is already started")

	# Method: setCameraOff
	def setCameraOff(self):
		if self._camera is not None:
			try:
				self._lock = True
				# For PiCamera call close method
				if isinstance(self._camera, PiCamera):
					self._camera.close()
				# Destroy Camera instance
				del self._camera
				self._camera = None
			except BaseException as baseerr:
				self.log(["Camera service has been stopped with errors:", baseerr])
				self._camera = None
		else:
			self.log("Camera service is already stopped")

	# Method: setCameraResolution
	def setCameraResolution(self, resolution):
		if self._camera is not None and resolution is not None:
			try:
				self._lock = True
				# Wait 1 second for the usecase when the resolution is set in the same time with the camera start
				time.sleep(1)
				# Set value
				self._resolution = (int(resolution.split(',')[0].strip()), int(resolution.split(',')[1].strip()))
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.resolution = self._resolution
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
				self._lock = False
			except BaseException as baseerr:
				self.log(["Applying camera resolution failed:", baseerr])

	# Method: setCameraFramerate
	def setCameraFramerate(self, framerate):
		if self._camera is not None and framerate is not None:
			try:
				self._lock = True
				# Set value
				self._framerate = framerate
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.framerate = self._framerate
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Applying camera framerate failed:", baseerr])

	# Method: setCameraSleeptime
	def setCameraSleeptime(self, sleeptime):
		self._sleeptime = sleeptime

	# Method: setMotionOn
	def setMotionOn(self):
		if not self.isMotionEnabled():
			self._applyMotion()
		else:
			self.log("Motion detection function is already enabled")

	# Method: setMotionOff
	def setMotionOff(self):
		if self.isMotionEnabled():
			self._motion = None
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionDetectionRecording
	def setMotionDetectionRecording(self, recording):
		if self.isMotionEnabled():
			self._motion.setRecording(recording)
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionRecordingLocation
	def setMotionRecordingLocation(self, location):
		if self.isMotionEnabled():
			self._motion.setLocation(location)
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionRecordingFormat
	def setMotionRecordingFormat(self, format):
		if self.isMotionEnabled():
			self._motion.setFormat(format)
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionRecordingThreshold
	def setMotionRecordingThreshold(self, threshold):
		if self.isMotionEnabled():
			self._motion.setThreshold(threshold)
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionDetectionContour
	def setMotionDetectionContour(self, contour):
		if self.isMotionEnabled():
			self._motion.setContour(contour)
		else:
			self.log("Motion detection function is not enabled")

	# Method: setStreamingOn
	def setStreamingOn(self):
		if not self.isStreamingEnabled():
			self._applyStreaming()
		else:
			self.log("Streaming function is already enabled")

	# Method: setStreamingOff
	def setStreamingOff(self):
		if self.isStreamingEnabled():
			try:
				self._stream.shutdown()
				self._stream.server_close()
				self._stream = None
			except IOError as ioerr:
				self.log(["Streaming function has been stopped with errors:", ioerr])
				self._stream = None
		else:
			self.log("Streaming function is not enabled")

	# Method: setStreamingPort
	def setStreamingPort(self, port):
		self._s_port = port
		if self.isStreamingEnabled():
			self.setStreamingOff()
			self.setStreamingOn()

	# Method: setStreamingSleep
	def setStreamingSleep(self, sleep):
		self._s_sleep = sleep
		if self.isStreamingEnabled():
			self._stream.setSleep(sleep)


# Class: Motion
class Motion:
	# Constructor
	def __init__(self, camera):
		# Set input parameters
		self._camera = camera
		# Initialize engine parameters
		self._gray = None
		self._size = (320,240)
		self._ismot = False
		self._fkmot = 0
		self._avmot = None
		# Motion detection parametrization
		self._format = 'image'
		self._contour = True
		self._recording = True
		self._threshold = 1000
		self._location = '/tmp'

	# Method: isContour
	def isContour(self):
		return self._contour

	# Method: setRecording
	def setContour(self, contour):
		self._contour = contour

	# Method: isRecording
	def isRecording(self):
		return self._recording

	# Method: setRecording
	def setRecording(self, recording):
		self._recording = recording

	# Method: getThreshold
	def getThreshold(self):
		return self._threshold

	# Method: setThreshold
	def setThreshold(self, threshold):
		self._threshold = threshold

	# Method: getLocation
	def getLocation(self):
		return self._location

	# Method: setLocation
	def setLocation(self, location):
		self._location = location

	# Method: getFormat
	def getFormat(self):
		return self._format

	# Method: setFormat
	def setFormat(self, format):
		self._format = format

	# Method: write
	def write(self, frame, text, area=0):
		try:
			clone = cv.CloneImage(frame)
			message = text + " @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
			cv.PutText(clone, message, (10, cv.GetSize(clone)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .32, .32, 0.0, 1, cv.CV_AA), (255, 255, 255))
			if self._format == 'image':
				filename = self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
				if area > 0:
					filename += "-" + str(area) + ".png"
				else:
					filename += ".png"
				cv.SaveImage(filename, clone)
			elif self._format == 'video':
				if not self._ismot:
					if self._avmot is not None:
						del(self._avmot)
						self._avmot = None
					filename = self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".avi"
					self._avmot = cv.CreateVideoWriter(filename, cv.CV_FOURCC('M', 'J', 'P', 'G'), 2, cv.GetSize(frame), True)
				if self._ismot and self._avmot is not None:
					cv.WriteFrame(self._avmot, clone)
		except IOError as ioerr:
			self._camera.log(["Saving motion data failed:", ioerr])
			self._camera._recording = False

	# Method: gray
	def gray(self, frame):
		copy = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_8U, 1)
		cv.CvtColor(frame, copy, cv.CV_RGB2GRAY)
		resize = cv.CreateImage(self._size, cv.IPL_DEPTH_8U, 1)
		cv.Resize(copy, resize)
		return resize

	# Method: absdiff
	def absdiff(self, frame1, frame2):
		output = cv.CloneImage(frame1)
		cv.AbsDiff(frame1, frame2, output)
		return output

	# Method: threshold
	def threshold(self, frame):
		cv.Threshold(frame, frame, 35, 255, cv.CV_THRESH_BINARY)
		cv.Dilate(frame, frame, None, 18)
		cv.Erode(frame, frame, None, 10)
		return frame

	# Method: contour
	def contour(self, move, frame):
		points = []
		area = 0
		xsize = cv.GetSize(frame)[0] / self._size[0]
		ysize = cv.GetSize(frame)[1] / self._size[1]
		storage = cv.CreateMemStorage(0)
		contour = cv.FindContours(move, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
		while contour:
			bound_rect = cv.BoundingRect(list(contour))
			contour = contour.h_next()
			# Compute the bounding points to the boxes that will be drawn on the screen
			pt1 = (bound_rect[0] * xsize, bound_rect[1] * ysize)
			pt2 = ((bound_rect[0] + bound_rect[2]) * xsize, (bound_rect[1] + bound_rect[3]) * ysize)
			# Add this latest bounding box to the overall area that is being detected as movement
			area += ((pt2[0] - pt1[0]) * (pt2[1] - pt1[1]))
			if self.isContour():
				points.append(pt1)
				points.append(pt2)
				cv.Rectangle(frame, pt1, pt2, cv.CV_RGB(255,0,0), 1)
		return area

	# Method: detect
	def detect(self, frame):
		if frame is not None:
			# Check if is needed to initialize the engine
			if self._gray is None:
				self.write(frame, "Start monitoring")
				self._gray = self.gray(frame)
			else:
				_gray = self.gray(frame)
				_diff = self.absdiff(self._gray, _gray)
				_move = self.threshold(_diff)
				_area = self.contour(_move, frame)
				# Evaluation
				if self.isRecording() and _area > self.getThreshold():
					self.write(frame, "Motion detected", _area)
					self._ismot = True
					self._fkmot = 0
				if self._ismot and self.isRecording() and _area <= self.getThreshold():
					self._fkmot += 1
					if self._fkmot > 10:
						self._ismot = False
						self._fkmot = 0
				self._gray = _gray


# Class: PiCamServerHandler
class PiCamServerHandler(BaseRequestHandler):
	# Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseRequestHandler.__init__(self, request, client_address, server)

	# Method: handle
	def handle(self):
		# Get client connection
		self.log("Connection from: " + str(self.client_address))
		# Receive data from client and process it
		command = self.request.recv(1024).strip()
		# Process client requests
		try:
			# Instantiate client structure to detect the action and subject
			self.log("Receiving command: " + str(command))
			data = StateData(command)
			# Action and subject evaluation
			if data.action == 'echo' and (data.subject is None or data.subject == 'server'):
				self.runEchoServer()
			if data.action == 'status' and (data.subject is None or data.subject == 'server'):
				self.runStatusServer()
			if data.action == 'stop' and data.subject == 'server':
				self.runStopServer()
			if data.action == 'start' and data.subject == 'service':
				self.runStartService(data.target)
			if data.action == 'stop' and data.subject == 'service':
				self.runStopService(data.target)
			if (data.action == 'set' or data.action == 'enable' or data.action == 'disable') and data.subject == 'property':
				self.runSetProperty(data)
			# Ending communication
			self.request.sendall("END")
		except BaseException as stderr:
			self.log(["Handling server command failed:", stderr])

	# Method: log
	def log(self, data, toClient=False):
		type, message = tomsg(data)
		if message != '':
			# Send message to the standard output or to the client console
			if toClient:
				if type is not None and type != '':
					self.request.sendall(type + "@" + message)
				else:
					self.request.sendall(message)
			else:
				print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)

	# Method: runStartService
	def runStartService(self, key):
		if key is not None:
			if key in self._server.getCameras():
				self.log("Camera " + key + " is already started", toClient=True)
			else:
				camera = Camera(key)
				camera.setStreamingPort(self._server.server_address[1] + 1 + camera.getId())
				camera.start()
				self._server.getCameras()[key] = camera
				self.log("Camera " + key + " has been started", toClient=True)
		else:
			self.log("Camera identifier was not specified", toClient=True)

	# Method: runStopService
	def runStopService(self, key):
		if key is not None:
			if key in self._server.getCameras():
				camera = self._server.getCameras()[key]
				camera.stop()
				del self._server.getCameras()[key]
				self.log("Camera " + key + " has been stopped", toClient=True)
			else:
				self.log("Camera " + key + " was not yet started", toClient=True)
		else:
			self.log("Camera could not be identified to stop service", toClient=True)

	# Method: runStopServer
	def runStopServer(self):
		self.log("Server shutting down")
		# Stop camera's threads
		if self._server.getCameras():
			keys = self._server.getCameras().keys()
			for key in keys:
				try:
					self.runStopService(key)
					time.sleep(1)
				except BaseException as baserr:
					self.log(["Stopping service on camera", key, "failed:", baserr])
		# Stop server thread
		self._server.shutdown()
		self._server.server_close()

	# Method: runEchoServer
	def runEchoServer(self):
		self.log(__project__ + " " + __module__ + " " + __version__ + ", " + __license__ + ", " + __copyright__, toClient=True)

	# Method: runStatusServer
	def runStatusServer(self):
		self.runEchoServer()

	# Method: runSetProperty
	def runSetProperty(self, data):
		# Translate enable and disable actions
		if data.action == data.getActions()[3]:
			data.property += " = True"
		if data.action == data.getActions()[4]:
			data.property += " = False"
		# Ge target camera
		if data.target in self._server.getCameras():
			# Identity target camera
			camera = self._server.getCameras()[data.target]
			# Identify property name and property value
			camprop = data.property.split('=')[0].strip()
			camdata = data.property.split('=')[1].strip()
			# Evaluate CameraStreaming property
			if camprop.lower() == data.getProperties()[0].lower():
				if str2bool(camdata):
					camera.setStreamingOn()
				else:
					camera.setStreamingOff()
			# Evaluate CameraMotionDetection property
			elif camprop.lower() == data.getProperties()[1].lower():
				if str2bool(camdata):
					camera.setMotionOn()
				else:
					camera.setMotionOff()
			# Evaluate CameraResolution property
			elif camprop.lower() == data.getProperties()[2].lower():
				camera.setCameraResolution(str(camdata))
			# Evaluate CameraFramerate property
			elif camprop.lower() == data.getProperties()[3].lower():
				camera.setCameraFramerate(int(camdata))
			# Evaluate CameraSleeptime property
			elif camprop.lower() == data.getProperties()[4].lower():
				camera.setCameraSleeptime(float(camdata))
			# Evaluate MotionDetectionContour property
			elif camprop.lower() == data.getProperties()[5].lower():
				camera.setMotionDetectionContour(str2bool(camdata))
			# Evaluate MotionDetectionRecording property
			elif camprop.lower() == data.getProperties()[6].lower():
				camera.setMotionDetectionRecording(str2bool(camdata))
			# Evaluate MotionRecordingFormat property
			elif camprop.lower() == data.getProperties()[7].lower():
				camera.setMotionRecordingFormat(str(camdata))
			# Evaluate MotionRecordingThreshold property
			elif camprop.lower() == data.getProperties()[8].lower():
				camera.setMotionRecordingThreshold(int(camdata))
			# Evaluate MotionRecordingLocation property
			elif camprop.lower() == data.getProperties()[9].lower():
				camera.setMotionRecordingLocation(str(camdata))
			# Evaluate StreamingPort property
			elif camprop.lower() == data.getProperties()[10].lower():
				camera.setStreamingPort(int(camdata))
			# Evaluate StreamingSleeptime property
			elif camprop.lower() == data.getProperties()[11].lower():
				camera.setStreamingSleep(float(camdata))
			# Answer to client
			self.log("Property '" + data.property + "' has been applied on camera " + data.target, toClient=True)
		else:
			self.log("Camera " + data.target + " is not yet started", toClient=True)


# Class: PiCamServer
class PiCamServer(ThreadingMixIn, TCPServer):
	# Global variables
	allow_reuse_address = True
	daemon_threads = True
	_cameras = {}

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True):
		TCPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._running = True

	# Method: getServerAddress
	def getServerAddress(self):
		return self.server_address

	# Method: getCameras
	def getCameras(self):
		return self._cameras

	# Method: isRunning
	def isRunning(self):
		return self._running

	# Method: shutdown
	def shutdown(self):
		self._running = False
		TCPServer.shutdown(self)


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
				time.sleep(self._server.getSleep())
			return
		except BaseException as baseerr:
			self.send_error(500, 'PiCam Streaming Server Error: \r\n\r\n%s' % str(baseerr))
			if __verbose__:
				traceback.print_exc()


# Class: StreamServer
class StreamServer(ThreadingMixIn, HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleep=0.05):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleep = sleep

	# Method: getFrame
	def getFrame(self):
		return self._frame

	# Method: getFrame
	def setFrame(self, frame):
		self._frame = frame

	# Method: getTimesleep
	def getSleep(self):
		return self._sleep

	# Method: setTimesleep
	def setSleep(self, sleeptime):
		self._sleep = sleeptime


# Class: PiCamClient
class PiCamClient:
	# Constructor
	def __init__(self, host='127.0.0.1', port=9079, api=False):
		# Set server host name and port
		self._host = host
		self._port = port
		# Validate host name
		if self._host is None or self._host == '':
			self._host = '127.0.0.1'
		# Validate port
		if self._port is None or not isinstance(self._port, int) or self._port <= 0:
			self._port = 9079
		self._onlog = True
		self._api = api
		self._apiOutMsg = []
		self._apiOutRes = True

	# Method: getServerAddress
	def getServerAddress(self):
		return self._host + ":" + str(self._port)

	# Method: connect
	def run(self, command):
		# Initialize output
		self._apiOutMsg = []
		self._apiOutRes = True
		# Declare server thread in case of the command will start it
		server = None
		# Instantiate Data module and parse (validate) input command
		try:
			data = StateData(command)
		except BaseException as baserr:
			errordata = ["Command translation failed:", baserr]
			if not self._api:
				self.log(errordata)
				sys.exit(1)
			else:
				self._logapi(errordata)
				return self._apiOutRes
		# Check if input command ask to start server instance
		if data.action == "start" and data.subject == "server":
			server = PiCamServer((self._host, self._port), PiCamServerHandler)
			serverhread = threading.Thread(target=server.serve_forever)
			serverhread.daemon = True
			serverhread.start()
			self.log(__module__ + " Server has been started")
			# Check if the current command is linked by other to execute the whole chain
			if data.hasLinkedData():
				data = data.getLinkedData()
				self._onlog = False
			else:
				data = None
		# Check if input comment ask to execute a server command
		while data is not None:
			try:
				# Send command to server instance
				self.log(__module__ + " Client is calling " + self.getServerAddress())
				client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				client.connect((self._host, self._port))
				# Generate command received from standard input
				command = data.getStatement()
				self.log("Sending command: " + command)
				client.sendall(command)
				# Getting the answers from server
				while True:
					answer = client.recv(1024)
					# Evaluate answer
					if answer != "END" and answer != '':
						if answer.startswith("INFO@") or answer.startswith("ERROR@"):
							level = answer.split('@', 1)[0]
							message = answer.split('@', 1)[1]
						else:
							level = None
							message = answer
						# Display message to standard output
						if message is not None and message != "":
							self.log(message, type=level, server=True)
							self._logapi(message, type=level)
					else:
						break
				client.close()
			except BaseException as baserr:
				errordata = ["Command failed:", baserr]
				self.log(errordata)
				self._logapi(errordata)
			finally:
				# Check if the current command is linked by other command
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
		# If server has been instantiated in this process wait to finish his execution
		if server is not None and not self._api:
			self._onlog = True
			while server.isRunning():
				try:
					time.sleep(1)
				except KeyboardInterrupt:
					print
					self.log('Interrupting server execution by user control')
					# Unlock server socket
					try:
						_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						_socket.connect(("localhost", self._port))
						_socket.sendall("stop server")
						_socket.close()
					except:
						# Nothing to do here
						self.log("Failed running silent shutdown")
		# End program execution
		if not self._api:
			print "End execution of PiCam.\n"
		else:
			return self._apiOutRes

	# Method: getApiResult
	def getApiResult(self):
		return self._apiOutRes

	# Method: getApiMessages
	def getApiMessages(self):
		return self._apiOutMsg

	# Method: log
	def log(self, data, type=None, server=False):
		type, message = tomsg(data, type)
		# Evaluate message and type
		if message != '' and not self._api:
			if not server:
				print "%s | %s Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)
			else:
				if self._onlog:
					print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)

	# Method: _logapi
	def _logapi(self, data, type=None):
		if self._api and self._onlog:
			type, message = tomsg(data, type)
			# Evaluate message and type
			if message != '':
				self._apiOutMsg.append(message)
				if type is not None and type == "ERROR": self._apiOutRes |= False


# Class: CmdData
class StateData:
	_actions = ['start', 'stop', 'set', 'enable', 'disable', 'status', 'echo']
	_subjects = ['server', 'service', 'property']
	_properties = ['CameraStreaming', 'CameraMotionDetection', 'CameraResolution', 'CameraFramerate', 'CameraSleeptime',
				   'MotionDetectionContour', 'MotionDetectionRecording', 'MotionRecordingFormat', 'MotionRecordingThreshold', 'MotionRecordingLocation',
				   'StreamingPort', 'StreamingSleeptime']
	_targetarticles = ['@', 'at', 'on', 'in', 'to']

	# Constructor
	def __init__(self, statement):
		self.action = None
		self.subject = None
		self.location = None
		self.property = None
		self.target = None
		# Validate input command and parse it
		if statement is not None and statement != '':
			if ' and ' in statement:
				self._parse(statement[0:statement.index(' and ')].split(' '))
				self._link = StateData(statement[statement.index(' and ') + 5:])
			else:
				self._parse(statement.split(' '))
				self._link = None
		else:
			raise RuntimeError("Invalid or null client command")
		# Validate obtained data structure
		if (self.action == "start" or self.action == "stop" or self.action == "status") and not (self.subject == "server" or self.subject == "service"):
			raise RuntimeError("Invalid subject of start/stop/status action: " + self.subject)
		elif (self.action == "set" or self.action == "enable" or self.action == "disable") and self.subject != "property":
			raise RuntimeError("Invalid action for property action: " + self.action)
		elif self.subject == 'server' and self.target is not None:
			raise RuntimeError("Invalid subject for the specified target: " + self.subject)
		elif self.action is None or self.action == '':
			raise RuntimeError("Action can not be null")
		elif self.subject is None or self.subject == '':
			raise RuntimeError("Subject can not be null")

	# Method: _parse
	def _parse(self, data):
		if data is not None and data != []:
			if data[0].strip() in self._actions:
				self.action = data[0].strip()
				del data[0]
				self._parse(data)
			elif data[0].strip() in self._subjects:
				self.subject = data[0].strip()
				del data[0]
				if self.subject == self._subjects[2]:
					index = None
					useprep = list(set(self._targetarticles) & set(data))
					useaction = list(set(self._actions) & set(data))
					if useprep:
						index = data.index(useprep[0])
					if useaction and (index is None or data.index(useaction[0]) < index):
						index = data.index(useaction[0])
					if index >= 0:
						self.property = ' '.join(data[0:index]).strip()
						del data[0:index]
					else:
						self.property = ' '.join(data).strip()
						del data[:]
					if not self.property.split('=')[0].strip() in self._properties:
						raise RuntimeError("Invalid property: " + self.property.split('=')[0].strip())
				self._parse(data)
			elif data[0].strip() in self._targetarticles:
				del data[0]
				self.target = '#' + filter(str.isdigit, data[0].strip())
				del data[0]
				self._parse(data)
			else:
				raise RuntimeError("Invalid command part: " + data[0].strip())

	# Method: getTextCommand
	def getStatement(self):
		outcmd = None
		if self.action is not None and self.subject is not None:
			outcmd = self.action + " " + self.subject
			if self.subject == self._subjects[2]:
				outcmd += " " + self.property
		if self.target is not None:
			outcmd += " on " + self.target
		return outcmd

	# Method: getTargetId
	def getTargetId(self):
		if self.target is not None:
			return int(filter(str.isdigit, self.target))
		else:
			return None

	# Method: hasLinkedData
	def hasLinkedData(self):
		return self._link != None

	# Method: getNextData
	def getLinkedData(self):
		return self._link

	# Method: getActions
	def getActions(self):
		return self._actions

	# Method: getSujects
	def getSujects(self):
		return self._subjects

	# Method: getProperties
	def getProperties(self):
		return self._properties

	# Method: getArticles
	def getArticles(self):
		return self._targetarticles


# Function: usage
def usage():
	print "\n" + __project__ + " " + __module__ + " " + __version__ + ", " + __license__ + ", " + __copyright__ + """
Usage: picam -c "start server" [-f ./picam.cfg] -i "0.0.0.0" -p 9079

Options:
 -v, --verbose    run in verbosity mode
 -i, --interface  host interface to start server component
 -h, --host       host name/ip of the server for client connectivity
 -p, --port       host port number for client connectivity
 -f, --file       file with command to start server instance or to run client commands
 --help           this help text

Examples:
> picam -c "start server"
> picam --command="start server"
  = run server (using default hostname and port) using input options
> picam start server
  = run server (using default hostname and port) aggregating command from all input parameters
> picam -c "start server" -i "0.0.0.0" -p 6400
> picam --command="start server" --interface="127.0.0.1" --port=6400
  = run server (using default hostname and port) using input options
> picam -c "start service on #1"
> picam --command="start service on c1"
  = run client to start on server camera #1. The client will connect to server using default port
> picam enable recording on c0
  = run client (using default hostname and port) aggregating command from all input parameters
> picam -c "set parameter resolution=1280,720 on c1" -h "192.168.0.100" -p 6400
> picam --command="set parameter resolution=1280,720 on c1" --host="127.0.0.1" --port=6400
  = run client that will send the command described by a specific option to a dedicated server
> picam "start server and start service on #0 and enable property streaming on #0 and enable property recording on #0"
  = this is a composed command (by 'and' operator) which can start the server, camera #0 and other. This kind of composed command could be run directly when you start the server or you can executed from client
> picam -f /opt/clue/etc/picam.cfg
  = run picam application using a configuration file (a file with commands), able to start the server or to run specific client actions
"""


# Function: str2bool
def str2bool(v):
	if v.lower() in ("on", "yes", "true", "t", "1"):
		return True
	elif v.lower() in ("off", "no", "false", "f", "0"):
		return False
	else:
		return None


# Function: cmdfile
def cmdfile(file, command=''):
	if file is not None and os.path.isfile(file):
		cfgfile = open(file, 'r')
		cfglines = cfgfile.readlines()
		cfgfile.close()
		for cmdline in cfglines:
			if cmdline.strip() != '' and not cmdline.strip().startswith('#'):
				if command is not None:
					command += ' and ' + cmdline.strip()
				else:
					command = cmdline.strip()
	return command


# Function: log
def tomsg(data, level=None):
	objlist = []
	message = ''
	# Define the list of objects and values
	if data is not None:
		if not isinstance(data, list):
			objlist.append(data)
		else:
			objlist = data
	# Build message
	for obj in objlist:
		if isinstance(obj, BaseException):
			# When verbose is activated print out the stacktrace
			if __verbose__:
				traceback.print_exc()
			# Take exception details to be described in log message
			part = str(obj)
			if part is None or part.strip() == '':
				part = type(obj).__name__
			message += ' ' + part
			level = "ERROR"
		else:
			message += ' ' + str(obj)
	if level is None or level == '': level = "INFO"
	# return turtle
	return level, message.strip()


# Main program
if __name__ == "__main__":
	# Global variables to identify input parameters
	command = None
	file = None
	host = None
	port = None
	# Parse input parameters
	opts, args = getopt.getopt(sys.argv[1:], "c:f:h:i:p:v", ["command=", "file=", "host=", "interface=", "port=", "verbose", "help"])
	# Collect input parameters
	for opt, arg in opts:
		if opt in ("-c", "--command"):
			command = arg
		elif opt in ("-f", "--file"):
			file = arg
		elif opt in ("-h", "--host", "-i", "--interface"):
			host = arg
		elif opt in ("-p", "--port"):
			port = arg
		elif opt in ("-v", "--verbose"):
			__verbose__ = True
		elif opt == '--help':
			usage()
			sys.exit(0)
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if (command is None or command == '') and file is None and host is None and port is None:
		command = ' '.join(sys.argv[1:])
		if command.strip() == 'help':
			usage()
			sys.exit(0)
	# Check if a configuration file has been specified read it ang get all commands defined in
	if file is not None and os.path.isfile(file):
		command = cmdfile(file, command)
	# Instantiate Client module an run the command
	client = PiCamClient(host, port)
	client.run(command)
	# Client normal exist
	sys.exit(0)
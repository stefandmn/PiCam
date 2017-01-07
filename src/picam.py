#!/usr/bin/python

import __init__

__project__   = __init__.__project__
__module__    = __init__.__module__
__email__     = __init__.__email__
__copyright__ = __init__.__copyright__
__license__   = __init__.__license__
__version__   = __init__.__version__
__verbose__   = False

import os
import io
import cv
import sys
import time
import json
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

	# Constants
	Sleeptime = 0.05
	StreamInterface = '0.0.0.0'
	StreamSleeptime = 0.05
	StreamStartPort = 9080

	# Constructor
	def __init__(self, id, motion=False, recording=False, streaming=False):
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
		self._sleeptime = Camera.Sleeptime
		self._resolution = None
		self._framerate = None
		# Initialize class private variables
		self._exec = False
		self._lock = True
		self._frame = None
		# Define tools
		self._camera = None
		self._motion = CamMotion(self)
		self._stream = CamStreaming(self)
		self._record = CamRecording(self)
		# Identify type of camera and initialize camera device
		self.setCameraOn()
		# Activate recording if was specified during initialization
		if motion:
			self._motion.start()
		if recording:
			self._record.start()
		if streaming:
			self._stream.start()
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

	# Method: stop
	def stop(self):
		self._exec = False
		# Stop motion detection
		if self.isMotionDetectionEnabled():
			self.setMotionDetection(False)
		# Stop motion detection
		if self.isRecordingEnabled():
			self.setRecording(False)
		# Stop streaming
		if self.isStreamingEnabled():
			self.setStreaming(False)
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
				# If motion detection feature is active run it to detect motion
				if self.isMotionDetectionEnabled():
					self._motion.run(self._frame)
				# If recording feature is active run it to record images or videos
				if self.isRecordingEnabled():
					self._record.run(self._frame)
				# If the streaming is active send the picture through the streaming channel
				if self.isStreamingEnabled():
					self._stream.run(self._frame)
				# Sleep for couple of seconds or milliseconds
				if self._sleeptime > 0:
					time.sleep(self._sleeptime)
			except BaseException as baserr:
				self.log(["Camera workflow failed:", baserr])
				self.stop()

	# Method: isCameraOn
	def isCameraOn(self):
		return self._camera is not None

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

	# Method: isCameraOff
	def isCameraOff(self):
		return self._camera is None

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
				if resolution.find(",") > 0:
					self._resolution = (int(resolution.split(',')[0].strip()), int(resolution.split(',')[1].strip()))
				elif resolution.lower().find("x") > 0:
					self._resolution = (int(resolution.lower().split('x')[0].strip()), int(resolution.lower().split('x')[1].strip()))
				else:
					raise RuntimeError("Undefined camera resolution value: " + str(resolution))
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.resolution = self._resolution
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
				self._lock = False
			except BaseException as baseerr:
				self.log(["Applying camera resolution failed:", baseerr])

	# Method: getCameraResolution
	def getCameraResolution(self):
		return self._resolution

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

	# Method: getCameraFramerate
	def getCameraFramerate(self):
		return self._framerate

	# Method: setCameraSleeptime
	def setCameraSleeptime(self, sleeptime):
		self._sleeptime = sleeptime

	# Method: getCameraSleeptime
	def getCameraSleeptime(self):
		return self._sleeptime

	# Method: isMotionActive
	def isMotionDetectionEnabled(self):
		return self._motion.isRunning()

	# Method: setMotionDetection
	def setMotionDetection(self, flag):
		if not self.isMotionDetectionEnabled() and flag:
			self._motion.start()
		elif self.isMotionDetectionEnabled() and not flag:
			self._motion.stop()
		elif self.isMotionDetectionEnabled() and flag:
			self.log("Motion Detection function is already activated")
		elif not self.isMotionDetectionEnabled() and not flag:
			self.log("Motion Detection function is not activated")

	# Method: setMotionDetectionThreshold
	def setMotionDetectionThreshold(self, threshold):
		self._motion.setThreshold(threshold)

	# Method: getMotionDetectionThreshold
	def getMotionDetectionThreshold(self):
		return self._motion.getThreshold()

	# Method: setMotionDetectionContour
	def setMotionDetectionContour(self, contour):
		self._motion.setContour(contour)

	# Method: getMotionDetectionContour
	def getMotionDetectionContour(self):
		return self._motion.isContour()

	# Method: isRecordingEnabled
	def isRecordingEnabled(self):
		return self._record.isRunning()

	# Method: setCameraRecording
	def setRecording(self, flag):
		if not self.isRecordingEnabled() and flag:
			self._record.start()
		elif self.isRecordingEnabled() and not flag:
			self._record.stop()
		elif self.isRecordingEnabled() and flag:
			self.log("Recording function is already activated")
		elif not self.isRecordingEnabled() and not flag:
			self.log("Recording function is not activated")

	# Method: setRecordingLocation
	def setRecordingLocation(self, location):
		if self.isRecordingEnabled():
			self._record.stop()
			self.setRecordingReset()
			self._record.setLocation(location)
			self._record.start()
		else:
			self.setRecordingReset()
			self._record.setLocation(location)

	# Method: getRecordingLocation
	def getRecordingLocation(self):
		return self._record.getLocation()

	# Method: setRecordingFormat
	def setRecordingFormat(self, format):
		if self.isRecordingEnabled():
			self._record.stop()
			self.setRecordingReset()
			self._record.setFormat(format)
			self._record.start()
		else:
			self.setRecordingReset()
			self._record.setFormat(format)

	# Method: getRecordingFormat
	def getRecordingFormat(self):
		return self._record.getFormat()

	# Method: setRecordingMessage
	def setRecordingMessage(self, text):
		self._record.setMessage(text)

	# Method: setRecordingSkip
	def setRecordingSkipped(self, skip):
		self._record.setSkip(skip)

	# Method: isRecordingSkipped
	def isRecordingSkipped(self):
		return self._record.isSkipped()

	# Method: setRecordingReset
	def setRecordingReset(self):
		self._record.reset()

	# Method: isStreamingEnabled
	def isStreamingEnabled(self):
		return self._stream.isRunning()

	# Method: setStreamingOn
	def setStreaming(self, flag):
		if not self.isStreamingEnabled() and flag:
			self._stream.start()
		elif self.isStreamingEnabled() and not flag:
			self._stream.stop()
		elif self.isStreamingEnabled() and flag:
			self.log("Streaming function is already activated")
		elif not self.isStreamingEnabled() and not flag:
			self.log("Streaming function is not activated")

	# Method: setStreamingPort
	def setStreamingPort(self, port):
		if self.isStreamingEnabled():
			self._stream.stop()
			self._stream.setStreamingPort(port)
			self._stream.start()
		else:
			self._stream.setStreamingPort(port)

	# Method: getStreamingPort
	def getStreamingPort(self):
		return self._stream.getStreamingPort()

	# Method: setStreamingSleep
	def setStreamingSleep(self, sleep):
		self._stream.setStreamingSleep(sleep)

	# Method: getStreamingSleep
	def getStreamingSleep(self):
		return self._stream.getStreamingSleep()


# Class: CamFunction
class CamFunction:

	# Constructor
	def __init__(self, camera, start=False):
		self._running = False
		# Validate camera object
		if camera is None:
			raise RuntimeError("Invalid or camera object for " + self.__class__.__name__ + " function")
		else:
			self._camera = camera
		# Start function, if is asked for
		if self._camera.isCameraOn and start:
			self.start()

	# Method: start
	def start(self):
		if self._camera.isCameraOn:
			self._running = True
		else:
			self._running = False

	# Method: stop
	def stop(self):
		self._running = False

	# Method: isRunning
	def isRunning(self):
		if self._camera.isCameraOn:
			return self._running
		else:
			return False

	# Method: run
	def run(self, frame):
		return

	# Method: log
	def log(self, data):
		type, message = tomsg(data)
		if message != '':
			print "%s | %s %s > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, "Service", message)


# Class: CamMotion
class CamMotion(CamFunction):
	# Constructor
	def __init__(self, camera, start=False):
		CamFunction.__init__(self, camera, start=start)
		# Motion detection properties
		self._contour = True
		self._threshold = 1500
		# Initialize engine parameters
		self.__gray = None
		self.__size = (320,240)
		self.__ismot = False
		self.__fkmot = 0

	# Method: isContour
	def isContour(self):
		return self._contour

	# Method: setRecording
	def setContour(self, contour):
		self._contour = contour

	# Method: getThreshold
	def getThreshold(self):
		return self._threshold

	# Method: setThreshold
	def setThreshold(self, threshold):
		self._threshold = threshold

	# Method: _gray
	def _gray(self, frame):
		copy = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_8U, 1)
		cv.CvtColor(frame, copy, cv.CV_RGB2GRAY)
		resize = cv.CreateImage(self.__size, cv.IPL_DEPTH_8U, 1)
		cv.Resize(copy, resize)
		return resize

	# Method: _absdiff
	def _absdiff(self, frame1, frame2):
		output = cv.CloneImage(frame1)
		cv.AbsDiff(frame1, frame2, output)
		return output

	# Method: _compute
	def _compute(self, frame):
		cv.Threshold(frame, frame, 35, 255, cv.CV_THRESH_BINARY)
		cv.Dilate(frame, frame, None, 18)
		cv.Erode(frame, frame, None, 10)
		return frame

	# Method: _area
	def _area(self, move, frame):
		points = []
		area = 0
		xsize = cv.GetSize(frame)[0] / self.__size[0]
		ysize = cv.GetSize(frame)[1] / self.__size[1]
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
			if self.isContour() and area > self.getThreshold():
				points.append(pt1)
				points.append(pt2)
				cv.Rectangle(frame, pt1, pt2, cv.CV_RGB(255,0,0), 1)
		return area

	# Method: run
	def run(self, frame):
		if frame is not None:
			# Check if is needed to initialize the engine
			if self.__gray is None:
				if self._camera.isRecordingEnabled() and self._camera.getRecordingFormat() == 'image':
					self._camera.setRecordingMessage("Start Monitoring")
				self.__gray = self._gray(frame)
			else:
				_gray = self._gray(frame)
				_diff = self._absdiff(self.__gray, _gray)
				_move = self._compute(_diff)
				_area = self._area(_move, frame)
				# Evaluation
				if self._camera.isRecordingEnabled():
					if _area > self.getThreshold():
						self.__ismot = True
						self.__fkmot = 0
						if self._camera.isRecordingSkipped():
							self._camera.setRecordingReset()
						self._camera.setRecordingMessage("Motion Detection")
					elif self.__ismot:
						self.__fkmot += 1
						if self.__fkmot > 59:
							if not self._camera.isRecordingSkipped():
								self._camera.setRecordingSkipped(True)
							self.__ismot = False
							self.__fkmot = 0
				self.__gray = _gray


# Class: CamRecording
class CamRecording(CamFunction):
	# Constructor
	def __init__(self, camera, start=False):
		CamFunction.__init__(self, camera, start=start)
		self._format = 'image'
		self._location = '/tmp'
		self.__skip = False
		self.__text = None
		self.__vref = None

	# Method: getFormat
	def getFormat(self):
		return self._format

	# Method: setFormat
	def setFormat(self, format):
		if format is not None:
			if format.lower() in ("image", "picture", "photo", "pic", "i", "p"):
				self._format = 'image'
			elif format.lower() in ("video", "movie", "v", "m"):
				self._format = 'video'

	# Method: getLocation
	def getLocation(self):
		return self._location

	# Method: setLocation
	def setLocation(self, location):
		self._location = location

	# Method: setMessage
	def setMessage(self, text):
		self._text = text

	# Method: setSkip
	def setSkip(self, skip):
		self._skip = skip

	# Method: isSkipped
	def isSkipped(self):
		return self._skip

	# Method: run
	def run(self, frame):
		if not self.__skip and self._running:
			try:
				clone = cv.CloneImage(frame)
				message = self.__text + " @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
				cv.PutText(clone, message, (10, cv.GetSize(clone)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .32, .32, 0.0, 1, cv.CV_AA), (255, 255, 255))
				if self._format == 'image':
					filename = self._location + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0')
					filename += "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
					filename += ".png"
					cv.SaveImage(filename, clone)
				elif self._format == 'video':
					if self._vref is not None:
						cv.WriteFrame(self._vref, clone)
					else:
						filename = self._location + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0')
						filename += "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".avi"
						self._vref = cv.CreateVideoWriter(filename, cv.CV_FOURCC('M', 'J', 'P', 'G'), 2, cv.GetSize(frame), True)
			except IOError as ioerr:
				self.log(["Recording function failed:", ioerr])
				self.stop()

	# Method: reset
	def reset(self):
		self.__vref = None
		self.__text = None
		self.__skip = False


# Class: CamStreaming
class CamStreaming(CamFunction):
	# Constructor
	def __init__(self, camera, start=False):
		CamFunction.__init__(self, camera, start=start)
		self._stream = None
		self._sleep = Camera.StreamSleeptime
		self._iface = Camera.StreamInterface
		self._port = Camera.StreamStartPort

	# Method: start
	def start(self):
		if self._camera.isCameraOn:
			try:
				self._stream = StreamingServer((self._iface, self._port), StreamHandler, frame=None, sleep=self._sleep)
				streamthread = threading.Thread(target=self._stream.serve_forever)
				streamthread.daemon = True
				streamthread.start()
				self._running = True
				self.log("Streaming started on " + str(self._stream.server_address))
			except IOError as ioerr:
				self.log(["Streaming initialization failed:", ioerr])
				self._stream = None
				self._running = False

	# Method: stop
	def stop(self):
		if self._stream is not None:
			try:
				self._stream.shutdown()
				self._stream.server_close()
				self._stream = None
			except IOError as ioerr:
				self.log(["Streaming function has been stopped with errors:", ioerr])
				self._stream = None
		self._running = False

	# Method: getStreamingPort
	def getStreamingPort(self):
		return self._port

	# Method: setStreamingPort
	def setStreamingPort(self, port):
		self._port = port

	# Method: StreamingSleep
	def getStreamingSleep(self):
		return self._sleep

	# Method: setStreamingSleep
	def setStreamingSleep(self, sleeptime):
		self._sleep = sleeptime
		if self._stream is not None:
			self._stream.setSleep(sleeptime)

	# Method: run
	def run(self, frame):
		if self._stream is not None and self._running:
			try:
				self._stream.setFrame(frame)
			except IOError as ioerr:
				self.log(["Sending streaming data failed:", ioerr])


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


# Class: StreamingServer
class StreamingServer(ThreadingMixIn, HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleep=0.01):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleep = sleep

	# Method: getFrame
	def getFrame(self):
		return self._frame

	# Method: getFrame
	def setFrame(self, frame):
		self._frame = frame

	# Method: getSleep
	def getSleep(self):
		return self._sleep

	# Method: setSleep
	def setSleep(self, sleep):
		self._sleep	= sleep


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
			self.log("Receiving client request: " + str(command))
			# Instantiate client structure to run the action and subject
			data = StateData(command)
			# Evaluate server actions
			if data is not None and data.subject == StateData.Subjects[0]:
				if data.action == StateData.Actions[8]:
					answer = self.server.runServerEcho()
				elif data.action == StateData.Actions[7]:
					answer = self.server.runServerStatus()
				elif data.action == StateData.Actions[9]:
					answer = self.server.runServerLoad(data.target)
				elif data.action == StateData.Actions[10]:
					answer = self.server.runServerSave(data.target)
				elif data.action == StateData.Actions[1]:
					answer = None
					if self.server.getCameras():
						keys = self.server.getCameras().keys()
						for key in keys:
							subanswer = self.server.runServiceStop(key)
							if answer is None:
								jsonanswer = json.loads(subanswer)
								jsonanswer["action"] = StateData.Actions[1]
								jsonanswer["subject"] = StateData.Subjects[0]
							else:
								jsonmsg = json.loads(subanswer)
								jsonanswer["achieved"] = jsonanswer["achieved"] & jsonmsg["achieved"]
								jsonanswer["message"] += ". " + jsonmsg["message"]
							time.sleep(1)
						answer = '{"action":"' + StateData.Actions[1] + '", "subject":"' + StateData.Subjects[0] + '", "achieved":' + str(jsonanswer["achieved"]).lower() + ', "message":"' + jsonanswer["message"] + '"}'
					else:
						answer = '{"action":"' + StateData.Actions[1] + '", "subject":"' + StateData.Subjects[0]+ '", "achieved":true, "message":"No camera is running"}'
				else:
					raise RuntimeError("Invalid server action: " + any2str(data.action))
			# Evaluate service actions
			elif data is not None and data.subject == StateData.Subjects[1]:
				if data.action == StateData.Actions[2]:
					answer = self.server.runServiceStart(data.target)
				elif data.action == StateData.Actions[3] and data.subject == StateData.Subjects[1]:
					answer = self.server.runServiceStop(data.target)
				else:
					raise RuntimeError("Invalid service action: " + any2str(data.action))
			# Evaluate property actions
			elif data is not None and data.subject == StateData.Subjects[2]:
				if data.action == StateData.Actions[5]:
					camprop = data.property.strip()
					camdata = "True"
				elif data.action == StateData.Actions[6]:
					camprop = data.property.strip()
					camdata = "False"
				elif data.action == StateData.Actions[4]:
					camprop = data.property.split('=')[0].strip()
					camdata = data.property.split('=')[1].strip()
				else:
					raise RuntimeError("Invalid property action: " + any2str(data.action))
				answer = self.server.runPropertySet(data.target, camprop, camdata)
			else:
				answer = '{"action":"unknown", "subject":"unknown", "achieved":false, "message":"Command ' + str(data) + ' is not implemented or is unknown"}'
		except BaseException as stderr:
			data = None
			answer = '{"action":"unknown", "subject":"unknown", "achieved":false, "message":"' + tomsg(["Error processing client request:", stderr])[1] + '"}'
		# Send server answer to the client (in JSON format)
		try:
			# If the command is shutdown stop all server threads and deallocate server object
			if data is not None and data.action == StateData.Actions[1] and data.subject == StateData.Subjects[0]:
				self.server.shutdown()
				self.server = None
			else:
				# Sending answer to client
				self.request.sendall(answer)
		except BaseException as stderr:
			self.log(["Handling server command failed:", stderr])

	# Method: log
	def log(self, data):
		type, message = tomsg(data)
		# Send message to the standard output or to the client console
		if message != '':
			print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)


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

	# Method _answer
	def _answer(self, action, subject, achieved, message=None, result=None):
		data = '{"action":"' + action + '", "subject":"' + subject + '", "achieved":' + str(achieved).lower()
		if message is not None and message != '':
			data += ', "message":"' + message + '"'
		if result is not None and result != '':
			if isinstance(result, str):
				data += ', "result":' + result + '}'
			else:
				data += ', "result":' + json.dumps(result) + '}'
		else:
			data += '}'
		return data

	# Method: streamline
	@staticmethod
	def streamline(service):
		if service is not None and isinstance(service, dict):
			try:
				# CameraSleeptime
				if service.get(StateData.Properties[6]) and any2float(service[StateData.Properties[6]]) == Camera.Sleeptime:
					service[StateData.Properties[6]] = "default"
				# StreamingSleeptime
				if service.get(StateData.Properties[13]) and any2float(service[StateData.Properties[13]]) == Camera.StreamSleeptime:
					service[StateData.Properties[13]] = "default"
				# StreamingPort
				if service.get(StateData.Properties[12]) and any2int(service[StateData.Properties[12]]) == Camera.StreamStartPort + int(filter(str.isdigit, str(service[StateData.Properties[0]]).strip())):
					service[StateData.Properties[12]] = "default"
				# Drop all default values from the service configuration
				for key in service.keys():
					if service[key] == "default":
						del service[key]
				return True
			except:
				return False
		else:
			return False

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
		self.server_close()

	# Method: runActionEcho
	def runServerEcho(self):
		result = '"{"project":"' + __project__ + '", "module":"' + __module__ + '", "version":"' + __version__ + '", "license":"' + __license__ + '", "copyright":"' + __copyright__ + '"}'
		# Aggregate JSON output
		return self._answer(StateData.Actions[8], StateData.Subjects[0], True, None, result)

	# Method: runActionStatus
	def runServerStatus(self):
		result = '{"project":"' + __project__ + '", "module":"' + __module__ + '", "version":"' + __version__ + '"'
		result += ', "host":"' + str(self.server_address[0]) + '", "port": ' + str(self.server_address[1]) + ', "services":'
		if self.getCameras():
			result += '['
			index = 0
			keys = self.getCameras().keys()
			for key in keys:
				camera = self.getCameras()[key]
				if index == 0:
					result += '{'
				else:
					result += ', {'
				result += '"' + StateData.Properties[0] + '":' + any2str(camera.getId())
				# CameraStatus
				result += ', "' + StateData.Properties[1] + '":"On"'
				# CameraResolution
				result += ', "' + StateData.Properties[4] + '":"' + ('default' if camera.getCameraResolution() is None else str(camera.getCameraResolution()[0]) + 'x' + str(camera.getCameraResolution()[1])) + '"'
				# CameraFramerate
				result += ', "' + StateData.Properties[5] + '":' + ('"default"' if camera.getCameraFramerate() is None else any2str(camera.getCameraFramerate()))
				# CameraFramerate
				result += ', "' + StateData.Properties[6] + '":' + ('"default"' if camera.getCameraFramerate() is None else any2str(camera.getCameraSleeptime()))
				# CameraMotionDetection
				result += ', "' + StateData.Properties[3] + '":"' + ('On' if camera.isMotionDetectionEnabled() else 'Off') + '"'
				if camera.isMotionDetectionEnabled():
					result += ', "' + StateData.Properties[7] + '":"' + ('On' if camera.getMotionDetectionContour() else 'Off') + '"'
					result += ', "' + StateData.Properties[10] + '":' + any2str(camera.getMotionDetectionThreshold())
				# CameraRecording
				result += ', "' + StateData.Properties[8] + '":"' + ('On' if camera.isRecordingEnabled() else 'Off') + '"'
				if camera.isRecordingEnabled():
					result += ', "' + StateData.Properties[9] + '":"' + any2str(camera.getRecordingFormat()) + '"'
					result += ', "' + StateData.Properties[11] + '":"' + any2str(camera.getRecordingLocation()) + '"'
				# CameraStreaming
				result += ', "' + StateData.Properties[2] + '":"' + ('On' if camera.isStreamingEnabled() else 'Off') + '"'
				if camera.isStreamingEnabled():
					result += ', "' + StateData.Properties[12] + '":' + any2str(camera.getStreamingPort())
					result += ', "' + StateData.Properties[13] + '":' + any2str(camera.getStreamingSleep())
				result += '}'
				index += 1
			result += ']'
		else:
			result += '[]'
		result += '}'
		# Aggregate JSON output
		return self._answer(StateData.Actions[7], StateData.Subjects[0], True, None, result)

	# Method: runServiceStart
	def runServiceStart(self, id):
		achieved = True
		result = None
		msg = None
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			if key in self.getCameras():
				msg = "Camera " + key + " is already started"
			else:
				try:
					camera = Camera(key)
					camera.setStreamingPort(self.server_address[1] + 1 + camera.getId())
					camera.start()
					self.getCameras()[key] = camera
					msg = "Camera " + key + " has been started"
				except BaseException as stderr:
					achieved = False
					msg = tomsg(["Error starting camera " + key + ":", stderr])[1]
		else:
			key = None
			msg = "Camera identifier was not specified"
		# Define result key
		if achieved and key is not None:
			result = '{"service":"' + key + '"}'
		# Aggregate JSON output
		return self._answer(StateData.Actions[2], StateData.Subjects[1], achieved, msg, result)

	# Method: runServiceStop
	def runServiceStop(self, id):
		achieved = True
		result = None
		msg = None
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			if key in self.getCameras():
				try:
					camera = self.getCameras()[key]
					camera.stop()
					del self.getCameras()[key]
					msg = "Camera " + key + " has been stopped"
				except BaseException as stderr:
					achieved = False
					msg = tomsg(["Error stopping camera " + key + ":", stderr])[1]
			else:
				msg = "Camera " + key + " was not yet started"
		else:
			key = None
			msg = "Camera could not be identified to stop service"
		# Define result key
		if achieved and key is not None:
			result = '{"service":"' + key + '"}'
		# Aggregate JSON output
		return self._answer(StateData.Actions[3], StateData.Subjects[1], achieved, msg, result)

	# Method: runPropertySet
	def runPropertySet(self, id, camprop, camdata):
		achieved = True
		result = None
		msg = None
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			# Ge target camera
			if key in self.getCameras():
				try:
					# Identity target camera
					camera = self.getCameras()[key]
					# Evaluate CameraStreaming property
					if camprop.lower() == StateData.Properties[2].lower():
						camera.setStreaming(any2bool(camdata))
					# Evaluate CameraMotionDetection property
					elif camprop.lower() == StateData.Properties[3].lower():
						camera.setMotionDetection(any2bool(camdata))
					# Evaluate CameraResolution property
					elif camprop.lower() == StateData.Properties[4].lower():
						camera.setCameraResolution(any2str(camdata))
					# Evaluate CameraFramerate property
					elif camprop.lower() == StateData.Properties[5].lower():
						camera.setCameraFramerate(any2int(camdata))
					# Evaluate CameraSleeptime property
					elif camprop.lower() == StateData.Properties[6].lower():
						camera.setCameraSleeptime(any2float(camdata))
					# Evaluate MotionDetectionContour property
					elif camprop.lower() == StateData.Properties[7].lower():
						camera.setMotionDetectionContour(any2bool(camdata))
					# Evaluate MotionDetectionThreshold property
					elif camprop.lower() == StateData.Properties[10].lower():
						camera.setMotionDetectionThreshold(any2int(camdata))
					# Evaluate CameraRecording property
					elif camprop.lower() == StateData.Properties[8].lower():
						camera.setRecording(any2bool(camdata))
					# Evaluate RecordingFormat property
					elif camprop.lower() == StateData.Properties[9].lower():
						camera.setRecordingFormat(any2str(camdata))
					# Evaluate RecordingLocation property
					elif camprop.lower() == StateData.Properties[11].lower():
						camera.setRecordingLocation(any2str(camdata))
					# Evaluate StreamingPort property
					elif camprop.lower() == StateData.Properties[12].lower():
						camera.setStreamingPort(any2int(camdata))
					# Evaluate StreamingSleeptime property
					elif camprop.lower() == StateData.Properties[13].lower():
						camera.setStreamingSleep(any2float(camdata))
					else:
						achieved = False
						msg = 'Unknown property: ' + camprop
					if achieved:
						msg = "Camera " + key + " has been updated based on property '" + camprop + "' = '" + str(camdata) + "'"
				except BaseException as stderr:
					achieved = False
					msg = tomsg(["Error setting property '" + camprop + "' = '" + str(camdata) + "' on camera " + key + ":", stderr])[1]
			else:
				achieved = False
				msg = "Camera " + key + " is not yet started"
		else:
			key = None
			msg = "Camera could not be identified to set property"
		# Define result key
		if achieved and key is not None:
			result='{"service":"' + key + '", "property":"' + camprop + '", "value":"' + str(camdata) + '"}'
		# Aggregate JSON output
		return self._answer(StateData.Actions[4], StateData.Subjects[2], achieved, msg, result)

	# Method: runServerLoad
	def runServerLoad(self, path=None):
		achieved = True
		result = None
		msg = None
		# Set default configuration (if is bit specified)
		if path is None:
			path = "/opt/clue/etc/picam.cfg"
		# Load and handle configuration
		if os.path.isfile(path):
			try:
				# Read the file content
				file = open(path, 'r')
				cfg = json.load(file)
				file.close()
				msg = "Loading configuration from target location: " + str(path)
				result = json.loads('{"file":"' + path + '", "start-services":[], "stop-services":[], "set-properties":[]}')
				if cfg.get("services"):
					# Load services from configuration
					for service in cfg['services']:
						# Streamline service configuration removing default values
						PiCamServer.streamline(service)
						# Validate camera id and status
						if service.get(StateData.Properties[0]) is None:
							continue
						# Get camera identifier
						CameraId = int(filter(str.isdigit, str(service[StateData.Properties[0]])))
						CameraStarted = False
						# CameraStatus
						if service.get(StateData.Properties[1]) and any2bool(service[StateData.Properties[1]]):
							jsonout = json.loads(self.runServiceStart(CameraId))
							CameraStarted = jsonout["achieved"]
							if jsonout["achieved"]:
								result["start-services"].append(jsonout["result"]["service"])
							else:
								msg += ('. ' + str(jsonout["message"]))
								continue
						elif service.get(StateData.Properties[1]) and not any2bool(service[StateData.Properties[1]]):
							jsonout = json.loads(self.runServiceStop(CameraId))
							if jsonout["achieved"]:
								result["stop-services"].append(jsonout["result"]["service"])
							else:
								msg += ('. ' + str(jsonout["message"]))
							continue
						# CameraResolution
						if service.get("CameraResolution"):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraResolution", service["CameraResolution"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# CameraFramerate
						if service.get("CameraFramerate"):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraFramerate", service["CameraFramerate"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# CameraSleeptime
						if service.get("CameraSleeptime"):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraSleeptime", service["CameraSleeptime"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# MotionDetectionContour
						if service.get("MotionDetectionContour"):
							jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionContour", service["MotionDetectionContour"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# MotionDetectionThreshold
						if service.get("MotionDetectionThreshold"):
							jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionThreshold", service["MotionDetectionThreshold"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# RecordingFormat
						if service.get("RecordingFormat"):
							jsonout = json.loads(self.runPropertySet(CameraId, "RecordingFormat", service["RecordingFormat"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# RecordingLocation
						if service.get("RecordingLocation"):
							jsonout = json.loads(self.runPropertySet(CameraId, "RecordingLocation", service["RecordingLocation"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# StreamingPort
						if service.get("StreamingPort"):
							jsonout = json.loads(self.runPropertySet(CameraId, "StreamingPort", service["StreamingPort"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# StreamingSleeptime
						if service.get("StreamingSleeptime"):
							jsonout = json.loads(self.runPropertySet(CameraId, "StreamingSleeptime", service["StreamingSleeptime"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						# Function: CameraMotionDetection
						if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraMotionDetection", service["CameraMotionDetection"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
							if not CameraStarted:
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraMotionDetection", service["CameraMotionDetection"]))
								if jsonout["achieved"]:
									if result["set-properties"].count(jsonout["result"]["property"]) == 0:
										result["set-properties"].append(jsonout["result"]["property"])
								else:
									msg += ('. ' + str(jsonout["message"]))
						# Function: CameraRecording
						if service.get("CameraRecording") and any2bool(service["CameraRecording"]):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraRecording", service["CameraRecording"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						elif service.get("CameraRecording") and not any2bool(service["CameraRecording"]):
							if not CameraStarted:
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraRecording", service["CameraRecording"]))
								if jsonout["achieved"]:
									if result["set-properties"].count(jsonout["result"]["property"]) == 0:
										result["set-properties"].append(jsonout["result"]["property"])
								else:
									msg += ('. ' + str(jsonout["message"]))
						# Function: CameraStreaming
						if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraStreaming", service["CameraStreaming"]))
							if jsonout["achieved"]:
								if result["set-properties"].count(jsonout["result"]["property"]) == 0:
									result["set-properties"].append(jsonout["result"]["property"])
							else:
								msg += ('. ' + str(jsonout["message"]))
						elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
							if not CameraStarted:
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraStreaming", service["CameraStreaming"]))
								if jsonout["achieved"]:
									if result["set-properties"].count(jsonout["result"]["property"]) == 0:
										result["set-properties"].append(jsonout["result"]["property"])
								else:
									msg += ('. ' + str(jsonout["message"]))
			except BaseException as stderr:
				result = None
				achieved = False
				msg = tomsg(["Error loading server configuration from file " + path + ": ", stderr])[1]
		else:
			achieved = False
			msg = "Invalid target location: " + str(path)
		# Aggregate JSON output
		return self._answer(StateData.Actions[9], StateData.Subjects[0], achieved, msg, result)

	# Method: runServerLoad
	def runServerSave(self, path=None):
		achieved = True
		result = None
		try:
			# Set default configuration
			if path is None:
				path = "/opt/clue/etc/picam.cfg"
			# Get server status
			status = json.loads(self.runServerStatus())
			# Read the file configuration (if exists)
			if path is not None and  os.path.isfile(path):
				file = open(path, 'r')
				cfg = json.load(file)
				file.close()
				if cfg.get("services"):
					del cfg["services"]
				cfg["services"] = status["result"]["services"]
			else:
				cfg = json.loads('{"host":"' + status["result"]["host"] + '", "port":' + str(status["result"]["port"]) + '}')
				cfg["services"] = status["result"]["services"]
			# Write consolidated configuration in file
			file = open(path, 'w')
			file.write(json.dumps(cfg, indent=4, sort_keys=True))
			file.close()
			msg = "Configuration saved in target location: " + str(path)
			result = json.loads('{"file":"' + path + '", "start-services":[], "set-properties":[]}')
			for service in cfg["services"]:
				for key in service.keys():
					if key is not None and key == StateData.Properties[0]:
						result["start-services"].append('#' + filter(str.isdigit, str(service[StateData.Properties[0]]).strip()))
					elif key is not None and key != StateData.Properties[1]:
						if result["set-properties"].count(service[key]) == 0:
							result["set-properties"].append(service[key])
		except BaseException as stderr:
			achieved = False
			msg = tomsg(["Error saving server configuration in file " + path + ": ", stderr])[1]
		# Aggregate JSON output
		return self._answer(StateData.Actions[10], StateData.Subjects[0], achieved, msg, result)


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
		self._api = api
		self._apiData = []

	# Method: connect
	def run(self, command):
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
				self._apiData.append('{"action":"unknown", "subject": "unknown", "achieved":false, "message":' + tomsg(errordata)[1])
				return self._apiData
		# Check if input command ask to start server instance
		if data.action == StateData.Actions[0] and data.subject == StateData.Subjects[0]:
			try:
				server = PiCamServer((self._host, self._port), PiCamServerHandler)
				serverhread = threading.Thread(target=server.serve_forever)
				serverhread.daemon = True
				serverhread.start()
				# Write output to std output or write it through API chain
				infodata = __project__ + " " + __module__ + " Server has been initialized"
				if not self._api:
					self.log(infodata)
				else:
					self._apiData.append('{"action":"' + StateData.Actions[0] + '", "subject":"' + StateData.Subjects[0] + '", "achieved":true, "message":' + tomsg(infodata)[1])
				# Check if the current command is linked by other to execute the whole chain
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
			except BaseException as baserr:
				errordata = ["PiCam server failed:", baserr]
				self.log(errordata)
				server = None
				data = None
		# Check if input comment ask to execute a server command
		while data is not None:
			try:
				# Send command to server instance
				self.log(__project__ + " " + __module__ + " Client is calling " + self._host + ":" + str(self._port))
				client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				client.connect((self._host, self._port))
				# Generate command received from standard input
				command = data.getStatement()
				self.log("Sending command: " + command)
				client.sendall(command)
				# Getting the answers from server
				while True:
					answer = client.recv(1024)
					if answer is not None and answer != '':
						if not self._api:
							# Get JSON structure
							jsonanswer = json.loads(answer)
							# Read message type and value to be displayed to STD output
							if jsonanswer is not None:
								if jsonanswer.get("message") is not None:
									message = jsonanswer["message"]
								else:
									message = None
								if jsonanswer["achieved"]:
									level = "INFO"
								else:
									level = "ERROR"
							else:
								message = "Server message could not be translated: " + str(answer)
								level = "ERROR"
							# Display message to standard output
							if jsonanswer["action"] == StateData.Actions[8] and jsonanswer["subject"] == StateData.Subjects[0]:
								self.log(self._echo(jsonanswer), type="INFO", server=True)
							elif jsonanswer["action"] == StateData.Actions[7] and jsonanswer["subject"] == StateData.Subjects[0]:
								self.log(self._status(jsonanswer), type="INFO", server=True)
							elif message is not None:
								self.log(message, type=level, server=True)
						else:
							self._apiData.append(answer)
					else:
						break
				client.close()
			except BaseException as baserr:
				errordata = ["Command failed:", baserr]
				if not self._api:
					self.log(errordata)
				else:
					self._apiData.append('{"action":"' + data.action + '", "subject":"' + data.subject + '", "achieved":false, "message":' + tomsg(errordata)[1])
			finally:
				# Check if the current command is linked by other command
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
		# If server has been instantiated in this process wait to finish his execution
		if server is not None and not self._api:
			while server.isRunning():
				try:
					time.sleep(1)
				except KeyboardInterrupt:
					print
					self.log('Interrupting server execution by user control', type="INFO", server=True)
					# Unlock server socket
					try:
						_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						_socket.connect(("localhost", self._port))
						_socket.sendall("shutdown server")
						_socket.close()
					except:
						# Nothing to do here
						self.log("Failed running silent shutdown", type="ERROR", server=True)
		# End program execution
		if not self._api:
			print ""
		else:
			if len(self._apiData) == 1:
				return self._apiData[0]
			else:
				return self._apiData

	# Method: log
	def log(self, data, type=None, server=False):
		type, message = tomsg(data, type)
		# Evaluate message and type
		if message != '' and not self._api:
			if not server:
				print "%s | %s Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)
			else:
				print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)

	# Method: echo
	def _echo(self, answer):
		if answer is not None and answer["result"] is not None:
			return answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"] + ", " + answer["result"]["copyright"]
		else:
			return ""

	# Method: status
	def _status(self, answer):
		if answer is not None and answer["result"] is not None:
			text = "Status of " + answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"]
			text += '\n\t> server: ' + answer["result"]["host"] + ":" + any2str(answer["result"]["port"])
			for service in answer["result"]["services"]:
				text += '\n\t> service: #' + any2str(service[StateData.Properties[0]])
				# Main Properties
				text += '\n\t\t| CameraResolution: ' + ('default' if service["CameraResolution"] is None else any2str(service["CameraResolution"]))
				text += '\n\t\t| CameraFramerate: ' + ('default' if service["CameraFramerate"] is None else any2str(service["CameraFramerate"]))
				text += '\n\t\t| CameraSleeptime: ' + ('default' if service["CameraSleeptime"] is None else any2str(service["CameraSleeptime"]))
				# Streaming
				if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
					text += '\n\t\t| CameraStreaming: On'
					text += '\n\t\t\t|| StreamingPort: ' + any2str(service["StreamingPort"])
					text += '\n\t\t\t|| StreamingSleeptime: ' + any2str(service["StreamingSleeptime"])
				elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
					text += '\n\t\t| CameraStreaming: Off'
				# Motion Detection
				if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
					text += '\n\t\t| CameraMotionDetection: On'
					text += '\n\t\t\t|| MotionDetectionContour: ' + ('On' if service["MotionDetectionContour"] else 'Off')
					text += '\n\t\t\t|| MotionDetectionThreshold: ' + any2str(service["MotionDetectionThreshold"])
				elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
					text += '\n\t\t| CameraMotionDetection: Off'
				# Recording
				if service.get("CameraRecording") and any2bool(service["CameraRecording"]):
					text += '\n\t\t| CameraRecording: On'
					text += '\n\t\t\t|| RecordingFormat: ' + any2str(service["RecordingFormat"])
					text += '\n\t\t\t|| RecordingLocation: ' + any2str(service["RecordingLocation"])
				elif service.get("CameraRecording") and not any2bool(service["CameraRecording"]):
					text += '\n\t\t| CameraRecording: Off'
			return text
		else:
			return ""

	# Method: command
	def load(self, filename, command=''):
		if filename is not None and os.path.isfile(filename):
			try:
				# Read the file content
				file = open(filename, 'r')
				content = file.readlines()
				file.close()
				# Check if content if JSON, otherwise  parse and run it
				if '\n'.join(content).strip().startswith('{') and '\n'.join(content).strip().endswith('}'):
					data = json.loads('\n'.join(content).strip())
					content = []
					if data.get("host") and data["host"] != "default":
						self._host = data["host"]
					if data.get("port") and data["port"] != "default":
						self._port = data["port"]
					if data.get("server") and (data["server"] == StateData.Actions[0] or data["server"] == StateData.Actions[1]):
						content.append("server " + data["server"])
					# Handle services
					if data.get("services"):
						for service in data['services']:
							# Streamline service configuration removing default values
							PiCamServer.streamline(service)
							# Validate camera id
							if service.get(StateData.Properties[0]) is None:
								continue
							# Get camera identifier
							CameraId = " on #" + any2str(service[StateData.Properties[0]])
							CameraStarted = False
							# Check camera status
							if service.get(StateData.Properties[1]) and any2bool(service[StateData.Properties[1]]):
								content.append("start service" + CameraId)
								CameraStarted = True
							elif service.get(StateData.Properties[1]) and not any2bool(service[StateData.Properties[1]]):
								if data.get("server") is None or (data.get("server") and data["server"] != StateData.Actions[0]):
									content.append("stop service" + CameraId)
								continue
							# CameraResolution
							if service.get("CameraResolution") and service["CameraResolution"] != "default":
								content.append("set property CameraResolution=" + any2str(service["CameraResolution"]) + CameraId)
							# CameraFramerate
							if service.get("CameraFramerate") and service["CameraFramerate"] != "default":
								content.append("set property CameraFramerate=" + any2str(service["CameraFramerate"]) + CameraId)
							# CameraSleeptime
							if service.get("CameraSleeptime") and service["CameraSleeptime"] != "default":
								content.append("set property CameraSleeptime=" + any2str(service["CameraSleeptime"]) + CameraId)
							# MotionDetectionContour
							if service.get("MotionDetectionContour") and any2bool(service["MotionDetectionContour"]):
								content.append("enable property MotionDetectionContour" + CameraId)
							elif service.get("MotionDetectionContour") and not any2bool(service["MotionDetectionContour"]):
								content.append("disable property MotionDetectionContour" + CameraId)
							# MotionDetectionThreshold
							if service.get("MotionDetectionThreshold") and service["MotionDetectionThreshold"] != "default":
								content.append("set property MotionDetectionThreshold=" + any2str(service["MotionDetectionThreshold"]) + CameraId)
							# RecordingFormat
							if service.get("RecordingFormat") and service["RecordingFormat"] != "default":
								content.append("set property RecordingFormat=" + any2str(service["RecordingFormat"]) + CameraId)
							# RecordingLocation
							if service.get("RecordingLocation") and service["RecordingLocation"] != "default":
								content.append("set property RecordingLocation=" + any2str(service["RecordingLocation"]) + CameraId)
							# StreamingPort
							if service.get("StreamingPort") and service["StreamingPort"] != "default":
								content.append("set property StreamingPort=" + any2str(service["StreamingPort"]) + CameraId)
							# StreamingSleeptime
							if service.get("StreamingSleeptime") and service["StreamingSleeptime"] != "default":
								content.append("set property StreamingSleeptime=" + any2str(service["StreamingSleeptime"]) + CameraId)
							# Function: CameraMotionDetection
							if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
								content.append("enable property CameraMotionDetection" + CameraId)
							elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
								if not CameraStarted:
									content.append("disable property CameraMotionDetection" + CameraId)
							# Function CameraRecording
							if service.get("CameraRecording") and any2bool(service["CameraRecording"]):
								content.append("enable property CameraRecording" + CameraId)
							elif service.get("CameraRecording") and not any2bool(service["CameraRecording"]):
								if not CameraStarted:
									content.append("disable property CameraRecording" + CameraId)
							# Function: CameraStreaming
							if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
									content.append("enable property CameraStreaming" + CameraId)
							elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
								if not CameraStarted:
									content.append("disable property CameraStreaming" + CameraId)
				# Build composed command
				for cmdline in content:
					if cmdline.strip() != '' and not cmdline.strip().startswith('#'):
						if command is not None:
							command += ' and ' + cmdline.strip()
						else:
							command = cmdline.strip()
			except BaseException as baserr:
				self.log(["Error transforming configuration into command:", baserr], type="ERROR", server=False)
		return command


# Class: CmdData
class StateData:
	Actions = ['init', 'shutdown', 'start', 'stop', 'set', 'enable', 'disable', 'status', 'echo', 'load', 'save']
	Subjects = ['server', 'service', 'property']
	Properties = ['CameraId', 'CameraStatus', 'CameraStreaming', 'CameraMotionDetection', 'CameraResolution', 'CameraFramerate',
				  'CameraSleeptime', 'MotionDetectionContour', 'CameraRecording', 'RecordingFormat', 'MotionDetectionThreshold',
				  'RecordingLocation', 'StreamingPort', 'StreamingSleeptime']
	Articles = ['@', 'at', 'on', 'in', 'to', 'from']

	# Constructor
	def __init__(self, statement):
		self.action = None
		self.subject = None
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
		if (self.action == StateData.Actions[0] or self.action == StateData.Actions[1] or self.action == StateData.Actions[7] or self.action == StateData.Actions[8] or self.action == StateData.Actions[9] or self.action == StateData.Actions[10]) and not self.subject == StateData.Subjects[0]:
			raise RuntimeError("Invalid subject of init/shutdown/status/echo/load/save action: " + any2str(self.subject))
		elif (self.action == StateData.Actions[2] or self.action == StateData.Actions[3]) and self.subject != StateData.Subjects[1]:
			raise RuntimeError("Invalid subject of start/stop action: " + any2str(self.subject))
		elif (self.action == StateData.Actions[4] or self.action == StateData.Actions[5] or self.action == StateData.Actions[6]) and self.subject != StateData.Subjects[2]:
			raise RuntimeError("Invalid action for property action: " + any2str(self.action))
		elif (self.subject == StateData.Subjects[1] or self.subject == StateData.Subjects[2]) and self.target is None:
			raise RuntimeError("Unknown target for the specified subject and action: " + any2str(self.subject) + "/" + any2str(self.action))
		elif self.action is None or self.action == '':
			raise RuntimeError("Action can not be null")
		elif self.subject is None or self.subject == '':
			raise RuntimeError("Subject can not be null")

	# Method: _parse
	def _parse(self, data):
		if data is not None and data != []:
			if data[0].strip() in self.Actions:
				self.action = data[0].strip()
				del data[0]
				self._parse(data)
			elif data[0].strip() in self.Subjects:
				self.subject = data[0].strip()
				del data[0]
				if self.subject == self.Subjects[2]:
					index = None
					useprep = list(set(self.Articles) & set(data))
					useaction = list(set(self.Actions) & set(data))
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
					if not self.property.split('=')[0].strip() in self.Properties:
						raise RuntimeError("Invalid property: " + self.property.split('=')[0].strip())
				self._parse(data)
			elif data[0].strip() in self.Articles:
				del data[0]
				if data[0].strip()[0] in ['.', '/']:
					self.target = str(data[0].strip())
				else:
					self.target = '#' + filter(str.isdigit, str(data[0].strip()))
				del data[0]
				self._parse(data)
			else:
				raise RuntimeError("Invalid command part: " + data[0].strip())

	# Method: getTextCommand
	def getStatement(self):
		outcmd = None
		if self.action is not None and self.subject is not None:
			outcmd = self.action + " " + self.subject
			if self.subject == self.Subjects[2]:
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
		return self.Actions

	# Method: getSujects
	def getSujects(self):
		return self.Subjects

	# Method: getProperties
	def getProperties(self):
		return self.Properties

	# Method: getArticles
	def getArticles(self):
		return self.Articles


# Function: usage
def usage():
	print "\n" + __project__ + " " + __module__ + " " + __version__ + ", " + __license__ + ", " + __copyright__ + """
Usage: picam -c "init server" [-f ./picam.cfg] -i "0.0.0.0" -p 9079

Options:
 -v, --verbose    run in verbosity mode
 -c, --command    describe the command that should be executed by server component
 -i, --interface  host interface to start server component
 -h, --host       host name/ip of the server for client connectivity
 -p, --port       host port number for client connectivity
 -f, --file       file with command to start server instance or to run client commands
 --help           this help text
 --version        version of picam client

Examples:
> picam -c "init server"
> picam --command="init server"
  = run server (using default hostname and port) using input options
> picam init server
  = run server (using default hostname and port) aggregating command from all input parameters
> picam -c "init server" -i "0.0.0.0" -p 6400
> picam --command="init server" --interface="127.0.0.1" --port=6400
  = run server (using default hostname and port) using input options
> picam -c "start service on #1"
> picam --command="start service on c1"
  = run client to start on server camera #1. The client will connect to server using default port
> picam enable recording on c0
  = run client (using default hostname and port) aggregating command from all input parameters
> picam -c "set property CameraResolution=1280,720 on c1" -h "192.168.0.100" -p 6400
> picam --command="set property CameraResolution=1280,720 on c1" --host="127.0.0.1" --port=6400
  = run client that will send the command described by a specific option to a dedicated server
"""


# Function: str2bool
def any2bool(v):
	if isinstance(v, bool):
		return v
	if isinstance(v, int):
		return True if v > 0 else False
	elif v.lower() in ("on", "yes", "true", "t", "1", "enable", "enabled", "active", "start", "started"):
		return True
	elif v.lower() in ("off", "no", "false", "f", "0", "disable", "disabled", "inactive", "stop", "stopped"):
		return False
	else:
		return False

# Function: any2int
def any2int(v):
	if v is not None:
		if isinstance(v, int):
			return v
		else:
			try:
				return int(v)
			except:
				return None
	else:
		return None

# Function: any2float
def any2float(v):
	if v is not None:
		if isinstance(v, float):
			return v
		else:
			try:
				return float(v)
			except:
				return None
	else:
		return None

# Function: any2str
def any2str(v):
	if v is not None:
		if isinstance(v, bool):
			return str(v).lower()
		else:
			try:
				return str(v)
			except:
				return None
	else:
		return None

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
	apimode = False
	file = None
	host = None
	port = None
	try:
		# Parse input parameters
		opts, args = getopt.getopt(sys.argv[1:], "c:f:h:i:p:v", ["command=", "file=", "host=", "interface=", "port=", "verbose", "help", "version", "api"])
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
			elif opt == '--api':
				apimode = True
			elif opt == '--help':
				usage()
				sys.exit(0)
			elif opt == '--version':
				print __project__ + " " + __module__ + " " + __version__ + "\n" + __copyright__ + "\n"
				sys.exit(0)
	except BaseException as baserr:
		command = None
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if (command is None or command == '') and file is None and host is None and port is None:
		command = ' '.join(sys.argv[1:])
		if command.strip() == 'help':
			usage()
			sys.exit(0)
	# Instantiate Client module an then run the command
	client = PiCamClient(host, port, api=apimode)
	# Check if a configuration file has been specified, read it ang get all commands defined in
	if file is not None and os.path.isfile(file):
		command = client.load(file, command)
	# Run identified command
	if not apimode:
		client.run(command)
	elif apimode:
		cmdout = client.run(command)
		print cmdout
	# Client normal exist
	sys.exit(0)

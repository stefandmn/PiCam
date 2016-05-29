#!/usr/bin/env python

import cv
import io
from PIL import Image
from picamera import PiCamera


class Motion:

	def load(self, index=1):
		if index > 0:
			camera = cv.CaptureFromCAM(index - 1)
			cv.SetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_WIDTH, 640)
			cv.SetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
			frame = cv.QueryFrame(camera)
		else:
			camera = PiCamera()
			camera.resolution = (640, 480)
			byte_buffer = io.BytesIO()
			camera.capture(byte_buffer, format='jpeg', use_video_port=True)
			byte_buffer.seek(0)
			pil = Image.open(byte_buffer)
			frame = cv.CreateImageHeader(camera.resolution, cv.IPL_DEPTH_8U, 3)
			cv.SetData(frame, pil.tostring())
			cv.CvtColor(frame, frame, cv.CV_RGB2BGR)
		return frame

	def write(self, output, name):
		cv.SaveImage("/tmp/output-" + name + ".png", output)

	def gray(self, input):
		output = cv.CreateImage(cv.GetSize(input), cv.IPL_DEPTH_8U, 1)
		cv.CvtColor(input, output, cv.CV_RGB2GRAY)
		return output

	def absdiff(self, input1, input2):
		output = cv.CloneImage(input1)
		cv.AbsDiff(input1, input2, output)
		return output

	def threshold(self, input):
		output = cv.CreateImage(cv.GetSize(input), cv.IPL_DEPTH_8U, 1)
		cv.Threshold(input, output, 70, 255, cv.CV_THRESH_BINARY)
		return output

	def magnifier(self, input):
		output = cv.CreateImage(cv.GetSize(input), cv.IPL_DEPTH_8U, 1)
		cv.Dilate(input, output, None, 18)
		cv.Erode(output, output, None, 10)
		return output

	def contour(self, input):
		storage = cv.CreateMemStorage(0)
		return cv.FindContours(input, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)

	def movearea(self, contour, input):
		points = []
		area = 0
		while contour:
			bound_rect = cv.BoundingRect(list(contour))
			contour = contour.h_next()

			# Compute the bounding points to the boxes that will be drawn on the screen
			pt1 = (bound_rect[0], bound_rect[1])
			pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])

			# Add this latest bounding box to the overall area that is being detected as movement
			area += ((pt2[0] - pt1[0]) * (pt2[1] - pt1[1]))
			points.append(pt1)
			points.append(pt2)
			cv.Rectangle(input, pt1, pt2, cv.CV_RGB(255,0,0), 1)
		return area


if __name__=="__main__":
	motion = Motion()
	index = 0
	count = 3

	previous_gray = None

	while index < count:
		print "Frame %d" %(index + 1)
		if index == 0:
			previous = motion.load(0)
			motion.write(previous, "init-original")
			previous_gray = motion.gray(previous)
			motion.write(previous_gray, "init-gray")
		else:
			current = motion.load(0)
			motion.write(current, "current-original")
			current_gray = motion.gray(current)
			motion.write(current_gray, "current-gray")
			current_absdiff = motion.absdiff(previous_gray, current_gray)
			motion.write(current_absdiff, "current-absdiff")
			current_threshold = motion.threshold(current_absdiff)
			motion.write(current_threshold, "current-threshold")

			previous_gray = current_gray
	print
#!/usr/bin/env python

import io
import cv
import sys
from PIL import Image
from picamera import PiCamera


class Motion:
	def __init__(self, cam=1):
		if cam > 0:
			self.camera = cv.CaptureFromCAM(cam - 1)
			cv.SetCaptureProperty(self.camera, cv.CV_CAP_PROP_FRAME_WIDTH, 640)
			cv.SetCaptureProperty(self.camera, cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
		else:
			self.camera = PiCamera()
			self.camera.resolution = (640, 480)

	def load(self):
		if isinstance(self.camera, PiCamera):
			byte_buffer = io.BytesIO()
			self.camera.capture(byte_buffer, format='jpeg', use_video_port=True)
			byte_buffer.seek(0)
			pil = Image.open(byte_buffer)
			frame = cv.CreateImageHeader(self.camera.resolution, cv.IPL_DEPTH_8U, 3)
			cv.SetData(frame, pil.tostring())
			cv.CvtColor(frame, frame, cv.CV_RGB2BGR)
		else:
			frame = cv.QueryFrame(self.camera)
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

	def threshold(self, frame):
		cv.Threshold(frame, frame, 35, 255, cv.CV_THRESH_BINARY)
		cv.Dilate(frame, frame, None, 18)
		cv.Erode(frame, frame, None, 10)
		return frame

	def threshold_v2(self, frame):
		cv.Smooth(frame, frame, cv.CV_BLUR, 5,5)
		cv.MorphologyEx(frame, frame, None, None, cv.CV_MOP_OPEN)
		cv.MorphologyEx(frame, frame, None, None, cv.CV_MOP_CLOSE)
		cv.Threshold(frame, frame, 10, 255, cv.CV_THRESH_BINARY_INV)
		return frame

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
			cv.Rectangle(input, pt1, pt2, cv.CV_RGB(255, 0, 0), 1)
		return area


if __name__ == "__main__":
	camera = int(sys.argv[1])
	count = int(sys.argv[2])

	motion = Motion(camera)
	previous_gray = None
	index = 0

	while index < count:
		print "Frame %d" % (index + 1)
		current = motion.load()

		if index == 0:
			motion.write(current, "A." + str(index) + ".1_init-original")
			previous_gray = motion.gray(current)
			motion.write(previous_gray, "A." + str(index) + ".2_init-gray")
		else:
			motion.write(current, "B." + str(index) + ".1_current-original")
			current_gray = motion.gray(current)
			motion.write(current_gray, "B." + str(index) + ".2_current-gray")
			current_absdiff = motion.absdiff(previous_gray, current_gray)
			motion.write(current_absdiff, "B." + str(index) + ".3_current-absdiff")
			current_threshold = motion.threshold(current_absdiff)
			motion.write(current_threshold, "B." + str(index) + ".4_current-threshold")

			previous_gray = current_gray
		index += 1
	print

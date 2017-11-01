#!/usr/bin/env python

import cv
import sys
import time


class Image:

	def load(self, name="image", index=1):
		return cv.LoadImage('/tmp/' + name + str(index) + ".png")

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
	image = Image()

	image1 = image.load(index=1)
	image2 = image.load(index=2)
	image3 = image.load(index=3)

	print
	output_gray1 = image.gray(image1)
	image.write(output_gray1, "gray1")
	output_gray2 = image.gray(image2)
	image.write(output_gray2, "gray2")
	output_gray_diff12 = image.absdiff(output_gray1, output_gray2)
	image.write(output_gray_diff12, "gray-diff12")
	output_gray_diff12_bw = image.threshold(output_gray_diff12)
	image.write(output_gray_diff12_bw, "gray-diff12-bw")
	output_gray_diff12_bw_mag = image.magnifier(output_gray_diff12_bw)
	image.write(output_gray_diff12_bw, "gray-diff12-bw-mag")
	contour = image.contour(output_gray_diff12_bw)
	print "Contours: " + str(len(list(contour)))
	area = image.movearea(contour, image2)
	image.write(image2, "out-image2")
	print 'Movement: ' + repr(area)

	print
	output_gray1 = image.gray(image1)
	image.write(output_gray1, "gray1")
	output_gray3 = image.gray(image3)
	image.write(output_gray3, "gray3")
	output_gray_diff13 = image.absdiff(output_gray1, output_gray3)
	image.write(output_gray_diff13, "gray-diff13")
	output_gray_diff13_bw = image.threshold(output_gray_diff13)
	image.write(output_gray_diff13_bw, "gray-diff13-bw")
	output_gray_diff13_bw_mag = image.magnifier(output_gray_diff13_bw)
	image.write(output_gray_diff13_bw, "gray-diff13-bw-mag")
	contour = image.contour(output_gray_diff13_bw)
	print "Contours: " + str(len(list(contour)))
	area = image.movearea(contour, image3)
	image.write(image3, "out-image3")
	print 'Movement: ' + repr(area)

	print
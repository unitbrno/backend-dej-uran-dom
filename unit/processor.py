# coding=utf-8
import logging
from typing import Type, TextIO, Iterable

import numpy
from scipy import ndimage

from unit.detectors.hough_circle import HoughCircleDetector
from unit.exporters.base import BaseExporter
from unit.exporters.csv import CsvExporter
from unit.filters.edge_detection import gaussian_filter, sobel_gradients
from unit.filters.erosion import erosion_filter
from unit.filters.threshold import threshold_image
from unit.geometry.geometry import longest_inline, longest_line, bbox2
from unit.loader import Loader
from unit.particle import Particle


class Processor(object):
    def __init__(
            self,
            exporter_class: Type[BaseExporter] = CsvExporter,
            loader_class: Type[Loader] = Loader,
    ):
        self._exporter_class = exporter_class
        self._loader_class = loader_class

    def run(self, input_path: str, output_stream: TextIO):
        return self.multiple_run(
            inputs=(input_path,),
            outputs=(output_stream,),
        )

    def multiple_run(self, inputs: Iterable[str], outputs: Iterable[TextIO]) -> None:
        loader = self._loader_class(*inputs)

        for image, input_path, output_stream in zip(loader.load_images(), inputs, outputs):
            logging.debug('Processing {}...'.format(input_path))
            particles = self._detect_particles(image=image)
            exporter = self._exporter_class(particles=particles, _file_obj=output_stream)
            exporter.export()

    def _detect_particles(self, image: numpy.ndarray) -> Iterable[Particle]:
        logging.debug('Applying threshold...')
        thresholded = threshold_image(image, 80)
        logging.debug('Applying erosion...')
        eroded = erosion_filter(thresholded, 23)
        logging.debug('Applying gaussian blur...')
        gaussed = gaussian_filter(eroded)
        logging.debug('Computing sobel gradients...')
        grads, thetas = sobel_gradients(gaussed)

        hough_detector = HoughCircleDetector(gaussed, grads)
        bound_boxes = hough_detector.detect()

        particles = list()

        for x, y, width, height in bound_boxes:
            particle = Particle()
            s = hough_detector._scale
            masked = thresholded[int(x) * s: int(x + width) * s, int(y) * s: int(y + height) * s]

            maxi = 0
            maxi_angle = 0
            for i in range(0, 180, 1):
                line = longest_line(ndimage.interpolation.rotate(masked, i))
                if maxi < line:
                    maxi = line
                    maxi_angle = i

            y, maxY, x, maxX = bbox2(masked)
            particle.width = maxX - x
            particle.height = maxY - y
            particle.max_length = maxi[0]
            particle.thickness = longest_inline(ndimage.interpolation.rotate(masked, maxi_angle + 90))

            # print(particle.width, particle.height, particle.max_length, particle.thickness)
            particles.append(particle)

        return particles

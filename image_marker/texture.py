# -*- coding: utf-8 -*-

import logging
import numpy as np
import pandas as pd
import pydicom
import png
import pathlib

from datetime import datetime
from os import path
from PIL import Image, ImageDraw
from scipy import misc, stats
from skimage.feature import greycomatrix, greycoprops


class Extractor:

    def __init__(self, root):
        self.root = root

    def extract(self, raw):
        ds = pydicom.dcmread(raw)
        tag = (
            ds.AcquisitionNumber,
            ds[(0x2001, 0x100a)].value,
            ds[(0x0008, 0x0013)].value,
        )
        # im = Image.fromarray(ds.pixel_array)
        shape = ds.pixel_array.shape
        image_2d = ds.pixel_array.astype(float)
        image_2d_scaled = (np.maximum(image_2d, 0) / image_2d.max()) * 255.0
        image_2d_scaled = np.uint8(image_2d_scaled)
        w = png.Writer(shape[1], shape[0], greyscale=True)
        now = datetime.now().strftime('%Y-%m-%d-%h-%m-%s')
        pngdir = path.join(
            path.dirname(raw),
            'samples',
            path.basename(raw),
            now,
            *map(str, tag)
        )
        logging.info('processing image: {}'.format(pngdir))
        pathlib.Path(pngdir).mkdir(parents=True, exist_ok=True)
        target = path.join(pngdir, 'sample.png')
        with open(target, 'wb') as f:
            w.write(f, image_2d_scaled)
        return target


class Marker:

    columns = [
        'dissimilarity',
        'correlation',
        'std',
        'entropy',
        'x',
        'y',
        'width',
        'height',
    ]

    def __init__(self, image, area, target_dir):
        self.image = image
        self.area = area
        self.target_dir = target_dir

    def extract_patch(self, location, size):
        im = misc.imread(self.image, flatten=True)
        x, y = location
        width, height = size
        return im[y:y+height, x:x+width]

    def mark_area(self, mat, pos, size):
        im = Image.fromarray(mat)
        graphics = Image.new('RGBA', im.size, (255, 255, 255, 0))
        ctx = ImageDraw.Draw(graphics)
        ctx.rectangle(
            (pos, (pos[0] + size[0], pos[1] + size[1])),
            fill=(255, 255, 255, 0),
            outline="red",
        )
        out = Image.alpha_composite(im.convert('RGBA'), graphics)
        return np.asarray(out)

    def texture_stats(self, patch):
        glcm = greycomatrix(
            patch.astype('int'),
            [3],
            [0, 0.25, 0.5],
            256,
            symmetric=True,
            normed=True,
        )
        dissimilarity = greycoprops(glcm, 'dissimilarity')[0, 0]
        correlation = greycoprops(glcm, 'correlation')[0, 0]
        hist = np.histogram(patch, bins='fd')
        distribution = stats.rv_histogram(hist)
        return patch.std(), distribution.entropy(), dissimilarity, correlation

    def mark(self):
        dir, file = path.split(self.image)
        im = misc.imread(self.image, flatten=True)
        im = self.mark_area(im, self.area[:2], self.area[2:])
        patch = self.extract_patch(self.area[:2], self.area[2:])
        stats = None
        try:
            stats = self.texture_stats(patch)
        except Exception:
            logging.warning('image: {} is too small'.format(file))
            stats = [None] * 4

        target = path.join(dir, 'marked-3', file)
        misc.imsave(target, im)
        return pd.DataFrame(dict(zip(self.columns, stats + self.area)))

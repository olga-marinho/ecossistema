import os
import urllib.request
from collections import namedtuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pose_landmarker_lite.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

OMBROS = (11, 12)
ANCAS = (23, 24)

BINS_COR = 32
BRILHO_MIN_PIXEL = 60
SATURACAO_MIN_PIXEL = 30
BRILHO_MIN_FINAL = 120


Pessoa = namedtuple("Pessoa", ["x", "cor"])


def _cor_predominante(pixels_bgr):
    if pixels_bgr is None or len(pixels_bgr) == 0:
        return None

    pixels = pixels_bgr.astype(np.int32)
    max_c = pixels.max(axis=1)
    min_c = pixels.min(axis=1)
    sat = max_c - min_c
    mask = (max_c >= BRILHO_MIN_PIXEL) & (sat >= SATURACAO_MIN_PIXEL)
    candidatos = pixels[mask]
    if len(candidatos) == 0:
        candidatos = pixels

    quantizada = (candidatos // BINS_COR) * BINS_COR
    chaves = (
        quantizada[:, 0].astype(np.int64) * 65536
        + quantizada[:, 1].astype(np.int64) * 256
        + quantizada[:, 2].astype(np.int64)
    )
    valores, contagens = np.unique(chaves, return_counts=True)
    chave = int(valores[np.argmax(contagens)])
    b = chave // 65536
    g = (chave // 256) % 256
    r = chave % 256

    meio = BINS_COR // 2
    b = min(255, b + meio)
    g = min(255, g + meio)
    r = min(255, r + meio)

    maximo = max(r, g, b)
    if maximo < BRILHO_MIN_FINAL:
        if maximo == 0:
            r = g = b = BRILHO_MIN_FINAL
        else:
            escala = BRILHO_MIN_FINAL / maximo
            r = int(min(255, r * escala))
            g = int(min(255, g * escala))
            b = int(min(255, b * escala))

    return (r, g, b)


class Detector:
    def __init__(self, num_poses=5):
        if not os.path.exists(MODEL_PATH):
            print("A descarregar modelo MediaPipe...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            num_poses=num_poses,
            running_mode=vision.RunningMode.VIDEO,
        )
        self._detector = vision.PoseLandmarker.create_from_options(options)
        self._timestamp = 0
        self._ultimo_frame = None
        self._ultimos_torsos = []

        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def detetar(self):
        ret, frame = self.cap.read()
        if not ret:
            return []

        frame = cv2.flip(frame, 1)
        self._ultimo_frame = frame
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        resultado = self._detector.detect_for_video(mp_image, self._timestamp)
        self._timestamp += 33

        pessoas = []
        torsos = []
        if resultado.pose_landmarks:
            for landmarks in resultado.pose_landmarks:
                indices = OMBROS + ANCAS
                x_centro = sum(landmarks[i].x for i in indices) / len(indices)

                xs = [landmarks[i].x for i in indices]
                ys = [landmarks[i].y for i in indices]
                x_min = max(0, int(min(xs) * w))
                x_max = min(w, int(max(xs) * w))
                y_min = max(0, int(min(ys) * h))
                y_max = min(h, int(max(ys) * h))

                cor = None
                if x_max - x_min >= 5 and y_max - y_min >= 5:
                    torsos.append((x_min, y_min, x_max, y_max))
                    regiao = frame[y_min:y_max, x_min:x_max]
                    cor = _cor_predominante(regiao.reshape(-1, 3))

                pessoas.append(Pessoa(x_centro, cor))

        self._ultimos_torsos = torsos
        return pessoas

    def cor_dos_torsos(self):
        if self._ultimo_frame is None or not self._ultimos_torsos:
            return None

        regioes = []
        for (x_min, y_min, x_max, y_max) in self._ultimos_torsos:
            regiao = self._ultimo_frame[y_min:y_max, x_min:x_max]
            if regiao.size:
                regioes.append(regiao.reshape(-1, 3))

        if not regioes:
            return None

        return _cor_predominante(np.concatenate(regioes, axis=0))

    def fechar(self):
        self.cap.release()

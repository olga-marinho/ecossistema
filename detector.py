import os
import urllib.request
from collections import namedtuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detector.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_full_range/float16/1/blaze_face_full_range.tflite"

BINS_COR = 32
BRILHO_MIN_PIXEL = 60
SATURACAO_MIN_PIXEL = 30
BRILHO_MIN_FINAL = 120
BRILHO_ALVO_COR = 170
GANHO_MAX_CLAREAMENTO = 1.8

MIN_LADO_QUADRADO = 5
PERCENTIL_SATURACAO = 65
SATURACAO_MIN_DOMINANTE = 45
SATURACAO_LIMIAR_NEUTRO = 55
FRACAO_MIN_PIXEIS_SATURADOS = 0.28
MIN_DETECAO_CONFIANCA = 0.35
ALFA_SUAVIZACAO_COR = 0.35


Pessoa = namedtuple("Pessoa", ["id", "x", "cor"])


def _cor_predominante(pixels_bgr):
    if pixels_bgr is None or len(pixels_bgr) == 0:
        return None

    pixels = pixels_bgr.astype(np.uint8)
    hsv = cv2.cvtColor(
        pixels.reshape(-1, 1, 3),
        cv2.COLOR_BGR2HSV
    ).reshape(-1, 3)

    brilho = hsv[:, 2].astype(np.int32)
    sat = hsv[:, 1].astype(np.int32)

    mask_brilho = brilho >= BRILHO_MIN_PIXEL
    candidatos = pixels[mask_brilho]
    sat_candidatos = sat[mask_brilho]

    if len(candidatos) == 0:
        candidatos = pixels
        sat_candidatos = sat

    if len(sat_candidatos) > 0:
        sat_limite = max(
            SATURACAO_MIN_DOMINANTE,
            int(np.percentile(sat_candidatos, PERCENTIL_SATURACAO))
        )

        mask_sat = sat_candidatos >= sat_limite
        sat_mediana = float(np.median(sat_candidatos))
        fracao_sat = float(np.count_nonzero(mask_sat)) / float(len(sat_candidatos))

        if (
            np.any(mask_sat)
            and sat_mediana >= SATURACAO_LIMIAR_NEUTRO
            and fracao_sat >= FRACAO_MIN_PIXEIS_SATURADOS
        ):
            candidatos = candidatos[mask_sat]

    candidatos_i32 = candidatos.astype(np.int32)

    mediana = np.median(candidatos_i32, axis=0)
    b, g, r = [int(v) for v in mediana]

    b = min(255, (b // BINS_COR) * BINS_COR + (BINS_COR // 2))
    g = min(255, (g // BINS_COR) * BINS_COR + (BINS_COR // 2))
    r = min(255, (r // BINS_COR) * BINS_COR + (BINS_COR // 2))

    maximo = max(r, g, b)
    if maximo < BRILHO_MIN_FINAL:
        if maximo == 0:
            r = g = b = BRILHO_MIN_FINAL
        else:
            escala = BRILHO_MIN_FINAL / maximo
            r = int(min(255, r * escala))
            g = int(min(255, g * escala))
            b = int(min(255, b * escala))

    # Compensa baixa luminosidade mantendo o tom da cor.
    maximo = max(r, g, b)
    if maximo < BRILHO_ALVO_COR:
        if maximo == 0:
            r = g = b = BRILHO_ALVO_COR
        else:
            ganho = min(GANHO_MAX_CLAREAMENTO, BRILHO_ALVO_COR / maximo)
            r = int(min(255, r * ganho))
            g = int(min(255, g * ganho))
            b = int(min(255, b * ganho))

    return (r, g, b)


def _suavizar_cor(cor_anterior, cor_atual):
    if cor_atual is None:
        return cor_anterior

    if cor_anterior is None:
        return cor_atual

    return tuple(
        int(round(cor_anterior[i] * (1.0 - ALFA_SUAVIZACAO_COR) + cor_atual[i] * ALFA_SUAVIZACAO_COR))
        for i in range(3)
    )


def _estimar_quadrado_torso(fx_min, fy_min, fw, fh, largura_frame, altura_frame):
    centro_torso_x = fx_min + fw // 2
    centro_torso_y = fy_min + fh + int(fh * 1.5)
    lado_torso = int(fw * 1.5)

    if lado_torso < MIN_LADO_QUADRADO:
        return None

    meio_lado = lado_torso // 2

    qx_min = max(0, centro_torso_x - meio_lado)
    qy_min = max(0, centro_torso_y - meio_lado)
    qx_max = min(largura_frame, qx_min + lado_torso)
    qy_max = min(altura_frame, qy_min + lado_torso)

    qx_min = max(0, qx_max - lado_torso)
    qy_min = max(0, qy_max - lado_torso)

    qx_min = max(0, min(largura_frame - 1, qx_min))
    qx_max = max(0, min(largura_frame, qx_max))
    qy_min = max(0, min(altura_frame - 1, qy_min))
    qy_max = max(0, min(altura_frame, qy_max))

    if qx_max - qx_min < MIN_LADO_QUADRADO or qy_max - qy_min < MIN_LADO_QUADRADO:
        return None

    return (qx_min, qy_min, qx_max, qy_max)


class Detector:
    def __init__(self, num_poses=5, mostrar_camera_debug=False):
        if not os.path.exists(MODEL_PATH):
            print("A descarregar modelo MediaPipe...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

        self._running_mode = vision.RunningMode.VIDEO
        self._detector = self._criar_detector(self._running_mode)
        self._timestamp = 0
        self._ultimo_frame = None
        self._ultimas_amostras_cor = []
        self._mostrar_camera_debug = mostrar_camera_debug
        self._cores_suavizadas_slots = []
        self._proximo_id = 0
        self._pessoas_rastreadas = []
        self._falhas_detector = 0
        self._detector_desativado = False
        self._erro_detector_reportado = False
        self._modo_fallback_ativado = False

        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def _criar_detector(self, running_mode):
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=running_mode,
            min_detection_confidence=MIN_DETECAO_CONFIANCA,
        )
        return vision.FaceDetector.create_from_options(options)

    def _detetar_mediapipe(self, mp_image):
        if self._running_mode == vision.RunningMode.VIDEO:
            resultado = self._detector.detect_for_video(mp_image, self._timestamp)
            self._timestamp += 33
            return resultado

        return self._detector.detect(mp_image)

    def _ativar_fallback_image_mode(self):
        self._running_mode = vision.RunningMode.IMAGE
        self._detector = self._criar_detector(self._running_mode)
        self._timestamp = 0
        self._modo_fallback_ativado = True
        print("[WARN] MediaPipe em modo IMAGE por compatibilidade neste PC.")

    def _mostrar_janela_debug(self, frame):
        if not self._mostrar_camera_debug:
            return

        frame_debug = frame.copy()

        for (x_min, y_min, x_max, y_max, cor_rgb) in self._ultimas_amostras_cor:
            cv2.rectangle(frame_debug, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)

            if cor_rgb is not None:
                cor_bgr = (cor_rgb[2], cor_rgb[1], cor_rgb[0])
                y_topo = max(0, y_min - 20)
                cv2.rectangle(frame_debug, (x_min, y_topo), (x_min + 20, y_min), cor_bgr, -1)
                cv2.rectangle(frame_debug, (x_min, y_topo), (x_min + 20, y_min), (0, 0, 0), 1)

        cv2.imshow("Teste", frame_debug)
        cv2.waitKey(1)

    def detetar(self):
        if self._detector_desativado:
            return []

        ret, frame = self.cap.read()
        if not ret:
            return []

        frame = cv2.flip(frame, 1)
        self._ultimo_frame = frame
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            resultado = self._detetar_mediapipe(mp_image)
            self._falhas_detector = 0
            self._erro_detector_reportado = False
        except RuntimeError as e:
            self._falhas_detector += 1

            if not self._erro_detector_reportado:
                print(f"[WARN] Falha no detector MediaPipe: {e}")
                self._erro_detector_reportado = True

            if self._running_mode == vision.RunningMode.VIDEO and not self._modo_fallback_ativado:
                try:
                    self._ativar_fallback_image_mode()
                    resultado = self._detetar_mediapipe(mp_image)
                    self._falhas_detector = 0
                    self._erro_detector_reportado = False
                except Exception:
                    return []
            else:
                if self._falhas_detector >= 30:
                    self._detector_desativado = True
                    print("[ERRO] Detector desativado por falhas repetidas neste PC.")
                return []
        except Exception as e:
            if not self._erro_detector_reportado:
                print(f"[WARN] Erro inesperado no detector: {e}")
                self._erro_detector_reportado = True
            return []

        deteccoes = []
        if resultado.detections:
            for detection in resultado.detections:
                bbox = detection.bounding_box
                fx_min = bbox.origin_x
                fy_min = bbox.origin_y
                fw = bbox.width
                fh = bbox.height

                x_centro = (fx_min + fw / 2) / w

                cor = None
                quadrado = _estimar_quadrado_torso(fx_min, fy_min, fw, fh, w, h)
                if quadrado is not None:
                    qx_min, qy_min, qx_max, qy_max = quadrado
                    regiao = frame[qy_min:qy_max, qx_min:qx_max]
                    cor = _cor_predominante(regiao.reshape(-1, 3))

                deteccoes.append({"x": x_centro, "cor": cor, "bbox": quadrado})

        matched_detections = set()
        novas_pessoas_rastreadas = []

        for tracker in self._pessoas_rastreadas:
            indice_melhor = -1
            distancia_melhor = 0.22

            for i, det in enumerate(deteccoes):
                if i in matched_detections:
                    continue
                dist = abs(tracker["x"] - det["x"])
                if dist < distancia_melhor:
                    distancia_melhor = dist
                    indice_melhor = i

            if indice_melhor != -1:
                det = deteccoes[indice_melhor]
                matched_detections.add(indice_melhor)

                cor_suavizada = _suavizar_cor(tracker["cor"], det["cor"])
                x_suavizado = tracker["x"] + (det["x"] - tracker["x"]) * 0.4

                novas_pessoas_rastreadas.append({
                    "id": tracker["id"],
                    "x": x_suavizado,
                    "cor": cor_suavizada,
                    "frames_missing": 0,
                    "bbox": det["bbox"]
                })
            else:
                tracker["frames_missing"] += 1
                if tracker["frames_missing"] < 25:
                    novas_pessoas_rastreadas.append(tracker)

        for i, det in enumerate(deteccoes):
            if i not in matched_detections:
                novas_pessoas_rastreadas.append({
                    "id": self._proximo_id,
                    "x": det["x"],
                    "cor": det["cor"],
                    "frames_missing": 0,
                    "bbox": det["bbox"]
                })
                self._proximo_id += 1

        self._pessoas_rastreadas = novas_pessoas_rastreadas

        pessoas_retorno = []
        amostras_debug = []
        for p in self._pessoas_rastreadas:
            if p["frames_missing"] < 12:
                pessoas_retorno.append(Pessoa(p["id"], p["x"], p["cor"]))
                if p["bbox"] is not None:
                    qx_min, qy_min, qx_max, qy_max = p["bbox"]
                    amostras_debug.append((qx_min, qy_min, qx_max, qy_max, p["cor"]))

        self._ultimas_amostras_cor = amostras_debug
        self._mostrar_janela_debug(frame)

        return sorted(pessoas_retorno, key=lambda p: p.x)

    def cor_dos_torsos(self):
        if self._ultimo_frame is None or not self._ultimas_amostras_cor:
            return None

        regioes = []
        for (x_min, y_min, x_max, y_max, _) in self._ultimas_amostras_cor:
            regiao = self._ultimo_frame[y_min:y_max, x_min:x_max]
            if regiao.size:
                regioes.append(regiao.reshape(-1, 3))

        if not regioes:
            return None

        return _cor_predominante(np.concatenate(regioes, axis=0))

    def fechar(self):
        self.cap.release()

        if self._mostrar_camera_debug:
            try:
                cv2.destroyWindow("Teste")
            except cv2.error:
                pass

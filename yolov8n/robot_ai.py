"""Direct Python API for a robot controller: ONNX detection + target alignment.

Only numpy, opencv-python and onnxruntime are required by this module.
Positive angular velocity = turn left, negative = turn right, in rad/s.
The optional control callback receives (linear_velocity_m_s, angular_velocity_rad_s).
No network, display windows, image saving or robot connection is started on import.
"""
import ast
import json
from dataclasses import dataclass
from pathlib import Path
import time

import cv2
import numpy as np
import onnxruntime as ort

if __package__:
    from .target_alignment import AlignmentConfig, AlignmentResult, TargetAligner, draw_alignment
else:
    from target_alignment import AlignmentConfig, AlignmentResult, TargetAligner, draw_alignment


@dataclass
class AIResult:
    alignment: AlignmentResult
    detections: list
    annotated_frame: np.ndarray | None
    inference_ms: float


class TargetAI:
    """Create once per controller, then call process_frame for each new BGR uint8 image."""
    def __init__(self, weights=None, *, alignment=None, confidence=0.25, iou=0.7, providers=None,
                 tracking_confidence=None):
        if not 0 <= confidence <= 1 or not 0 <= iou <= 1:
            raise ValueError("confidence and iou must be between 0 and 1.")
        self.confidence, self.iou = confidence, iou
        self.tracking_confidence = min(0.15, confidence) if tracking_confidence is None else tracking_confidence
        self.aligner = TargetAligner(alignment, confidence=confidence,
                                     tracking_confidence=self.tracking_confidence)
        path = Path(weights) if weights is not None else Path(__file__).resolve().parent/"best.onnx"
        if not path.is_file():
            raise FileNotFoundError(f"ONNX model not found: {path}")
        available = ort.get_available_providers()
        if providers is None:
            providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                         if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"])
        if not providers or any(provider not in available for provider in providers):
            raise ValueError(f"Requested providers {providers}; available: {available}")
        settings = ort.SessionOptions()
        settings.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(path), sess_options=settings, providers=providers)
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("Expected one input and one raw detection output; export with nms=False.")
        self.input_name = inputs[0].name
        shape = inputs[0].shape
        if (inputs[0].type != "tensor(float)" or len(shape) != 4 or shape[:2] != [1,3]
                or not all(isinstance(v,int) and v > 0 for v in shape[2:])):
            raise ValueError(f"Expected fixed FP32 [1,3,H,W] model, got {shape}, {inputs[0].type}")
        self.height, self.width = shape[2:]
        metadata = self.session.get_modelmeta().custom_metadata_map
        if alignment is None and "target_alignment" in metadata:
            self.aligner = TargetAligner(AlignmentConfig.from_dict(json.loads(metadata["target_alignment"])),
                                         confidence=confidence, tracking_confidence=self.tracking_confidence)
        names = ast.literal_eval(metadata.get("names","{}"))
        self.names = {int(k):v for k,v in names.items()} if isinstance(names,dict) else dict(enumerate(names))
        if self.names.get(self.aligner.config.target_class) != "target":
            raise ValueError("ONNX class mapping must retain target = 11; export the trained checkpoint.")
        if set(self.names) != set(range(len(self.names))):
            raise ValueError("Expected contiguous original class IDs.")
        out_shape = outputs[0].shape
        if len(out_shape) != 3 or out_shape[1] != 4+len(self.names):
            raise ValueError(f"Expected raw [1,4+classes,anchors], got {out_shape}. Use export_onnx.py.")
        self.providers = self.session.get_providers()
        self.session.run(None,{self.input_name:np.zeros(shape,dtype=np.float32)})

    def _detect(self, frame):
        h,w = frame.shape[:2]
        gain = min(self.width/w,self.height/h)
        size = (round(w*gain),round(h*gain))
        resized = cv2.resize(frame,size,interpolation=cv2.INTER_LINEAR)
        left = round((self.width-size[0])/2-0.1)
        top = round((self.height-size[1])/2-0.1)
        padded = cv2.copyMakeBorder(resized,top,self.height-size[1]-top,
            left,self.width-size[0]-left,cv2.BORDER_CONSTANT,value=(114,114,114))
        tensor = np.ascontiguousarray(padded[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255.0
        begin = time.perf_counter()
        raw = self.session.run(None,{self.input_name:tensor})[0]
        inference_ms = (time.perf_counter()-begin)*1000
        rows = raw[0].T
        scores = rows[:,4:]
        class_ids = scores.argmax(axis=1)
        best_scores = scores.max(axis=1)
        keep = ((class_ids == self.aligner.config.target_class) &
                (best_scores >= self.tracking_confidence) & np.isfinite(rows).all(axis=1) &
                (rows[:,2] > 0) & (rows[:,3] > 0))
        rows, best_scores = rows[keep], best_scores[keep]
        if not len(rows):
            return [],inference_ms
        order = best_scores.argsort()[::-1][:30000]
        rows,best_scores = rows[order],best_scores[order]
        xywh = np.column_stack((rows[:,0]-rows[:,2]/2,rows[:,1]-rows[:,3]/2,rows[:,2:4]))
        selected = cv2.dnn.NMSBoxes(xywh.tolist(),best_scores.tolist(),self.tracking_confidence,self.iou)
        detections = []
        for index in np.asarray(selected,dtype=int).reshape(-1)[:100]:
            x,y,bw,bh = xywh[index]
            box = [(x-left)/gain,(y-top)/gain,(x+bw-left)/gain,(y+bh-top)/gain]
            box = [float(np.clip(box[0],0,w)),float(np.clip(box[1],0,h)),
                   float(np.clip(box[2],0,w)),float(np.clip(box[3],0,h))]
            if box[2] > box[0] and box[3] > box[1]:
                detections.append(dict(xyxy=box,confidence=float(best_scores[index]),
                    class_id=self.aligner.config.target_class))
        return detections,inference_ms

    @staticmethod
    def _apply(control, state):
        if control is not None:
            control(state.linear_velocity,state.angular_velocity)

    def process_frame(self, frame_bgr, *, control=None, captured_at=None, draw=True):
        """Detect, align and optionally call control(0.0, angular_rad_s).

        frame_bgr: original unmirrored uint8 HxWx3 BGR image.
        captured_at: time.monotonic() from THIS process/host, captured when
        the frame became available, never the robot simulation's time counter.
        If camera stalls, call tick() on every control tick to apply stale STOP.
        """
        stamp = time.monotonic() if captured_at is None else captured_at
        if frame_bgr is None:
            state = self.aligner.reset("no_frame")
            self._apply(control,state)
            return AIResult(state,[],None,0.0)
        try:
            if (not isinstance(frame_bgr,np.ndarray) or frame_bgr.dtype != np.uint8
                    or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3
                    or frame_bgr.shape[0] == 0 or frame_bgr.shape[1] == 0):
                raise ValueError("frame_bgr must be a nonempty uint8 HxWx3 image.")
            now = time.monotonic()
            if not np.isfinite(stamp) or now-stamp > self.aligner.config.frame_timeout or stamp > now+0.02:
                state = self.aligner.reset("stale_frame")
                self._apply(control,state)
                annotated = draw_alignment(frame_bgr,state,self.aligner.config) if draw else None
                return AIResult(state,[],annotated,0.0)
            detections,inference_ms = self._detect(frame_bgr)
            h,w = frame_bgr.shape[:2]
            state = self.aligner.update(detections,w,h,frame_time=stamp)
        except Exception:
            self._apply(control,self.aligner.reset("inference_error"))
            raise
        self._apply(control,state)
        annotated = None
        if draw:
            annotated = frame_bgr.copy()
            if state.found and state.display_box_xyxy is not None:
                x1,y1,x2,y2 = map(round,state.display_box_xyxy)
                cv2.rectangle(annotated,(x1,y1),(x2,y2),(70,210,70),2)
                cv2.putText(annotated,f"target #{state.target_id} {state.confidence:.2f}",(x1,max(15,y1-7)),
                            cv2.FONT_HERSHEY_SIMPLEX,.5,(70,210,70),1,cv2.LINE_AA)
            annotated = draw_alignment(annotated,state,self.aligner.config)
        return AIResult(state,detections,annotated,inference_ms)

    def tick(self, control=None):
        """Call on each robot control tick when no new frame is ready."""
        state = self.aligner.current_command()
        self._apply(control,state)
        return state

    def stop(self, control=None):
        state = self.aligner.reset("stopped")
        self._apply(control,state)
        return state

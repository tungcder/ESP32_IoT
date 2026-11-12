"""One camera owner; direct LAN ICE, no external STUN/TURN service."""
import asyncio
import secrets
import time

import cv2
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError

from .service import FRAME_TIMEOUT
from yolov8n.target_alignment import draw_alignment_guides

CAMERA_TIMEOUT = 10


class FrameClock:
    """Reject buffered frames, then re-sync only after media arrives at a live pace."""
    def __init__(self):
        self.offset = None
        self.previous = None
        self.recovering = False
        self.paced = 0

    def accept(self, pts, stamp):
        if pts is None:
            return True
        previous = self.previous
        self.previous = (pts, stamp)
        offset = stamp - pts
        if self.offset is None:
            self.offset = offset
            return True
        step = pts - previous[0]
        elapsed = stamp - previous[1]
        if step <= 0 or offset - self.offset > FRAME_TIMEOUT:
            self.recovering = True
        if self.recovering:
            # Bursts of old decoded frames cannot establish a new live baseline.
            paced = 0.01 <= elapsed <= 0.25 and 0 < step <= 0.25 and 0.5 <= elapsed / step <= 1.5
            self.paced = self.paced + 1 if paced else 0
            if self.paced < 3:
                return False
            self.offset, self.recovering, self.paced = offset, False, 0
        else:
            # Follow small clock drift without accepting a sudden delay jump.
            self.offset += max(-0.001, min(0.001, offset - self.offset))
        return True


class CameraReceiver:
    def __init__(self, service):
        self.service = service
        self.lock = asyncio.Lock()
        self.pc = None
        self.owner = None
        self.generation = None
        self.tasks = set()
        self.closing = set()
        self.last_frame = 0
        self.started = 0
        self.received = 0
        self.has_video = False

    def task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def offer(self, token, sdp, kind):
        if kind != "offer" or not isinstance(sdp, str) or len(sdp) > 65536:
            raise ValueError("Du lieu ket noi camera khong hop le.")
        async with self.lock:
            if self.pc is not None:
                raise ValueError("Đã có camera kết nối. Dừng camera cũ trên laptop trước.")
            if not self.service.paired(token):
                raise ValueError("QR đã hết hạn hoặc đã dùng. Quét QR mới trên laptop.")
            generation = await asyncio.to_thread(self.service.begin_camera)
            pc = self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
            self.generation = generation
            owner = self.owner = secrets.token_urlsafe(32)
            self.started, self.last_frame = time.monotonic(), 0
            self.received, self.has_video = 0, False

        @pc.on("track")
        def on_track(track):
            if self.pc is pc and self.owner == owner and track.kind == "video" and not self.has_video:
                self.has_video = True
                self.task(self.receive(track, owner, generation))
            else:
                track.stop()

        @pc.on("connectionstatechange")
        async def connection_state():
            if pc.connectionState in ("failed", "closed"):
                self.task(self.close(owner, "Kết nối camera iPhone đã ngắt"))

        try:
            await asyncio.wait_for(pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=kind)), 10)
            if not self.has_video:
                raise ValueError("Kết nối không chứa video camera.")
            answer = await pc.createAnswer()
            await asyncio.wait_for(pc.setLocalDescription(answer), 10)
            async with self.lock:
                if self.owner != owner:
                    raise ValueError("Phiên camera đã đóng trong lúc kết nối.")
                self.service.rotate_pair()
            self.task(self.monitor(owner))
            return dict(sdp=pc.localDescription.sdp, type=pc.localDescription.type, owner=owner)
        except BaseException:
            await self.close(owner, "Không thiết lập được WebRTC; quét QR và thử lại")
            raise

    @staticmethod
    def decode(frame, preview, alignment=None):
        image = frame.to_ndarray(format="bgr24")
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        height, width = image.shape[:2]
        if max(width, height) > 640:
            ratio = 640 / max(width, height)
            image = cv2.resize(image, (round(width * ratio), round(height * ratio)))
        jpeg = None
        if preview:
            # Draw only on the display copy; YOLO always receives clean pixels.
            display = draw_alignment_guides(image, alignment)
            ok, encoded = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                jpeg = encoded.tobytes()
        return image, jpeg

    async def receive(self, track, owner, generation):
        clock = FrameClock()
        latest = asyncio.Queue(maxsize=1)
        decoder = asyncio.create_task(self.decode_frames(latest, owner, generation))
        try:
            while self.owner == owner:
                frame = await track.recv()
                stamp = time.monotonic()
                pts = float(frame.pts * frame.time_base) if frame.pts is not None and frame.time_base else None
                recovering = clock.recovering
                if not clock.accept(pts, stamp):
                    continue
                if recovering:
                    self.service.log("Đã đồng bộ lại timestamp camera sau gián đoạn; xe không tự khởi động lại")
                if latest.full():
                    latest.get_nowait()
                latest.put_nowait((frame, stamp))
        except (MediaStreamError, asyncio.CancelledError):
            pass
        except Exception as error:
            await self.close(owner, "Lỗi nhận hình WebRTC: " + type(error).__name__)
        finally:
            decoder.cancel()
            await asyncio.gather(decoder, return_exceptions=True)
            if self.owner == owner:
                await self.close(owner, "Camera iPhone đã dừng gửi hình")

    async def decode_frames(self, latest, owner, generation):
        last_preview = 0
        try:
            while self.owner == owner:
                frame, stamp = await latest.get()
                if time.monotonic() - stamp > FRAME_TIMEOUT:
                    continue
                image, jpeg = await asyncio.to_thread(self.decode, frame, stamp - last_preview >= 1 / 15,
                                                     self.service.alignment_config)
                if jpeg:
                    last_preview = stamp
                if self.owner != owner:
                    break
                if await asyncio.to_thread(self.service.receive_frame, image, stamp, generation, jpeg):
                    self.last_frame = stamp
                    self.received += 1
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.task(self.close(owner, "Lỗi giải mã hình WebRTC: " + type(error).__name__))

    async def monitor(self, owner):
        while self.owner == owner:
            await asyncio.sleep(0.5)
            now = time.monotonic()
            if self.last_frame and now - self.last_frame > CAMERA_TIMEOUT:
                await self.close(owner, "Không có hình hợp lệ trong 10 giây; kiểm tra Safari, Wi-Fi và quét QR mới")
            elif not self.last_frame and now - self.started > 20:
                await self.close(owner, "Chưa nhận được hình trong 20 giây; kiểm tra Safari và tường lửa UDP")

    def status(self, owner):
        if not self.owner or not secrets.compare_digest(str(owner), self.owner):
            raise ValueError("Phiên camera đã hết. Quét QR mới trên laptop.")
        return dict(connected=self.pc.connectionState == "connected", frames=self.received,
                    receiving=bool(self.last_frame) and time.monotonic() - self.last_frame <= FRAME_TIMEOUT,
                    frame_age_ms=round((time.monotonic() - self.last_frame) * 1000) if self.last_frame else None)

    async def close(self, owner=None, reason="Ngắt camera từ laptop"):
        async with self.lock:
            if not self.pc or (owner is not None and owner != self.owner):
                return
            pc, generation = self.pc, self.generation
            self.pc = self.owner = self.generation = None
        async def finish():
            # Revoke images/motor ownership before waiting on the WebRTC transport.
            await asyncio.to_thread(self.service.end_camera, generation, reason)
            await pc.close()

        teardown = asyncio.create_task(finish())
        self.closing.add(teardown)
        teardown.add_done_callback(self.closing.discard)
        await asyncio.shield(teardown)

    async def shutdown(self):
        await self.close(reason="Đóng ứng dụng camera")
        current = asyncio.current_task()
        tasks = [task for task in self.tasks if task is not current]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*self.closing, return_exceptions=True)

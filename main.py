import json
import os
import shutil
import subprocess
from functools import reduce
from pathlib import Path

CONFIG_FILE = "config.json"
PROJECT_DIR = Path(__file__).absolute().parent


class PathIsNotDir(ValueError): ...


class NoImagesFound(ValueError): ...


class FailedToRender(ValueError): ...


class FailedToPrepareFrames(ValueError): ...


class FrameRenderer:
    FRAME_EXTS = ["png"]
    FRAME_FMT = "frame_{idx:06d}{ext}"
    FFMPEG_FRAME_FMT = "frame_%06d.png"

    def collect_files_ordered(self, dir: Path, exts: list[str]) -> list[Path]:
        def accBlob(acc, x):
            acc.extend(x)
            return acc

        return sorted(
            reduce(
                accBlob,
                (dir.glob(f"*.{ext}") for ext in exts),
                [],
            ),
            key=lambda f: f.name,
        )

    def copy_frame(self, img, buffer_dir, idx, ext):
        new_name = buffer_dir / self.FRAME_FMT.format(idx=idx, ext=ext)
        if not new_name.exists():
            os.link(img, new_name)

    def prepare_frames(self, frames: list[Path], buffer_dir: Path, frames_setup: dict, fps):
        idx = 0
        for img in frames:
            ext = img.suffix.lower()
            if img.name in frames_setup:
                setup = frames_setup[img.name]
                length = setup["length"]
                for i in range(round((length * fps) / 1000)):
                    self.copy_frame(img, buffer_dir, idx, ext)
                    idx += 1
            else:
                self.copy_frame(img, buffer_dir, idx, ext)
                idx += 1

    def render_video_from_frames(
        self, input_dir: Path, output_file: Path, input_fps: int, output_fps: int
    ):
        command = [
            "ffmpeg",
            "-framerate",
            str(input_fps),
            "-i",
            str(input_dir / self.FFMPEG_FRAME_FMT),
            "-r",
            str(output_fps),
            "-pix_fmt",
            "yuv420p",
            str(output_file),
        ]
        subprocess.run(command, check=True)

    def render(
        self,
        input_dir: Path,
        output_file: Path,
        input_fps: int,
        output_fps: int,
        frames_setup,
    ) -> None:
        input_dir = input_dir.absolute()
        output_file = output_file.absolute()

        if not input_dir.is_dir():
            raise PathIsNotDir()

        images = self.collect_files_ordered(input_dir, self.FRAME_EXTS)

        if not images:
            raise NoImagesFound()

        temp_dir = input_dir / "ffmpeg_frames"
        temp_dir.mkdir(exist_ok=True)
        try:
            self.prepare_frames(images, temp_dir, frames_setup, input_fps)
        except:
            raise FailedToPrepareFrames()
        try:
            self.render_video_from_frames(temp_dir, output_file, input_fps, output_fps)
        except:
            raise FailedToRender()
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    renderer = FrameRenderer()
    with open(PROJECT_DIR / CONFIG_FILE) as f:
        config = json.loads(f.read())
    scene = config["scene"]

    with open(PROJECT_DIR / f"{scene}.json") as f:
        scene_config = json.loads(f.read())
    config.update(scene_config)

    scene_folder = Path(config["scenes_folder"]) / config["scene"]
    video_file = Path(config["result_folder"]) / f"{config['scene']}.mp4"
    Path(config["result_folder"]).mkdir(exist_ok=True)

    renderer.render(
        scene_folder,
        video_file,
        config["input_fps"],
        config["output_fps"],
        config["frames"],
    )

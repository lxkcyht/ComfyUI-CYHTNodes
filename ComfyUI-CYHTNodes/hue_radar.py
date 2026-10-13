import io

import numpy as np
import torch
from PIL import Image

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import rgb_to_hsv


class HueWheelRadar:
    """把图像像素按色相角度分箱，绘制极坐标色轮雷达图。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"label": "图像"}),
                "bins": ("INT", {"default": 72, "min": 12, "max": 360, "step": 1, "label": "分箱数"}),
                "metric": (
                    ["像素数量", "平均饱和度", "平均明度", "数量×饱和度"],
                    {"default": "像素数量", "label": "统计方式"},
                ),
                "max_samples": ("INT", {"default": 100000, "min": 1000, "max": 5000000, "step": 1000, "label": "最大采样数"}),
                "min_saturation": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "step": 0.01, "label": "最低饱和度"}),
                "min_value": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "step": 0.01, "label": "最低明度"}),
                "normalize": (["最大值", "总和", "不归一化"], {"default": "最大值", "label": "归一化方式"}),
                "log_scale": (["线性", "对数"], {"default": "线性", "label": "缩放方式"}),
                "display_mode": (["色轮", "混合"], {"default": "色轮", "label": "显示模式"}),
                "fig_size": ("INT", {"default": 512, "min": 256, "max": 2048, "step": 64, "label": "图像尺寸"}),
                "bg_color": (["白色", "黑色", "透明"], {"default": "白色", "label": "背景颜色"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("色轮雷达图",)
    FUNCTION = "render"
    CATEGORY = "图像分析"

    def render(
        self,
        image,
        bins,
        metric,
        max_samples,
        min_saturation,
        min_value,
        normalize,
        log_scale,
        display_mode,
        fig_size,
        bg_color,
    ):
        batch = image.shape[0]
        outputs = []
        is_transparent = (bg_color == "透明")

        for b in range(batch):
            img = image[b].detach().cpu().numpy()
            pixels = img.reshape(-1, 3).astype(np.float32)

            n = pixels.shape[0]
            if n > max_samples:
                rng = np.random.default_rng(1234)
                idx = rng.choice(n, max_samples, replace=False)
                pixels = pixels[idx]

            hsv = rgb_to_hsv(pixels.reshape(1, -1, 3)).reshape(-1, 3)
            h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]

            mask = (s >= min_saturation) & (v >= min_value)
            h, s, v = h[mask], s[mask], v[mask]

            if h.size == 0:
                outputs.append(self._blank(fig_size, bg_color))
                continue

            if metric == "像素数量":
                weights = np.ones_like(h)
            elif metric == "平均饱和度":
                weights = s
            elif metric == "平均明度":
                weights = v
            else:
                weights = s * v

            hist, _ = np.histogram(
                h * 360.0,
                bins=bins,
                range=(0.0, 360.0),
                weights=weights,
            )

            if normalize == "最大值" and hist.max() > 0:
                hist = hist / hist.max()
            elif normalize == "总和" and hist.sum() > 0:
                hist = hist / hist.sum()

            if log_scale == "对数":
                hist = np.log1p(hist)
                if hist.max() > 0:
                    hist = hist / hist.max()

            outputs.append(
                self._draw(hist, bins, display_mode, fig_size, bg_color, is_transparent)
            )

        out = np.stack(outputs, axis=0)
        return (torch.from_numpy(out).float(),)

    def _draw(self, hist, bins, display_mode, fig_size, bg_color, is_transparent):
        dpi = 100
        fig = plt.figure(figsize=(fig_size / dpi, fig_size / dpi), dpi=dpi)

        if is_transparent:
            fig.patch.set_alpha(0.0)
            ax_bg = "none"
        elif bg_color == "黑色":
            fig.patch.set_facecolor("black")
            ax_bg = "black"
        else:
            fig.patch.set_facecolor("white")
            ax_bg = "white"

        ax = plt.subplot(111, projection="polar")
        ax.set_facecolor(ax_bg)

        theta = np.deg2rad(
            np.linspace(0, 360, bins, endpoint=False) + 180.0 / bins
        )
        colors = plt.cm.hsv(np.linspace(0, 1, bins, endpoint=False))

        theta_closed = np.append(theta, theta[0] + 2 * np.pi)
        hist_closed = np.append(hist, hist[0])

        if display_mode == "色轮":
            width = 2 * np.pi / bins
            for i in range(bins):
                if hist[i] <= 0:
                    continue
                t1 = theta[i] - width / 2
                t2 = theta[i] + width / 2
                ax.fill(
                    [t1, t1, t2, t2],
                    [0, hist[i], hist[i], 0],
                    color=colors[i],
                    alpha=0.9,
                    linewidth=0,
                    edgecolor='none',
                )
            theta_ring = np.linspace(0, 2 * np.pi, 360)
            for i in range(360):
                ax.plot([theta_ring[i], theta_ring[i]], [1.02, 1.08],
                        color=plt.cm.hsv(i / 360), linewidth=2)

        else:
            for i in range(bins):
                t1 = theta_closed[i]
                t2 = theta_closed[i + 1]
                h1 = hist_closed[i]
                h2 = hist_closed[i + 1]
                if h1 <= 0 and h2 <= 0:
                    continue
                angle_deg = np.rad2deg((t1 + t2) / 2) % 360
                color = plt.cm.hsv(angle_deg / 360.0)
                ax.fill(
                    [t1, t1, t2, t2],
                    [0, h1, h2, 0],
                    color=color,
                    alpha=0.75,
                    linewidth=0,
                    edgecolor='none',
                )

            ax.plot(
                theta_closed, hist_closed,
                color="black", linewidth=1.2, alpha=0.75,
                solid_joinstyle='miter', solid_capstyle='butt',
            )

            for i in range(bins):
                if hist[i] <= 0:
                    continue
                ax.scatter(
                    theta[i],
                    hist[i],
                    c=[colors[i]],
                    s=14,
                    zorder=5,
                    edgecolors="none",
                )

            theta_ring = np.linspace(0, 2 * np.pi, 360)
            for i in range(360):
                ax.plot([theta_ring[i], theta_ring[i]], [1.02, 1.08],
                        color=plt.cm.hsv(i / 360), linewidth=2)

        ax.set_theta_zero_location("E")
        ax.set_theta_direction(-1)
        ax.set_xticks(np.deg2rad(np.arange(0, 360, 30)))
        ax.set_xticklabels([f"{a}°" for a in range(0, 360, 30)])

        text_color = "white" if bg_color == "黑色" else "black"
        ax.tick_params(colors=text_color, labelsize=8)
        ax.grid(color=text_color, alpha=0.3)
        for spine in ax.spines.values():
            spine.set_color(text_color)

        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            transparent=is_transparent,
            bbox_inches="tight",
            pad_inches=0.0,
        )
        plt.close(fig)
        buf.seek(0)

        if is_transparent:
            pil = Image.open(buf).convert("RGBA").resize(
                (fig_size, fig_size), Image.LANCZOS
            )
            arr = np.asarray(pil, dtype=np.float32) / 255.0
        else:
            pil = Image.open(buf).convert("RGB").resize(
                (fig_size, fig_size), Image.LANCZOS
            )
            arr = np.asarray(pil, dtype=np.float32) / 255.0

        return arr

    def _blank(self, fig_size, bg_color):
        if bg_color == "黑色":
            return np.zeros((fig_size, fig_size, 3), dtype=np.float32)
        if bg_color == "透明":
            return np.zeros((fig_size, fig_size, 4), dtype=np.float32)
        return np.ones((fig_size, fig_size, 3), dtype=np.float32)


NODE_CLASS_MAPPINGS = {
    "HueWheelRadar": HueWheelRadar,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HueWheelRadar": "色轮雷达图 (Hue Wheel Radar)",
}
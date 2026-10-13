import { app } from "../../scripts/app.js";

// ============ 算法常量 ============
const MEDIAN_WINDOW = 5;            // 中值滤波窗口大小（取最近5次间隔）
const EMA_ALPHA_BASE = 0.25;        // EMA基础平滑系数
const MIN_TAP_INTERVAL_MS = 100;    // 小于100ms视为误触

app.registerExtension({
    name: "Comfy.AdvancedAudioTempoTapper.Button",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "AdvancedAudioTempoTapperNode") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);

            // ============ 内部状态 ============
            let tapIntervals = [];      // 最近的点击间隔（毫秒）
            let lastTapTime = null;
            let currentBpm = 0.0;       // 当前平滑后的 BPM
            let lastRawBpm = 0.0;       // 上一次原始 BPM（用于计算波动率）

            // ============ 隐藏后端数据控件 ============
            const floatWidget = this.widgets?.find(w => w.name === "bpm_float");
            const intWidget = this.widgets?.find(w => w.name === "bpm_int");
            const textWidget = this.widgets?.find(w => w.name === "bpm_text");

            [floatWidget, intWidget, textWidget].forEach(w => {
                if (w) { w.type = "hidden"; w.computeSize = () => [0, -4]; }
            });

            // ============ 创建 UI ============
            const container = document.createElement("div");
            Object.assign(container.style, {
                display: "flex", flexDirection: "column", gap: "8px",
                padding: "10px", width: "100%", boxSizing: "border-box",
                backgroundColor: "#1e1e1e", borderRadius: "8px", marginTop: "10px",
                minHeight: "220px"
            });

            const statusLabel = document.createElement("div");
            statusLabel.textContent = "BPM: 等待打拍...";
            Object.assign(statusLabel.style, {
                color: "#ccc", fontSize: "18px", fontFamily: "monospace",
                textAlign: "center", padding: "8px",
                backgroundColor: "#2a2a2a", borderRadius: "6px"
            });

            // ---- 超大 TAP 按钮 ----
            const tapButton = document.createElement("button");
            tapButton.textContent = "TAP (点击打拍)";
            Object.assign(tapButton.style, {
                width: "100%", height: "80px", fontSize: "26px",
                fontWeight: "bold", color: "#fff", backgroundColor: "#10b981",
                border: "none", borderRadius: "10px", cursor: "pointer",
                transition: "background 0.15s, transform 0.1s"
            });
            tapButton.onmouseover = () => tapButton.style.backgroundColor = "#059669";
            tapButton.onmouseout = () => tapButton.style.backgroundColor = "#10b981";
            tapButton.onmousedown = () => tapButton.style.transform = "scale(0.97)";
            tapButton.onmouseup = () => tapButton.style.transform = "scale(1)";

            // ============ 核心算法 ============
            function median(arr) {
                if (!arr.length) return 0;
                const sorted = [...arr].sort((a, b) => a - b);
                const mid = Math.floor(sorted.length / 2);
                return sorted.length % 2 !== 0
                    ? sorted[mid]
                    : (sorted[mid - 1] + sorted[mid]) / 2;
            }

            tapButton.onclick = () => {
                const now = performance.now(); // 高精度单调时钟

                // --- 记录间隔 ---
                if (lastTapTime !== null) {
                    const interval = now - lastTapTime;

                    // 过滤异常间隔（仅保留最短下限，防止手抖误触）
                    if (interval > MIN_TAP_INTERVAL_MS) {
                        tapIntervals.push(interval);
                        if (tapIntervals.length > MEDIAN_WINDOW) {
                            tapIntervals.shift();
                        }

                        // --- 中值滤波得到稳健间隔 ---
                        const medInterval = median(tapIntervals);
                        const rawBpm = 60000 / medInterval;

                        // --- 自适应 EMA 平滑 ---
                        // 波动大时 alpha 大（快速响应），波动小时 alpha 小（抑制抖动）
                        let alpha = EMA_ALPHA_BASE;
                        if (lastRawBpm > 0) {
                            const variation = Math.abs(rawBpm - lastRawBpm) / lastRawBpm;
                            if (variation > 0.15) alpha = 0.5;
                            else if (variation < 0.05) alpha = 0.1;
                        }

                        currentBpm = currentBpm === 0
                            ? rawBpm
                            : alpha * rawBpm + (1 - alpha) * currentBpm;

                        lastRawBpm = rawBpm;

                        // --- 更新 UI 和数据 ---
                        const bpmFloat = currentBpm;
                        const bpmInt = Math.round(currentBpm);
                        const bpmText = `${bpmInt} BPM`;

                        statusLabel.textContent = `BPM: ${bpmFloat.toFixed(1)}  (点击 ${tapIntervals.length + 1})`;
                        syncWidgets(bpmFloat, bpmInt, bpmText);
                    }
                }

                lastTapTime = now;
                this.setDirtyCanvas(true, true);
            };

            function syncWidgets(f, i, t) {
                if (floatWidget) floatWidget.value = f;
                if (intWidget) intWidget.value = i;
                if (textWidget) textWidget.value = t;
            }

            // ---- 重置按钮 ----
            const resetButton = document.createElement("button");
            resetButton.textContent = "重置 (Reset)";
            Object.assign(resetButton.style, {
                width: "100%", height: "40px", fontSize: "16px",
                color: "#fff", backgroundColor: "#ef4444",
                border: "none", borderRadius: "8px", cursor: "pointer"
            });
            resetButton.onclick = () => {
                tapIntervals = [];
                lastTapTime = null;
                currentBpm = 0.0;
                lastRawBpm = 0.0;
                statusLabel.textContent = "BPM: 等待打拍...";
                syncWidgets(0, 0, "0 BPM");
                this.setDirtyCanvas(true, true);
            };

            // ============ 底部说明文字 ============
            const helpLabel = document.createElement("div");
            helpLabel.innerHTML =
                "<b>说明</b><br>" +
                "• 点击上限显示为 6 是正常的：算法使用'滑动窗口'，只保留最近 5 个时间间隔，对应 6 次点击。<br>" +
                "• 打拍越均匀，读数越稳定；建议至少打 6~8 次。打点结束后运行工作流会自动发送三种类型的输出。";
            Object.assign(helpLabel.style, {
                color: "#888", fontSize: "12px", lineHeight: "1.5",
                fontFamily: "sans-serif", textAlign: "left",
                padding: "8px", backgroundColor: "#151515",
                borderRadius: "6px", borderTop: "1px solid #333"
            });

            // ============ 组装 DOM ============
            container.appendChild(statusLabel);
            container.appendChild(tapButton);
            container.appendChild(resetButton);
            container.appendChild(helpLabel);

            // ============ 添加 DOM Widget 并指定初始大小 ============
            if (this.addDOMWidget) {
                this.addDOMWidget("tap_ui", "button", container, {
                    serialize: false,
                    getValue: () => null,
                    setValue: () => {},
                    computeSize: () => [320, 260]
                });
            } else {
                console.warn("当前 ComfyUI 版本不支持 addDOMWidget，已回退到普通按钮。");
                this.addWidget("button", "TAP (点击打拍)", null, () => tapButton.onclick());
            }

            // ============ 设置默认大小和最小尺寸限制 ============
            // 调整后的大小，允许节点缩得比之前更小一点
            this.setSize([340, 380]);

            // 最小尺寸限制：宽度 340，高度 380
            this.minSize = [340, 380];

            // 双保险：监听 resize，防止拖到比最小值还小
            const onResize = this.onResize;
            this.onResize = function (size) {
                if (onResize) onResize.apply(this, arguments);
                size[0] = Math.max(size[0], 340);
                size[1] = Math.max(size[1], 380);
            };
        };
    }
});
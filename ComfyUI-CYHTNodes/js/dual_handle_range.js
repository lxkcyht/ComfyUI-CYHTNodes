import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Comfy.DualHandleRange",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "GetSessionAlphaString") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            const MIN = 1;
            const MAX = 16;
            const widgetHeight = 30;
            const handleRadius = 7;
            const margin = 12;

            // 隐藏后端定义的两个默认数值控件
            for (const w of this.widgets) {
                if (w.name === "起始位置" || w.name === "结束位置") {
                    w.computeSize = () => [0, -4]; // 高度设为负数以完全隐藏
                    w.draw = () => {};              // 不绘制任何内容
                    w.disabled = true;             // 禁用交互
                }
            }

            const startWidget = this.widgets.find(w => w.name === "起始位置");
            const endWidget = this.widgets.find(w => w.name === "结束位置");
            if (!startWidget || !endWidget) return r;

            let draggingHandle = null; // "start" | "end" | null

            // 坐标换算工具函数
            function valToX(val, w) {
                const trackLeft = margin + handleRadius;
                const trackRight = w - margin - handleRadius;
                const ratio = (val - MIN) / (MAX - MIN);
                return trackLeft + ratio * (trackRight - trackLeft);
            }
            function xToVal(x, w) {
                const trackLeft = margin + handleRadius;
                const trackRight = w - margin - handleRadius;
                let ratio = (x - trackLeft) / (trackRight - trackLeft);
                ratio = Math.max(0, Math.min(1, ratio));
                return Math.round(MIN + ratio * (MAX - MIN));
            }

            // 自定义 Widget
            const rangeWidget = {
                type: "dual_handle_range",
                name: "范围选择",
                value: [startWidget.value, endWidget.value],
                y: 0,
                options: { serialize: false },

                computeSize(width) {
                    return [width, widgetHeight];
                },

                draw(ctx, node, width, y) {
                    this.y = y;
                    // ★ 关键：每次都直接从后端控件读取当前值，
                    //   确保工作流加载恢复后的值与界面显示一致
                    const valueStart = startWidget.value;
                    const valueEnd = endWidget.value;
                    const trackLeft = margin + handleRadius;
                    const trackRight = width - margin - handleRadius;

                    ctx.save();

                    // 1. 背景轨道
                    ctx.strokeStyle = "#555";
                    ctx.lineWidth = 4;
                    ctx.lineCap = "round";
                    ctx.beginPath();
                    ctx.moveTo(trackLeft, y + widgetHeight / 2);
                    ctx.lineTo(trackRight, y + widgetHeight / 2);
                    ctx.stroke();

                    // 2. 选中区间
                    const xStart = valToX(valueStart, width);
                    const xEnd = valToX(valueEnd, width);
                    ctx.strokeStyle = "#4a9eff";
                    ctx.lineWidth = 4;
                    ctx.beginPath();
                    ctx.moveTo(xStart, y + widgetHeight / 2);
                    ctx.lineTo(xEnd, y + widgetHeight / 2);
                    ctx.stroke();

                    // 3. 手柄
                    const cy = y + widgetHeight / 2;
                    ctx.fillStyle = draggingHandle === "start" ? "#ffffff" : "#4a9eff";
                    ctx.beginPath();
                    ctx.arc(xStart, cy, handleRadius, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = "#fff";
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    ctx.fillStyle = draggingHandle === "end" ? "#ffffff" : "#4a9eff";
                    ctx.beginPath();
                    ctx.arc(xEnd, cy, handleRadius, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.stroke();

                    // 4. 数值文本
                    ctx.fillStyle = "#ccc";
                    ctx.font = "11px monospace";
                    ctx.textAlign = "center";
                    ctx.fillText(`${valueStart} - ${valueEnd}`, width / 2, y + widgetHeight - 3);
                    ctx.restore();
                },

                mouse(event, pos, node) {
                    const [mx, my] = pos;
                    const cy = this.y + widgetHeight / 2;
                    const w = this.width || node.size[0];
                    const valueStart = startWidget.value;
                    const valueEnd = endWidget.value;
                    const xStart = valToX(valueStart, w);
                    const xEnd = valToX(valueEnd, w);

                    if (event.type === "pointerdown") {
                        const distStart = Math.hypot(mx - xStart, my - cy);
                        const distEnd = Math.hypot(mx - xEnd, my - cy);
                        const hitRadius = handleRadius + 5;

                        if (distStart < hitRadius && distStart <= distEnd) {
                            draggingHandle = "start";
                            return true;
                        }
                        if (distEnd < hitRadius) {
                            draggingHandle = "end";
                            return true;
                        }
                        // 点击空白区域，移动最近的手柄
                        const clickedVal = xToVal(mx, w);
                        if (Math.abs(clickedVal - valueStart) <= Math.abs(clickedVal - valueEnd)) {
                            draggingHandle = "start";
                            startWidget.value = Math.min(clickedVal, valueEnd);
                        } else {
                            draggingHandle = "end";
                            endWidget.value = Math.max(clickedVal, valueStart);
                        }
                        node.setDirtyCanvas(true, true);
                        return true;
                    }

                    if (event.type === "pointermove" && draggingHandle) {
                        const newVal = xToVal(mx, w);
                        if (draggingHandle === "start") {
                            startWidget.value = Math.min(newVal, endWidget.value);
                        } else {
                            endWidget.value = Math.max(newVal, startWidget.value);
                        }
                        node.setDirtyCanvas(true, true);
                        return true;
                    }

                    if (event.type === "pointerup") {
                        draggingHandle = null;
                        node.setDirtyCanvas(true, true);
                        return true;
                    }
                    return false;
                },
            };

            this.onDrawForeground = function (ctx) {
                rangeWidget.width = this.size[0];
            };

            this.addCustomWidget(rangeWidget);
            return r;
        };
    },
});
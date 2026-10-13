

import importlib
import logging

LOGGER = logging.getLogger("ComfyUI-CYHTNode")

# 子模块顺序 = 节点在菜单/映射中的注册顺序
_SUBMODULES = (
    "session_alpha_string",
    "hue_radar",
    "prompt_weight_baroscope",
    "tap_tempo_node",
)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

for _submodule_name in _SUBMODULES:
    try:
        _module = importlib.import_module("." + _submodule_name, __package__)
    except Exception as _exc:  # 单个子模块缺依赖时，不影响其余节点加载
        LOGGER.exception(
            "[ComfyUI-CYHTNode] 子模块 %s 加载失败（其余节点仍可用）：%s",
            _submodule_name,
            _exc,
        )
        continue

    NODE_CLASS_MAPPINGS.update(getattr(_module, "NODE_CLASS_MAPPINGS", None) or {})
    NODE_DISPLAY_NAME_MAPPINGS.update(
        getattr(_module, "NODE_DISPLAY_NAME_MAPPINGS", None) or {}
    )

# 前端 JS 扩展目录（本包统一的 WEB_DIRECTORY，包含全部子插件的前端脚本）：
#   js/dual_handle_range.js   为“获取会话UID”节点提供双手柄范围控件
#   js/tap_tempo_button.js    为“TAP节拍打点器”节点提供打拍按钮 UI
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

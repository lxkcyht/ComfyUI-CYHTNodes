class AdvancedAudioTempoTapperNode:
    """
    高级 TAP 节拍打点器：前端负责计算 BPM，后端透传输出。
    输出：数字(FLOAT)、整数(INT)、文本(STRING)
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bpm_float": ("FLOAT", {"default": 0.0}),
                "bpm_int": ("INT", {"default": 0}),
                "bpm_text": ("STRING", {"default": "0 BPM", "multiline": False}),
            }
        }

    RETURN_TYPES = ("FLOAT", "INT", "STRING")
    RETURN_NAMES = ("节拍浮点数", "节拍整数", "节拍文本")
    FUNCTION = "execute"
    CATEGORY = "音频/节拍"
    OUTPUT_NODE = True

    def execute(self, bpm_float, bpm_int, bpm_text):
        return (bpm_float, bpm_int, bpm_text)


NODE_CLASS_MAPPINGS = {
    "AdvancedAudioTempoTapperNode": AdvancedAudioTempoTapperNode
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedAudioTempoTapperNode": "TAP节拍打点器"
}
import hashlib
import uuid

SESSION_SEED = uuid.uuid4().int
FULL_LENGTH = 16

def _seed_to_alpha(seed_int, length=FULL_LENGTH):
    hash_bytes = hashlib.sha256(str(seed_int).encode('utf-8')).digest()
    num = int.from_bytes(hash_bytes[:16], 'big')
    base = 26
    num_mod = num % (base ** length)
    chars = [chr(ord('A') + (num_mod // (base ** i)) % base) for i in range(length)]
    return ''.join(reversed(chars))

SESSION_ALPHA_FULL = _seed_to_alpha(SESSION_SEED, FULL_LENGTH)
print(f"[DualHandleRange] ComfyUI started. Full session alpha string (16): {SESSION_ALPHA_FULL}")


class GetSessionAlphaString:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # 这两个参数由前端 JS 控制，不在节点面板上直接显示
                "起始位置": ("INT", {"default": 1, "min": 1, "max": FULL_LENGTH, "step": 1}),
                "结束位置": ("INT", {"default": FULL_LENGTH, "min": 1, "max": FULL_LENGTH, "step": 1}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("会话UID",)
    FUNCTION = "get_session_alpha"
    CATEGORY = "utils/工具"

    def get_session_alpha(self, 起始位置, 结束位置):
        start = min(起始位置, 结束位置)
        end = max(起始位置, 结束位置)
        result = SESSION_ALPHA_FULL[start - 1:end]
        return (result,)


NODE_CLASS_MAPPINGS = {"GetSessionAlphaString": GetSessionAlphaString}
NODE_DISPLAY_NAME_MAPPINGS = {"GetSessionAlphaString": "获取会话UID"}
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
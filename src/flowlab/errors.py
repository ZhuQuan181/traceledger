"""跨模块共享的控制流异常。"""


class ExperimentCancelled(Exception):
    """用户取消了仍在执行的实验。"""

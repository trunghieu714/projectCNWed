from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseScorer(ABC):
    """
    Abstract Base Class cho các thuật toán đánh giá kỹ năng (Strategy Pattern).
    Cho phép linh hoạt hoán đổi giữa Classic DTW, Weighted DTW, hoặc Rule-based Neuro-Symbolic.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, coach_data: Dict[str, Any], student_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        So khớp và tính toán điểm số giữa bài mẫu của HLV và bài nộp của HV.

        Returns:
            Dict chứa:
                - "final_score": float (0 - 100)
                - "warping_path": List[Tuple[int, int]] (ánh xạ frame HLV <-> frame HV)
                - "frame_errors": List[Dict] (danh sách các frame bị lệch và góc sai lệch)
                - "feedback_summary": str (nhận xét tự động)
        """
        pass
